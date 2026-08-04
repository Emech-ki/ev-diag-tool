"""
Main Window — v2.0.0 With Multi-Provider + Vehicle Selector + Model Info
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QStatusBar, QMessageBox,
    QTabWidget, QFrame, QComboBox, QMenu
)
from typing import Optional
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QEvent, QObject
from PyQt6.QtGui import QMouseEvent


class _ViewRightClickFilter(QObject):
    """拦截 QComboBox 弹出框 viewport 的右键事件"""

    right_clicked = pyqtSignal(int)  # 发射被右键的行号

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
            if event.button() == Qt.MouseButton.RightButton:
                # obj 是 viewport，通过 parent() 获取 view
                view = obj.parent()
                if view and hasattr(view, 'indexAt'):
                    index = view.indexAt(event.pos())
                    if index.isValid():
                        self.right_clicked.emit(index.row())
                return True  # 阻止 view 处理（不会选中+关闭）
        return super().eventFilter(obj, event)


class _RightClickComboBox(QComboBox):
    """支持右键弹出菜单的 QComboBox"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view_filter = _ViewRightClickFilter(self)

    def showPopup(self):
        super().showPopup()  # 先弹出，确保 view/viewport 已创建
        # 将事件过滤器安装到 viewport（真正接收鼠标事件的 widget）
        vp = self.view().viewport()
        if vp:
            vp.installEventFilter(self._view_filter)

    @property
    def view_right_clicked(self):
        """返回 view 右键信号，外部可连接"""
        return self._view_filter.right_clicked

from src.engine.diagnostic import DiagnosticEngine, DiagnosticResult
from src.ui.result_panel import ResultPanel
from src.ui.agent_chat import AgentChatPanel
from src.ui.history_panel import HistoryPanel
from src.ui.styles import (
    PRIMARY, PRIMARY_DARK, PRIMARY_BG,
    BG, CARD_BG, CARD_BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, FONT_MONO,
    SUCCESS, SUCCESS_BG, WARNING, WARNING_BG
)

from src.version import VERSION_LINE
from src.config import AI_PROVIDER, append_endpoint_to_env, remove_endpoint_from_env, update_endpoint_in_env
from src.ui.add_endpoint_dialog import AddEndpointDialog


class DiagnoseWorker(QThread):
    kb_ready = pyqtSignal(object)   # partial DiagnosticResult (KB done, AI not yet)
    ai_token = pyqtSignal(str)       # one token from streaming AI
    ai_finished = pyqtSignal(str)    # full AI text when streaming done
    finished = pyqtSignal(object)    # complete DiagnosticResult
    error = pyqtSignal(str)

    def __init__(self, engine: DiagnosticEngine, code: str, vehicle: str = "", extra: str = ""):
        super().__init__()
        self.engine = engine
        self.code = code
        self.vehicle = vehicle
        self.extra = extra

    def run(self):
        try:
            code = self.code.strip().upper()

            # Phase 1: KB query (fast)
            knowledge = self.engine.kb.lookup(code)
            ai_available = self.engine.llm.is_available()

            partial = DiagnosticResult(
                code=code,
                knowledge=knowledge,
                ai_suggestion=None,
                ai_available=ai_available
            )
            self.kb_ready.emit(partial)

            # Phase 2: AI streaming
            ai_suggestion = None
            if ai_available:
                tokens = []
                for token in self.engine.llm.get_diagnostic_suggestion_stream(
                    code=code,
                    knowledge=knowledge,
                    vehicle_info=self.vehicle,
                    additional_info=self.extra
                ):
                    tokens.append(token)
                    self.ai_token.emit(token)
                ai_suggestion = "".join(tokens)
                self.ai_finished.emit(ai_suggestion)

            # Final complete result
            result = DiagnosticResult(
                code=code,
                knowledge=knowledge,
                ai_suggestion=ai_suggestion,
                ai_available=ai_available
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MultiDiagnoseWorker(QThread):
    """多故障码诊断工作线程"""
    progress = pyqtSignal(str)       # 进度信息
    finished = pyqtSignal(object)    # MultiCodeDiagnosticResult
    error = pyqtSignal(str)

    def __init__(self, engine: DiagnosticEngine, codes: list, vehicle: str = "", extra: str = ""):
        super().__init__()
        self.engine = engine
        self.codes = codes
        self.vehicle = vehicle
        self.extra = extra

    def run(self):
        try:
            self.progress.emit(f"正在分析 {len(self.codes)} 个故障码...")
            result = self.engine.diagnose_multiple(
                codes=self.codes,
                vehicle_info=self.vehicle,
                additional_info=self.extra
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class _AICheckWorker(QThread):
    """后台检查 AI Provider 可用性，避免阻塞主线程"""
    result = pyqtSignal(bool, list)  # (is_available, models)

    def __init__(self, llm):
        super().__init__()
        self.llm = llm

    def run(self):
        try:
            available = self.llm.is_available()
            models = self.llm.get_available_models() if available else []
            self.result.emit(available, models)
        except Exception:
            self.result.emit(False, [])


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.engine = DiagnosticEngine()
        self.worker: Optional[DiagnoseWorker] = None
        self._ai_check_worker = None
        self._model_selector_updating = False
        self._init_ui()
        self._check_database()
        self._check_ai()
        self._load_vehicle_data()

    def _init_ui(self):
        self.setWindowTitle(f"EV-Diag-Tool {VERSION_LINE}")
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(f"QMainWindow {{ background-color: {BG}; }}")

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ── Brand Bar ──
        brand = QFrame()
        brand.setStyleSheet(f"background-color: {PRIMARY_DARK};")
        brand.setFixedHeight(52)
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(24, 0, 24, 0)

        title = QLabel("EV-Diag-Tool")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        brand_layout.addWidget(title)

        ver = QLabel(VERSION_LINE)
        ver.setStyleSheet("color: rgba(255,255,255,0.45); font-size: 11px; margin-left: 8px; padding-top: 2px;")
        brand_layout.addWidget(ver)

        brand_layout.addStretch()

        # ── Provider Selector (本地模型 / 调用模型) ──
        brand_combo_style = f"""
            QComboBox {{
                font-size: 12px; padding: 4px 8px;
                background-color: rgba(255,255,255,0.15);
                color: white; border: 1px solid rgba(255,255,255,0.3);
                border-radius: 6px;
            }}
            QComboBox:hover {{ background-color: rgba(255,255,255,0.25); }}
            QComboBox::drop-down {{
                border: none; width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: white; color: {TEXT_PRIMARY};
                border: 1px solid {CARD_BORDER}; selection-background-color: {PRIMARY_BG};
            }}
        """

        self.provider_selector = _RightClickComboBox()
        self.provider_selector.setMinimumWidth(120)
        self.provider_selector.setMaximumHeight(30)
        self.provider_selector.setStyleSheet(brand_combo_style)
        self.provider_selector.currentTextChanged.connect(self._on_provider_changed)
        self.provider_selector.view_right_clicked.connect(self._on_provider_view_right_click)
        self.provider_selector.installEventFilter(self)
        brand_layout.addWidget(self.provider_selector)

        brand_layout.addSpacing(6)

        # ── Model Selector ──
        self.model_selector = QComboBox()
        self.model_selector.setEditable(True)
        self.model_selector.setMinimumWidth(160)
        self.model_selector.setMaximumHeight(30)
        self.model_selector.setStyleSheet(brand_combo_style)
        self.model_selector.currentTextChanged.connect(self._on_model_changed)
        brand_layout.addWidget(self.model_selector)

        brand_layout.addSpacing(14)

        self.db_dot = QLabel("●")
        self.db_dot.setStyleSheet("color: #9AA0A6; font-size: 12px;")
        brand_layout.addWidget(self.db_dot)
        self.db_status_label = QLabel("Database")
        self.db_status_label.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 11px; margin-left: 4px; margin-right: 14px;")
        brand_layout.addWidget(self.db_status_label)

        self.ollama_dot = QLabel("●")
        self.ollama_dot.setStyleSheet("color: #9AA0A6; font-size: 12px;")
        brand_layout.addWidget(self.ollama_dot)
        self.ollama_status_label = QLabel("AI")
        self.ollama_status_label.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 11px; margin-left: 4px;")
        brand_layout.addWidget(self.ollama_status_label)

        brand_layout.addSpacing(14)

        # ── Theme Toggle ──
        self.brand = brand
        self.theme_btn = QPushButton()
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.setFixedSize(32, 32)
        self.theme_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                font-size: 16px; color: rgba(255,255,255,0.85);
            }
            QPushButton:hover { background: rgba(255,255,255,0.15); border-radius: 6px; }
        """)
        self.theme_btn.setToolTip("切换深色/浅色模式")
        self.theme_btn.clicked.connect(self._on_toggle_theme)
        brand_layout.addWidget(self.theme_btn)
        self._update_theme_btn_icon()

        main_layout.addWidget(brand)

        # ── Content ──
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(28, 20, 28, 20)

        # ── Search Card ──
        search_card = QFrame()
        self.search_card = search_card
        search_card.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 12px;
            }}
        """)
        search_layout = QVBoxLayout(search_card)
        search_layout.setContentsMargins(20, 16, 20, 16)
        search_layout.setSpacing(10)

        search_title = QLabel("故障码诊断")
        self.search_title = search_title
        search_title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT_PRIMARY};")
        search_layout.addWidget(search_title)

        code_row = QHBoxLayout()
        code_row.setSpacing(10)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("输入故障码，如 P0300")
        self.code_input.setStyleSheet(f"""
            QLineEdit {{
                font-size: 16px; padding: 8px 14px; font-family: "{FONT_MONO}";
                border: 2px solid {CARD_BORDER}; border-radius: 10px;
                background: white; min-height: 26px;
            }}
            QLineEdit:focus {{ border-color: {PRIMARY}; }}
        """)
        self.code_input.returnPressed.connect(self.on_diagnose)
        code_row.addWidget(self.code_input, 3)

        self.search_btn = QPushButton("诊断")
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.setMinimumHeight(44)
        self.search_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 15px; font-weight: bold;
                background-color: {PRIMARY}; color: white;
                border: none; border-radius: 10px;
                padding: 4px 32px;
            }}
            QPushButton:hover {{ background-color: {PRIMARY_DARK}; }}
            QPushButton:disabled {{ background-color: #90CAF9; }}
        """)
        self.search_btn.clicked.connect(self.on_diagnose)
        code_row.addWidget(self.search_btn)

        search_layout.addLayout(code_row)

        extra_row = QHBoxLayout()
        extra_row.setSpacing(8)

        combo_style = f"""
            QComboBox {{
                font-size: 13px; padding: 6px 10px;
                border: 1px solid {CARD_BORDER}; border-radius: 8px;
                background: white; min-height: 22px;
            }}
            QComboBox:focus {{ border-color: {PRIMARY}; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox QAbstractItemView {{
                background-color: white; color: {TEXT_PRIMARY};
                border: 1px solid {CARD_BORDER}; selection-background-color: {PRIMARY_BG};
            }}
        """

        self.make_selector = QComboBox()
        self.make_selector.setPlaceholderText("品牌")
        self.make_selector.setMinimumWidth(120)
        self.make_selector.setStyleSheet(combo_style)
        self.make_selector.currentTextChanged.connect(self._on_make_changed)
        extra_row.addWidget(self.make_selector, 1)

        self.model_selector_vehicle = QComboBox()
        self.model_selector_vehicle.setPlaceholderText("车型")
        self.model_selector_vehicle.setEditable(True)
        self.model_selector_vehicle.setMinimumWidth(160)
        self.model_selector_vehicle.setStyleSheet(combo_style)
        extra_row.addWidget(self.model_selector_vehicle, 2)

        self.symptom_input = QLineEdit()
        self.symptom_input.setPlaceholderText("症状描述（如：冷车启动抖动）")
        self.symptom_input.setStyleSheet(f"""
            QLineEdit {{
                font-size: 13px; padding: 6px 10px;
                border: 1px solid {CARD_BORDER}; border-radius: 8px;
                background: white; min-height: 22px;
            }}
            QLineEdit:focus {{ border-color: {PRIMARY}; }}
        """)
        extra_row.addWidget(self.symptom_input, 2)

        search_layout.addLayout(extra_row)
        content_layout.addWidget(search_card)

        # ── Tab Widget ──
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {CARD_BORDER};
                border-radius: 4px;
                background-color: {CARD_BG};
            }}
            QTabBar::tab {{
                padding: 10px 20px; font-size: 13px;
                border: 1px solid transparent;
                border-bottom: none;
            }}
            QTabBar::tab:selected {{
                background-color: {CARD_BG};
                border-color: {CARD_BORDER};
                border-bottom: 2px solid {PRIMARY};
                color: {PRIMARY}; font-weight: bold;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {PRIMARY_BG};
            }}
        """)

        self.result_panel = ResultPanel()
        self.result_panel.diagnose_requested.connect(self._on_related_code_clicked)
        self.result_panel.export_requested.connect(self._export_current_result)
        self.tab_widget.addTab(self.result_panel, "诊断结果")

        self.agent_panel = AgentChatPanel(self.engine)
        self.tab_widget.addTab(self.agent_panel, "AI 助手")

        self.history_panel = HistoryPanel(self.engine.kb.db)
        self.history_panel.export_requested.connect(self._export_history_record)
        self.tab_widget.addTab(self.history_panel, "历史记录")

        content_layout.addWidget(self.tab_widget, 1)
        main_layout.addWidget(content, 1)

        # ── Status Bar ──
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                background-color: {CARD_BG};
                border-top: 1px solid {CARD_BORDER};
                font-size: 11px; color: {TEXT_MUTED}; padding: 2px 16px;
            }}
        """)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 — 输入故障码开始诊断")

    # ── Status Helpers ──

    def _set_dot_status(self, dot: QLabel, text_label: QLabel, ok: bool, detail: str = ""):
        dot.setStyleSheet(f"color: {'#4CAF50' if ok else '#FF9800'}; font-size: 12px;")
        text_label.setText(detail)
        text_label.setStyleSheet(f"color: {'rgba(255,255,255,0.9)' if ok else 'rgba(255,255,255,0.6)'}; font-size: 11px; margin-left: 4px;")

    def _check_database(self):
        try:
            info = self.engine.check_database_status()
            if info["exists"] and info["total_codes"] > 0:
                self._set_dot_status(self.db_dot, self.db_status_label, True, f"DB {info['total_codes']} DTCs")
            else:
                self._set_dot_status(self.db_dot, self.db_status_label, False, "DB empty")
        except Exception:
            self._set_dot_status(self.db_dot, self.db_status_label, False, "DB error")

    OLLAMA_CHECK_DELAY = 500

    def _check_ai(self):
        """初始化 provider 选择器 + 检查 AI Provider"""
        self._init_provider_selector()
        # 手动触发当前选中的 provider 切换（信号被阻止时不会自动触发）
        current_text = self.provider_selector.currentText()
        if current_text and current_text != "+ 添加模型...":
            try:
                if current_text == "本地模型":
                    self.engine.llm.switch_to_local()
                else:
                    self.engine.llm.switch_to_remote(current_text)
            except Exception:
                pass
        self._refresh_model_list()
        QTimer.singleShot(self.OLLAMA_CHECK_DELAY, self._do_check_ai_async)

    _ADD_ENDPOINT_TAG = "__add_endpoint__"

    def _init_provider_selector(self):
        """初始化 provider 下拉框：本地模型 + 已配置的远程端点 + 添加入口。
        如果调用方已 blockSignals，会保持阻塞状态不被覆盖。"""
        was_blocked = self.provider_selector.signalsBlocked()
        self.provider_selector.blockSignals(True)
        self.provider_selector.clear()
        self.provider_selector.addItem("本地模型")

        # 添加已配置的远程端点
        endpoints = self.engine.llm.get_remote_endpoints()
        for ep in endpoints:
            self.provider_selector.addItem(ep["name"])

        # 分隔线 + 添加入口
        self.provider_selector.insertSeparator(self.provider_selector.count())
        self.provider_selector.addItem("+ 添加模型...")
        add_idx = self.provider_selector.count() - 1
        self.provider_selector.setItemData(add_idx, self._ADD_ENDPOINT_TAG, Qt.ItemDataRole.UserRole)

        # 如果配置了 AI_PROVIDER=openai 且有端点，默认选中第一个远程端点
        from src.config import AI_PROVIDER
        if AI_PROVIDER == "openai" and endpoints:
            self.provider_selector.setCurrentIndex(1)  # 第一个远程端点
        else:
            self.provider_selector.setCurrentIndex(0)  # 本地模型

        # 恢复调用方的阻塞状态（只有调用方未阻塞时才解除）
        if not was_blocked:
            self.provider_selector.blockSignals(False)

    def _on_provider_changed(self, provider_text: str):
        """Provider 切换回调"""
        if not provider_text:
            return

        # 检查是否选中了"+ 添加模型..."
        idx = self.provider_selector.currentIndex()
        tag = self.provider_selector.itemData(idx, Qt.ItemDataRole.UserRole)
        if tag == self._ADD_ENDPOINT_TAG:
            self._show_add_endpoint_dialog()
            return

        if provider_text == "本地模型":
            self.engine.llm.switch_to_local()
            self._refresh_model_list()
            self._set_dot_status(self.ollama_dot, self.ollama_status_label, False, "AI checking...")
            QTimer.singleShot(300, self._do_check_ai_async)
        else:
            # 切换到远程端点
            success = self.engine.llm.switch_to_remote(provider_text)
            if success:
                self._set_dot_status(self.ollama_dot, self.ollama_status_label, False, f"AI checking ({provider_text})...")
                self._refresh_model_list()
                self._do_check_ai_async()
            else:
                self.status_bar.showMessage(f"切换到 {provider_text} 失败")

    def _show_add_endpoint_dialog(self):
        """弹出添加远程端点对话框"""
        # 记住当前选中项，取消时恢复
        prev_index = self.provider_selector.currentIndex()
        prev_text = self.provider_selector.currentText()

        dialog = AddEndpointDialog(self)
        if dialog.exec() == AddEndpointDialog.DialogCode.Accepted and dialog.get_result():
            data = dialog.get_result()
            try:
                append_endpoint_to_env(
                    name=data["name"],
                    url=data["base_url"],
                    key=data["api_key"],
                    model=data["model_name"],
                )
                # 重新初始化 provider 选择器（会重新读取 .env 中的端点）
                self._init_provider_selector()
                # 选中新添加的端点（倒数第三项：...端点, 分隔线, +添加模型...）
                new_count = self.provider_selector.count()
                self.provider_selector.setCurrentIndex(new_count - 3)
                self.status_bar.showMessage(f"已添加远程模型: {data['name']}")
            except Exception as e:
                QMessageBox.warning(self, "保存失败", f"写入 .env 文件失败:\n{e}")
                self._init_provider_selector()
                self.provider_selector.setCurrentIndex(prev_index)
        else:
            # 用户取消，用 blockSignals 恢复选中项，避免重入 _on_provider_changed
            self.provider_selector.blockSignals(True)
            self._init_provider_selector()
            restore_idx = self.provider_selector.findText(prev_text)
            if restore_idx >= 0:
                self.provider_selector.setCurrentIndex(restore_idx)
            else:
                self.provider_selector.setCurrentIndex(0)
            self.provider_selector.blockSignals(False)

    # ── 右键删除远程端点 ──

    def eventFilter(self, obj, event):
        """拦截 Provider combo box 本体的右键事件（弹出框关闭状态）"""
        if obj is self.provider_selector and event.type() == QEvent.Type.MouseButtonPress:
            if isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.RightButton:
                row = self.provider_selector.currentIndex()
                if row >= 0:
                    self._on_provider_right_click(row)
                return True
        return super().eventFilter(obj, event)

    def _on_provider_view_right_click(self, row: int):
        """弹出框列表中右键点击某项（由 _RightClickComboBox 信号触发）"""
        self._on_provider_right_click(row)

    def _on_provider_right_click(self, row: int):
        """Provider 下拉框右键点击处理"""
        # 获取该项的文本和标记
        text = self.provider_selector.itemText(row)
        tag = self.provider_selector.itemData(row, Qt.ItemDataRole.UserRole)

        # 排除：本地模型、分隔线、"+ 添加模型..."
        if text == "本地模型" or tag == self._ADD_ENDPOINT_TAG or not text:
            return

        menu = QMenu(self)
        edit_action = menu.addAction(f"编辑 \"{text}\"")
        delete_action = menu.addAction(f"删除 \"{text}\"")
        action = menu.exec(self.cursor().pos())

        if action == edit_action:
            self._edit_endpoint(text)
        elif action == delete_action:
            self._delete_endpoint(text)

    def _delete_endpoint(self, name: str):
        """删除指定的远程端点"""
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除远程模型 \"{name}\" 吗？\n\n此操作将从配置中移除该端点。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            remove_endpoint_from_env(name)
            # 刷新下拉框并切回本地模型
            self._init_provider_selector()
            self.provider_selector.setCurrentIndex(0)
            # 切换 LLM provider 并刷新模型列表
            self.engine.llm.switch_to_local()
            self._refresh_model_list()
            self.status_bar.showMessage(f"已删除远程模型: {name}")
        except Exception as e:
            QMessageBox.warning(self, "删除失败", f"删除端点失败:\n{e}")

    def _edit_endpoint(self, name: str):
        """编辑指定的远程端点"""
        # 从 .env 读取现有配置
        from src.config import get_remote_endpoints
        endpoints = get_remote_endpoints()
        endpoint_data = None
        for ep in endpoints:
            if ep["name"] == name:
                endpoint_data = ep
                break

        if not endpoint_data:
            QMessageBox.warning(self, "错误", f"未找到端点 \"{name}\" 的配置")
            return

        # 记住当前选中项
        prev_index = self.provider_selector.currentIndex()

        dialog = AddEndpointDialog(self, endpoint_data=endpoint_data)
        if dialog.exec() == AddEndpointDialog.DialogCode.Accepted and dialog.get_result():
            data = dialog.get_result()
            try:
                update_endpoint_in_env(
                    endpoint_name=name,
                    new_url=data["base_url"],
                    new_key=data["api_key"],
                    new_model=data["model_name"],
                )
                # 如果当前正在使用该端点，重新切换刷新
                if self.provider_selector.currentText() == name:
                    self.engine.llm.switch_to_remote(name)
                    self._refresh_model_list()
                # 刷新下拉框
                self._init_provider_selector()
                # 恢复选中项
                for i in range(self.provider_selector.count()):
                    if self.provider_selector.itemText(i) == name:
                        self.provider_selector.setCurrentIndex(i)
                        break
                self.status_bar.showMessage(f"已更新远程模型: {name}")
            except Exception as e:
                QMessageBox.warning(self, "保存失败", f"更新 .env 文件失败:\n{e}")
                self._init_provider_selector()
                self.provider_selector.setCurrentIndex(prev_index)

    def _refresh_model_list(self):
        """刷新当前 provider 的模型列表"""
        try:
            models = self.engine.llm.get_available_models()
            current = self.engine.llm.model_name

            self._model_selector_updating = True
            self.model_selector.blockSignals(True)
            self.model_selector.clear()
            self.model_selector.addItems(models)

            idx = self.model_selector.findText(current)
            if idx >= 0:
                self.model_selector.setCurrentIndex(idx)
            else:
                self.model_selector.setEditText(current)

            self.model_selector.blockSignals(False)
            self._model_selector_updating = False

            if not models:
                name = self.engine.llm.current_endpoint_name
                self.status_bar.showMessage(f"{name} 无可用模型 — 请检查服务是否启动")
        except Exception as e:
            self._model_selector_updating = False
            name = self.engine.llm.current_endpoint_name
            self.status_bar.showMessage(f"获取 {name} 模型列表失败: {e}")

    def _do_check_ai_async(self):
        """后台线程检查当前 AI Provider，不阻塞 UI"""
        # 停止旧的检查 worker
        if self._ai_check_worker is not None and self._ai_check_worker.isRunning():
            self._ai_check_worker.result.disconnect(self._on_ai_check_done)
            self._ai_check_worker.quit()
            self._ai_check_worker.wait(500)

        # 记录发起检查时的 provider，避免结果覆盖用户已切换的 provider
        self._check_target = self.engine.llm.current_endpoint_name
        self._ai_check_worker = _AICheckWorker(self.engine.llm)
        self._ai_check_worker.result.connect(self._on_ai_check_done)
        self._ai_check_worker.start()

    def _on_ai_check_done(self, available: bool, models: list):
        """AI Provider 检查完成回调（仅当 provider 未切换时应用结果）"""
        current = self.engine.llm.current_endpoint_name
        # 如果用户在检查期间切换了 provider，忽略此结果
        if hasattr(self, '_check_target') and self._check_target != current:
            return
        if available:
            self._set_dot_status(self.ollama_dot, self.ollama_status_label, True, f"AI Ready ({current})")
            self._init_model_selector_with(models)
        else:
            self._set_dot_status(self.ollama_dot, self.ollama_status_label, False, f"AI offline ({current})")

    def _init_model_selector_with(self, models: list):
        """用已有模型列表初始化模型选择器"""
        try:
            current = self.engine.llm.model_name

            self._model_selector_updating = True
            self.model_selector.blockSignals(True)
            self.model_selector.clear()
            self.model_selector.addItems(models)

            idx = self.model_selector.findText(current)
            if idx >= 0:
                self.model_selector.setCurrentIndex(idx)
            else:
                self.model_selector.setEditText(current)

            self.model_selector.blockSignals(False)
            self._model_selector_updating = False
        except Exception:
            self._model_selector_updating = False

    def _on_model_changed(self, model_name: str):
        """模型切换回调（仅用户手动切换时触发）"""
        if not model_name or self._model_selector_updating:
            return
        self.engine.llm.set_model(model_name)
        self.engine.llm.reset_availability()
        name = self.engine.llm.current_endpoint_name
        self.status_bar.showMessage(f"已切换模型: [{name}] {model_name} — 下次诊断时生效")

    # ── Vehicle Selector ──

    def _load_vehicle_data(self):
        """加载车型数据到品牌/车型下拉框"""
        try:
            makes = self.engine.kb.get_vehicle_makes()
            self.make_selector.clear()
            self.make_selector.addItems(makes)
        except Exception:
            pass

    def _on_make_changed(self, make: str):
        """品牌切换时更新车型列表"""
        self.model_selector_vehicle.clear()
        self.model_selector_vehicle.setEditText("")
        if not make:
            return
        try:
            models = self.engine.kb.get_models_by_make(make)
            model_names = [m["model"] for m in models]
            self.model_selector_vehicle.addItems(model_names)
        except Exception:
            pass

    def _get_vehicle_info(self) -> str:
        """获取当前选择的车型信息文本"""
        make = self.make_selector.currentText().strip()
        model = self.model_selector_vehicle.currentText().strip()
        if make and model:
            return f"{make} {model}"
        elif model:
            return model
        return ""

    # ── Diagnosis ──

    def on_diagnose(self):
        from src.engine.diagnostic import parse_fault_codes

        input_text = self.code_input.text().strip()
        if not input_text:
            QMessageBox.warning(self, "提示", "请输入故障码")
            return

        # 解析故障码
        codes = parse_fault_codes(input_text)
        if not codes:
            QMessageBox.warning(self, "提示", "未识别到有效的故障码格式\n\n支持格式: P0300, P0171 P0420")
            return

        # 单码走原流程，多码走新流程
        if len(codes) == 1:
            self._diagnose_single(codes[0])
        else:
            self._diagnose_multiple(codes)

    def _diagnose_single(self, code: str):
        """单故障码诊断流程"""
        self.search_btn.setEnabled(False)
        self.search_btn.setText("诊断中...")
        self.status_bar.showMessage(f"正在诊断 {code}...")

        self.result_panel.clear()

        # 断开旧 worker 信号，防止泄漏
        if self.worker is not None:
            try:
                self.worker.kb_ready.disconnect(self._on_kb_ready)
                self.worker.ai_token.disconnect(self._on_ai_token)
                self.worker.ai_finished.disconnect(self._on_ai_finished)
                self.worker.finished.disconnect(self._on_diagnose_finished)
                self.worker.error.disconnect(self._on_diagnose_error)
            except TypeError:
                pass
            if self.worker.isRunning():
                self.worker.quit()
                if not self.worker.wait(1000):
                    self.worker.terminate()
                    self.worker.wait(500)

        self.worker = DiagnoseWorker(
            engine=self.engine,
            code=code,
            vehicle=self._get_vehicle_info(),
            extra=self.symptom_input.text().strip()
        )
        self.worker.kb_ready.connect(self._on_kb_ready)
        self.worker.ai_token.connect(self._on_ai_token)
        self.worker.ai_finished.connect(self._on_ai_finished)
        self.worker.finished.connect(self._on_diagnose_finished)
        self.worker.error.connect(self._on_diagnose_error)
        self.worker.start()

    def _diagnose_multiple(self, codes: list):
        """多故障码诊断流程"""
        codes_str = ", ".join(codes)
        self.search_btn.setEnabled(False)
        self.search_btn.setText("诊断中...")
        self.status_bar.showMessage(f"正在分析 {len(codes)} 个故障码: {codes_str}...")

        self.result_panel.clear()

        # 停止旧 worker（安全方式，兼容不同类型的 worker）
        if self.worker is not None:
            # 尝试断开所有可能的信号
            for signal_name in ['kb_ready', 'ai_token', 'ai_finished', 'finished', 'error', 'progress']:
                signal = getattr(self.worker, signal_name, None)
                if signal:
                    try:
                        signal.disconnect()
                    except TypeError:
                        pass
            if self.worker.isRunning():
                self.worker.quit()
                if not self.worker.wait(1000):
                    self.worker.terminate()
                    self.worker.wait(500)

        self.worker = MultiDiagnoseWorker(
            engine=self.engine,
            codes=codes,
            vehicle=self._get_vehicle_info(),
            extra=self.symptom_input.text().strip()
        )
        self.worker.progress.connect(self._on_multi_progress)
        self.worker.finished.connect(self._on_multi_diagnose_finished)
        self.worker.error.connect(self._on_diagnose_error)
        self.worker.start()

    def _on_kb_ready(self, result: DiagnosticResult):
        """知识库查询完成，立即展示"""
        self.search_btn.setEnabled(True)
        self.search_btn.setText("诊断")
        self.status_bar.showMessage(f"知识库查询完成 — AI 诊断建议生成中...")

        self.result_panel.show_kb_result(result)

        if result.has_knowledge():
            self.tab_widget.setCurrentIndex(0)

    def _on_related_code_clicked(self, code: str):
        """相关故障码点击，清理 worker + 延迟查询"""
        if self.worker is not None:
            try:
                self.worker.kb_ready.disconnect(self._on_kb_ready)
                self.worker.ai_token.disconnect(self._on_ai_token)
                self.worker.ai_finished.disconnect(self._on_ai_finished)
                self.worker.finished.disconnect(self._on_diagnose_finished)
                self.worker.error.disconnect(self._on_diagnose_error)
            except TypeError:
                pass
            if self.worker.isRunning():
                self.worker.quit()
                self.worker.wait(500)

        # 恢复按钮状态
        self.search_btn.setEnabled(True)
        self.search_btn.setText("诊断")

        self.code_input.setText(code)
        self.status_bar.showMessage(f"正在查询相关故障码 {code}...")
        QTimer.singleShot(0, lambda: self._do_related_code_lookup(code))

    def _do_related_code_lookup(self, code: str):
        """实际执行相关码查询（延迟到 Qt 完成点击处理后）

        注意：SQLite 单条索引查询 <1ms，在主线程执行可接受。
        已通过 QTimer.singleShot(0, ...) 延迟到事件循环执行。
        """
        knowledge = self.engine.kb.lookup(code)
        if knowledge:
            result = DiagnosticResult(
                code=code,
                knowledge=knowledge,
                ai_suggestion=None,
                ai_available=self.engine.llm.is_available()
            )
            self.result_panel.show_lookup_result(result)
            self.tab_widget.setCurrentIndex(0)
            self.status_bar.showMessage(f"已跳转至 {code}")
        else:
            self.status_bar.showMessage(f"未找到故障码 {code} 的信息")

    def _on_ai_token(self, token: str):
        """收到 AI 流式 token"""
        self.result_panel.append_ai_text(token)

    def _on_ai_finished(self, full_text: str):
        """AI 流式完成，重新格式化显示"""
        if full_text:
            code = self.code_input.text().strip().upper()
            self.result_panel.finalize_ai_suggestion(code, full_text)
        self.status_bar.showMessage("诊断完成 — AI 建议已生成")

    def _on_diagnose_finished(self, result: DiagnosticResult):
        """诊断全部完成（保存历史、同步 Agent）"""
        self._save_diagnosis_history(result)

        if result.has_ai() or result.has_knowledge():
            self.agent_panel.sync_diagnosis(result)

    def _save_diagnosis_history(self, result: DiagnosticResult):
        """保存诊断记录到历史"""
        try:
            vehicle = self._get_vehicle_info()
            symptom = self.symptom_input.text().strip()
            self.engine.kb.db.save_history(
                code=result.code,
                vehicle_info=vehicle,
                symptoms=symptom,
                knowledge_found=result.has_knowledge(),
                ai_suggestion=result.ai_suggestion or ""
            )
            self.history_panel.refresh()
        except Exception as e:
            self.status_bar.showMessage(f"保存历史记录失败: {e}")

    def _on_diagnose_error(self, error_msg: str):
        self.search_btn.setEnabled(True)
        self.search_btn.setText("诊断")
        self.status_bar.showMessage(f"诊断异常: {error_msg}")

    def _on_multi_progress(self, msg: str):
        """多故障码诊断进度更新"""
        self.status_bar.showMessage(msg)

    def _on_multi_diagnose_finished(self, result):
        """多故障码诊断完成"""
        self.search_btn.setEnabled(True)
        self.search_btn.setText("诊断")
        self.status_bar.showMessage(f"多故障码分析完成 — {len(result.codes)} 个故障码")

        # 显示综合结果
        self.result_panel.show_multi_code_result(result)
        self.tab_widget.setCurrentIndex(0)

        # 保存历史记录
        self._save_multi_diagnosis_history(result)

    def _save_multi_diagnosis_history(self, result):
        """保存多故障码诊断记录到历史"""
        try:
            vehicle = self._get_vehicle_info()
            symptom = self.symptom_input.text().strip()

            # 保存整体记录
            codes_str = ", ".join(result.codes)
            self.engine.kb.db.save_history(
                code=codes_str,
                vehicle_info=vehicle,
                symptoms=symptom,
                knowledge_found=result.has_knowledge(),
                ai_suggestion=result.ai_suggestion or ""
            )

            # 保存每个单独记录
            for r in result.results:
                self.engine.kb.db.save_history(
                    code=r.code,
                    vehicle_info=vehicle,
                    symptoms=f"[多码分析] {symptom}" if symptom else "[多码分析]",
                    knowledge_found=r.has_knowledge(),
                    ai_suggestion=""
                )

            self.history_panel.refresh()
        except Exception as e:
            self.status_bar.showMessage(f"保存历史记录失败: {e}")

    def _export_current_result(self):
        """导出当前诊断结果"""
        from PyQt6.QtWidgets import QFileDialog
        from src.ui.export_utils import export_as_text, export_as_html

        result = self.result_panel.get_current_result()
        if not result:
            QMessageBox.warning(self, "导出", "没有可导出的诊断结果")
            return

        vehicle = self._get_vehicle_info()
        symptom = self.symptom_input.text().strip()

        # 默认文件名
        default_name = f"诊断报告_{result.code}_{result.timestamp.replace(':', '-').replace(' ', '_')}"

        # 文件保存对话框
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "导出诊断报告",
            default_name,
            "文本文件 (*.txt);;HTML 文件 (*.html)"
        )
        if not file_path:
            return

        try:
            if file_path.endswith(".html"):
                content = export_as_html(
                    code=result.code,
                    knowledge=result.knowledge,
                    ai_suggestion=result.ai_suggestion,
                    vehicle_info=vehicle,
                    symptoms=symptom,
                    timestamp=result.timestamp,
                )
            else:
                if not file_path.endswith(".txt"):
                    file_path += ".txt"
                content = export_as_text(
                    code=result.code,
                    knowledge=result.knowledge,
                    ai_suggestion=result.ai_suggestion,
                    vehicle_info=vehicle,
                    symptoms=symptom,
                    timestamp=result.timestamp,
                )

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            self.status_bar.showMessage(f"诊断报告已导出: {file_path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"导出诊断报告失败:\n{e}")

    def _export_history_record(self, record: dict):
        """导出历史记录的诊断报告"""
        from PyQt6.QtWidgets import QFileDialog
        from src.ui.export_utils import export_as_text, export_as_html

        code = record.get("code", "")
        if not code:
            return

        # 重新查询知识库获取完整数据
        knowledge = self.engine.kb.lookup(code)

        vehicle_info = record.get("vehicle_info", "")
        symptoms = record.get("symptoms", "")
        ai_suggestion = record.get("ai_suggestion", "")
        timestamp = record.get("created_at", "")

        default_name = f"诊断报告_{code}_{timestamp.replace(':', '-').replace(' ', '_')[:15]}"

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "导出诊断报告",
            default_name,
            "文本文件 (*.txt);;HTML 文件 (*.html)"
        )
        if not file_path:
            return

        try:
            if file_path.endswith(".html"):
                content = export_as_html(
                    code=code, knowledge=knowledge,
                    ai_suggestion=ai_suggestion or None,
                    vehicle_info=vehicle_info, symptoms=symptoms,
                    timestamp=timestamp,
                )
            else:
                if not file_path.endswith(".txt"):
                    file_path += ".txt"
                content = export_as_text(
                    code=code, knowledge=knowledge,
                    ai_suggestion=ai_suggestion or None,
                    vehicle_info=vehicle_info, symptoms=symptoms,
                    timestamp=timestamp,
                )

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            self.status_bar.showMessage(f"诊断报告已导出: {file_path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"导出诊断报告失败:\n{e}")

    # ── Theme Methods ──

    def _update_theme_btn_icon(self):
        """更新主题切换按钮图标"""
        from src.ui.styles import is_dark
        self.theme_btn.setText("☀️" if is_dark() else "🌙")

    def _on_toggle_theme(self):
        """切换深色/浅色模式"""
        from src.ui.styles import toggle_theme
        new_theme = toggle_theme()
        self._update_theme_btn_icon()
        self._apply_theme()
        self.status_bar.showMessage(f"已切换到{'深色' if new_theme == 'dark' else '浅色'}模式")

    def _apply_theme(self):
        """应用当前主题样式 — 使用 get_token() 动态获取值"""
        from src.ui.styles import get_token, FONT_MONO

        BG = get_token("BG")
        CARD_BG = get_token("CARD_BG")
        CARD_BORDER = get_token("CARD_BORDER")
        TEXT_PRIMARY = get_token("TEXT_PRIMARY")
        TEXT_SECONDARY = get_token("TEXT_SECONDARY")
        TEXT_MUTED = get_token("TEXT_MUTED")
        PRIMARY = get_token("PRIMARY")
        PRIMARY_DARK = get_token("PRIMARY_DARK")
        PRIMARY_BG = get_token("PRIMARY_BG")
        INPUT_BG = get_token("INPUT_BG")
        INPUT_BORDER = get_token("INPUT_BORDER")
        INPUT_FOCUS = get_token("INPUT_FOCUS")

        # 主窗口背景
        self.setStyleSheet(f"QMainWindow {{ background-color: {BG}; }}")

        # 品牌栏
        self.brand.setStyleSheet(f"background-color: {PRIMARY_DARK};")

        # 搜索卡片
        self.search_card.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 12px;
            }}
        """)
        self.search_title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT_PRIMARY};")

        # 代码输入框
        self.code_input.setStyleSheet(f"""
            QLineEdit {{
                font-size: 16px; padding: 8px 14px; font-family: "{FONT_MONO}";
                border: 2px solid {INPUT_BORDER}; border-radius: 10px;
                background: {INPUT_BG}; min-height: 26px; color: {TEXT_PRIMARY};
            }}
            QLineEdit:focus {{ border-color: {INPUT_FOCUS}; }}
        """)

        # 搜索按钮
        self.search_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 15px; font-weight: bold;
                background-color: {PRIMARY}; color: white;
                border: none; border-radius: 10px;
                padding: 4px 32px;
            }}
            QPushButton:hover {{ background-color: {PRIMARY_DARK}; }}
            QPushButton:disabled {{ background-color: #90CAF9; }}
        """)

        # 车型选择器
        combo_style = f"""
            QComboBox {{
                font-size: 13px; padding: 6px 10px;
                border: 1px solid {INPUT_BORDER}; border-radius: 8px;
                background: {INPUT_BG}; min-height: 22px; color: {TEXT_PRIMARY};
            }}
            QComboBox:focus {{ border-color: {INPUT_FOCUS}; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox QAbstractItemView {{
                background-color: {CARD_BG}; color: {TEXT_PRIMARY};
                border: 1px solid {CARD_BORDER}; selection-background-color: {PRIMARY_BG};
            }}
        """
        self.make_selector.setStyleSheet(combo_style)
        self.model_selector_vehicle.setStyleSheet(combo_style)

        # 症状输入框
        self.symptom_input.setStyleSheet(f"""
            QLineEdit {{
                font-size: 13px; padding: 6px 10px;
                border: 1px solid {INPUT_BORDER}; border-radius: 8px;
                background: {INPUT_BG}; min-height: 22px; color: {TEXT_PRIMARY};
            }}
            QLineEdit:focus {{ border-color: {INPUT_FOCUS}; }}
        """)

        # Tab 组件
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {CARD_BORDER};
                border-radius: 4px;
                background-color: {CARD_BG};
            }}
            QTabBar::tab {{
                padding: 10px 20px; font-size: 13px;
                border: 1px solid transparent;
                border-bottom: none; color: {TEXT_SECONDARY};
            }}
            QTabBar::tab:selected {{
                background-color: {CARD_BG};
                border-color: {CARD_BORDER};
                border-bottom: 2px solid {PRIMARY};
                color: {PRIMARY}; font-weight: bold;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {PRIMARY_BG};
            }}
        """)

        # 状态栏
        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                background-color: {CARD_BG};
                border-top: 1px solid {CARD_BORDER};
                font-size: 11px; color: {TEXT_MUTED}; padding: 2px 16px;
            }}
        """)

        # 子面板刷新
        if hasattr(self, 'result_panel'):
            self.result_panel.refresh_theme()
        if hasattr(self, 'agent_panel'):
            self.agent_panel.refresh_theme()
        if hasattr(self, 'history_panel'):
            self.history_panel.refresh_theme()
