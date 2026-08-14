"""
三电诊断面板
电池/电机/电控 三大子系统的诊断界面：
概览 + 向导（症状引导）+ 故障码多码诊断（内嵌 ResultPanel 展示）
"""

import html
from typing import Optional, Dict, Any, List

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QStackedWidget, QTextBrowser, QButtonGroup,
    QMessageBox, QScrollArea, QTabWidget
)

from src.engine.diagnostic import DiagnosticEngine, MultiCodeDiagnosticResult
from src.engine import three_electric
from src.ui.result_panel import ResultPanel
from src.ui.styles import (
    PRIMARY, PRIMARY_DARK, PRIMARY_BG,
    BG, CARD_BG, CARD_BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)


class ThreeElectricDiagnoseWorker(QThread):
    """三电多码诊断工作线程（候选码 → MultiCodeDiagnosticResult）"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, engine: DiagnosticEngine, codes: list, symptom_context: str = "",
                 priority_codes: Optional[list] = None,
                 priority_weights: Optional[dict] = None):
        super().__init__()
        self.engine = engine
        self.codes = codes
        self.symptom_context = symptom_context
        self.priority_codes = list(priority_codes or [])
        self.priority_weights = dict(priority_weights or {})

    def run(self):
        try:
            self.progress.emit(f"正在分析 {len(self.codes)} 个故障码...")
            result = self.engine.diagnose_multiple(
                codes=self.codes,
                additional_info=self.symptom_context,
                priority_codes=self.priority_codes,
                priority_weights=self.priority_weights,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class _ChipBrowser(QTextBrowser):
    """支持 dtc:// 链接点击的文本浏览器（拦截该 scheme 防止跳转）"""

    def setSource(self, url):
        if url.scheme() == "dtc":
            return
        super().setSource(url)


class ElectricSystemPage(QWidget):
    """单个三电子系统的诊断页：概览 + 向导 + 结果"""

    _RESULT_TAB_INDEX = 2  # 内嵌 Tab 中「诊断结果」的索引

    def __init__(self, engine: DiagnosticEngine, subsystem: str, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.subsystem = subsystem
        self.worker: Optional[ThreeElectricDiagnoseWorker] = None
        self._guide = three_electric.get_guide_for(subsystem)
        self._current_group: Optional[dict] = None
        self._current_option: Optional[dict] = None
        self._overview = three_electric.build_overview(engine.kb, subsystem)
        self._init_ui()
        self._reset_wizard()

    # ── UI 构建 ──

    def _init_ui(self):
        # 页面级滚动：窗口过小时内部内容不被压缩，改用滚轮滚动整页
        self._page_scroll = QScrollArea()
        self._page_scroll.setWidgetResizable(True)
        self._page_scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        self._page_content = QWidget()
        self._page_content.setStyleSheet(f"background-color: {CARD_BG};")
        self._page_scroll.setWidget(self._page_content)

        outer = QVBoxLayout(self._page_content)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        # ── 头部条：icon + 名称 + 统计 ──
        self._header = QFrame()
        self._header.setStyleSheet(f"background-color: {CARD_BG}; border: 1px solid {CARD_BORDER}; border-radius: 10px;")
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(16, 12, 16, 12)

        self._icon_label = QLabel(self._overview.get("icon", "❓"))
        self._icon_label.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(self._icon_label)

        self._name_label = QLabel(self._overview.get("name", self.subsystem))
        self._name_label.setStyleSheet(f"font-size: 17px; font-weight: bold; color: {TEXT_PRIMARY};")
        header_layout.addWidget(self._name_label)

        self._stats_label = QLabel()
        self._stats_label.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY}; margin-left: 12px;")
        header_layout.addWidget(self._stats_label)
        header_layout.addStretch()
        outer.addWidget(self._header)

        # ── 使用引导横幅 ──
        self._guide_banner = QFrame()
        self._guide_banner.setStyleSheet(f"background-color: {PRIMARY_BG}; border: 1px solid {PRIMARY}; border-radius: 10px;")
        banner_layout = QHBoxLayout(self._guide_banner)
        banner_layout.setContentsMargins(16, 10, 16, 10)
        banner_layout.setSpacing(8)

        self._guide_banner_icon = QLabel("🧭")
        self._guide_banner_icon.setStyleSheet("font-size: 18px;")
        banner_layout.addWidget(self._guide_banner_icon)

        self._guide_banner_text = QLabel(
            "使用方法：① 选择故障现象 → ② 选择具体表现 → ③ 点击「开始诊断」，结果自动显示在「诊断结果」页"
        )
        self._guide_banner_text.setWordWrap(True)
        self._guide_banner_text.setStyleSheet(f"font-size: 12px; color: {PRIMARY};")
        banner_layout.addWidget(self._guide_banner_text, 1)
        outer.addWidget(self._guide_banner)

        # ── 内嵌 Tab：快速排查 / 系统概览 / 诊断结果 ──
        self._inner_tabs = QTabWidget()
        self._inner_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {CARD_BORDER};
                border-radius: 4px;
                background-color: {CARD_BG};
            }}
            QTabBar::tab {{
                padding: 8px 16px; font-size: 13px;
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
        outer.addWidget(self._inner_tabs, 1)
        self._inner_tabs.setMinimumHeight(460)

        # ── Tab 1：快速排查（向导） ──
        self._wizard_page = QWidget()
        self._wizard_page.setStyleSheet(f"background-color: {CARD_BG};")
        wizard_layout = QVBoxLayout(self._wizard_page)
        wizard_layout.setContentsMargins(16, 16, 16, 16)
        wizard_layout.setSpacing(10)

        self._step_label = QLabel()
        self._step_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {PRIMARY};")
        wizard_layout.addWidget(self._step_label)

        self._wizard_hint = QLabel()
        self._wizard_hint.setWordWrap(True)
        self._wizard_hint.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED};")
        wizard_layout.addWidget(self._wizard_hint)

        self._wizard_body = QWidget()
        self._wizard_body_layout = QVBoxLayout(self._wizard_body)
        self._wizard_body_layout.setContentsMargins(0, 0, 0, 0)
        self._wizard_body_layout.setSpacing(6)
        wizard_layout.addWidget(self._wizard_body)

        self._inner_tabs.addTab(self._wizard_page, "快速排查")

        # ── Tab 2：系统概览 ──
        self._overview_page = QWidget()
        self._overview_page.setStyleSheet(f"background-color: {CARD_BG};")
        ov_layout = QVBoxLayout(self._overview_page)
        ov_layout.setContentsMargins(0, 0, 0, 0)

        self._overview_scroll = QScrollArea()
        self._overview_scroll.setWidgetResizable(True)
        self._overview_scroll.setStyleSheet(f"""
            QScrollArea {{ background-color: transparent; border: none; }}
        """)
        ov_container = QWidget()
        ov_scroll_layout = QVBoxLayout(ov_container)
        ov_scroll_layout.setContentsMargins(16, 16, 16, 16)
        ov_scroll_layout.setSpacing(12)

        self._overview_card = QFrame()
        self._overview_card.setStyleSheet(f"background-color: {CARD_BG}; border: 1px solid {CARD_BORDER}; border-radius: 10px;")
        ov_card_layout = QVBoxLayout(self._overview_card)
        ov_card_layout.setContentsMargins(16, 12, 16, 12)
        ov_card_layout.setSpacing(8)

        ov_title = QLabel("系统覆盖概览")
        ov_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {TEXT_PRIMARY};")
        ov_card_layout.addWidget(ov_title)

        self._coverage_label = QLabel()
        self._coverage_label.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY}; line-height: 1.7;")
        self._coverage_label.setWordWrap(True)
        ov_card_layout.addWidget(self._coverage_label)

        common_title = QLabel("常见故障码（点击可诊断）")
        common_title.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED}; margin-top: 4px;")
        ov_card_layout.addWidget(common_title)

        self._common_browser = _ChipBrowser()
        self._common_browser.setOpenExternalLinks(False)
        self._common_browser.setMinimumHeight(52)
        self._common_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: transparent; border: none;
                font-size: 12px; color: {TEXT_PRIMARY};
            }}
        """)
        self._common_browser.anchorClicked.connect(self._on_common_clicked)
        ov_card_layout.addWidget(self._common_browser)

        ov_scroll_layout.addWidget(self._overview_card)
        ov_scroll_layout.addStretch()
        self._overview_scroll.setWidget(ov_container)
        ov_layout.addWidget(self._overview_scroll)
        self._inner_tabs.addTab(self._overview_page, "系统概览")

        # ── Tab 3：诊断结果（内嵌 ResultPanel，全高） ──
        self._result_page = QWidget()
        self._result_page.setStyleSheet(f"background-color: {CARD_BG};")
        result_layout = QVBoxLayout(self._result_page)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_layout.setSpacing(0)

        self.result_panel = ResultPanel()
        self.result_panel.diagnose_requested.connect(self._on_related_code_clicked)
        self.result_panel.export_requested.connect(self._on_export)
        result_layout.addWidget(self.result_panel, 1)
        self._inner_tabs.addTab(self._result_page, "诊断结果")

        self._render_overview()
        self._render_stats()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._page_scroll)

    # ── 概览渲染 ──

    def _render_stats(self):
        ov = self._overview
        self._stats_label.setText(
            f"共 {ov['total_codes']} 条故障码 · 有详情 {ov['codes_with_detail']} 条"
        )

    def _render_overview(self):
        c = self._get_colors()
        ov = self._overview

        lines = []
        for r in ov.get("systems", []):
            total = r.get("total", 0)
            with_detail = r.get("with_detail", 0)
            sev = [r.get("sev_low", 0), r.get("sev_medium", 0), r.get("sev_high", 0), r.get("sev_critical", 0)]
            lines.append(
                f"<b>{html.escape(r.get('system', ''))}</b> — {total} 条"
                f"（有详情 {with_detail} · 低{sev[0]} 中{sev[1]} 高{sev[2]} 严重{sev[3]}）"
            )
        if lines:
            self._coverage_label.setText("<br>".join(lines))
        else:
            self._coverage_label.setText("暂无覆盖数据")

        common = ov.get("common_codes", [])
        if common:
            chips = " ".join(
                f'<a href="dtc://{html.escape(r["code"])}" style="text-decoration: none; '
                f'background-color: {c["PRIMARY_BG"]}; color: {c["PRIMARY"]}; '
                f'font-family: Consolas; font-size: 12px; padding: 2px 10px; border-radius: 4px; '
                f'margin-right: 6px;">{html.escape(r["code"])}</a>'
                for r in common
            )
            self._common_browser.setHtml(
                f'<div style="font-family: Microsoft YaHei UI, sans-serif;">{chips}</div>'
            )
        else:
            self._common_browser.clear()

    def _on_common_clicked(self, url):
        """点击概览中的常见故障码 → 单码诊断"""
        if url.scheme() == "dtc":
            code = url.host().upper() if url.host() else url.path().strip("/")
            if code:
                self._start_diagnosis([code])

    # ── 向导流程 ──

    def _clear_wizard_body(self):
        while self._wizard_body_layout.count():
            item = self._wizard_body_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _reset_wizard(self):
        """回到第 1 步：选择故障现象"""
        self._current_group = None
        self._current_option = None
        self._step_label.setText("步骤 1/3：请选择故障现象")
        self._wizard_hint.setText("请选择一个故障现象，向导将引导你定位可能的故障码。")
        self._clear_wizard_body()

        groups = self._guide.get("symptom_groups", [])
        if not groups:
            tip = QLabel("该子系统暂无向导数据")
            tip.setStyleSheet(f"font-size: 12px; color: {self._get_colors()['TEXT_MUTED']};")
            self._wizard_body_layout.addWidget(tip)
            return

        for group in groups:
            btn = QPushButton(group.get("label", group.get("id", "未知现象")))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._group_btn_style())
            btn.clicked.connect(lambda checked=False, g=group: self._show_group(g))
            self._wizard_body_layout.addWidget(btn)

    def _show_group(self, group: dict):
        """第 2 步：显示该现象的具体问题"""
        self._current_group = group
        self._current_option = None
        self._step_label.setText("步骤 2/3：请选择具体表现")
        self._wizard_hint.setText(group.get("question", ""))
        self._clear_wizard_body()

        options = group.get("options", [])
        for option in options:
            btn = QPushButton(option.get("label", "下一步"))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._option_btn_style())
            btn.clicked.connect(lambda checked=False, o=option: self._show_option(group, o))
            self._wizard_body_layout.addWidget(btn)

        self._add_back_button(self._reset_wizard)

    def _show_option(self, group: dict, option: dict):
        """第 3 步：展示候选故障码，确认后启动诊断"""
        self._current_group = group
        self._current_option = option
        hint = group.get("final_hint", "")
        self._step_label.setText("步骤 3/3：确认候选码并开始诊断")
        self._wizard_hint.setText(f"已选择：{option.get('label', '')}\n排查提示：{hint}")

        self._clear_wizard_body()

        codes = three_electric.get_option_codes(option)
        c = self._get_colors()
        chips = " ".join(
            f'<span style="font-family: Consolas; font-size: 12px; background-color: {c["PRIMARY_BG"]}; '
            f'color: {c["PRIMARY"]}; padding: 2px 10px; border-radius: 4px; margin-right: 6px;">{html.escape(code)}</span>'
            for code in codes
        )
        codes_label = QLabel(f"候选故障码：{chips}")
        codes_label.setTextFormat(Qt.TextFormat.RichText)
        codes_label.setWordWrap(True)
        codes_label.setStyleSheet(f"font-size: 13px; color: {c['TEXT_PRIMARY']};")
        self._wizard_body_layout.addWidget(codes_label)

        diagnose_btn = QPushButton("开始诊断")
        diagnose_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        diagnose_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 14px; font-weight: bold;
                background-color: {c['PRIMARY']}; color: white;
                border: none; border-radius: 8px;
                padding: 4px 24px; min-height: 34px;
            }}
            QPushButton:hover {{ background-color: {c['PRIMARY_DARK']}; }}
            QPushButton:disabled {{ background-color: #90CAF9; }}
        """)
        diagnose_btn.clicked.connect(lambda: self._start_diagnosis(codes))
        self._wizard_body_layout.addWidget(diagnose_btn)

        back_row = QHBoxLayout()
        back_btn = QPushButton("← 返回")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(self._back_btn_style())
        back_btn.clicked.connect(lambda: self._show_group(group))
        back_row.addWidget(back_btn)
        back_row.addStretch()
        self._wizard_body_layout.addLayout(back_row)

    def _add_back_button(self, slot):
        back_row = QHBoxLayout()
        back_btn = QPushButton("← 返回")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(self._back_btn_style())
        back_btn.clicked.connect(slot)
        back_row.addWidget(back_btn)
        back_row.addStretch()
        self._wizard_body_layout.addLayout(back_row)

    # ── 诊断流程 ──

    def _start_diagnosis(self, codes: list):
        """启动多码诊断 worker，并自动切换到「诊断结果」页"""
        if not codes:
            return
        self._stop_worker()
        self._set_busy(True)
        self._inner_tabs.setCurrentIndex(self._RESULT_TAB_INDEX)
        # 向导候选码显式置信度 weight：按 weight 降序即「高疑似」，
        # weight 作为语音块随 priority_weights 贯穿 worker → diagnose_multiple → AI 提示
        priority = three_electric.get_option_codes(self._current_option) if self._current_option else []
        weights = three_electric.get_option_weights(self._current_option) if self._current_option else {}
        self.worker = ThreeElectricDiagnoseWorker(
            self.engine, codes, self._build_symptom_context(),
            priority_codes=priority,
            priority_weights=weights,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_diagnose_finished)
        self.worker.error.connect(self._on_diagnose_error)
        self.worker.start()

    def _build_symptom_context(self) -> str:
        """拼装症状上下文（现象 → 具体表现 → 排查提示），供 AI 对症下药"""
        parts = [f"子系统：{self._overview.get('name', self.subsystem)}"]
        if self._current_group:
            parts.append(f"故障现象：{self._current_group.get('label', '')}")
            if self._current_option:
                parts.append(f"具体表现：{self._current_option.get('label', '')}")
            hint = self._current_group.get("final_hint", "")
            if hint:
                parts.append(f"排查提示：{hint}")
        return "\n".join(parts)

    def _on_progress(self, msg: str):
        self._wizard_hint.setText(msg)

    def _on_diagnose_finished(self, result: MultiCodeDiagnosticResult):
        self._set_busy(False)
        self.result_panel.show_multi_code_result(result)
        self._wizard_hint.setText(f"✅ 诊断完成，共分析 {len(result.codes)} 个候选故障码。")

    def _on_diagnose_error(self, error_msg: str):
        self._set_busy(False)
        QMessageBox.warning(self, "诊断失败", f"诊断过程出错：{error_msg}")
        self._wizard_hint.setText("诊断失败，请重试。")

    def _set_busy(self, busy: bool):
        self._wizard_body.setEnabled(not busy)
        if busy:
            self._wizard_hint.setText("⏳ 正在诊断，请稍候...")

    def _stop_worker(self):
        """安全停止当前 worker 线程"""
        if self.worker is not None:
            try:
                self.worker.progress.disconnect(self._on_progress)
                self.worker.finished.disconnect(self._on_diagnose_finished)
                self.worker.error.disconnect(self._on_diagnose_error)
            except TypeError:
                pass
            if self.worker.isRunning():
                self.worker.quit()
                if not self.worker.wait(5000):
                    self.worker.terminate()
                    self.worker.wait(1000)
            self.worker.deleteLater()
            self.worker = None

    def _on_related_code_clicked(self, code: str):
        """点击知识库中的相关故障码 → 单码诊断"""
        self._start_diagnosis([code])

    # ── 导出 ──

    def _on_export(self):
        """导出内嵌结果面板当前诊断结果"""
        from PyQt6.QtWidgets import QFileDialog
        from src.ui.export_utils import export_as_text, export_as_html, export_as_pdf, aggregate_multi_knowledge

        result = self.result_panel.get_current_result()
        if not result:
            QMessageBox.warning(self, "导出", "没有可导出的诊断结果")
            return

        if isinstance(result, MultiCodeDiagnosticResult):
            code = ", ".join(result.codes)
            knowledge = aggregate_multi_knowledge(result.results, code=code)
            ai_suggestion = result.ai_suggestion
            timestamp = result.timestamp
            symptoms = result.symptom_context
        else:
            code = result.code
            knowledge = result.knowledge
            ai_suggestion = result.ai_suggestion
            timestamp = result.timestamp
            symptoms = ""

        default_name = f"三电诊断报告_{code}_{timestamp.replace(':', '-').replace(' ', '_')}"

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "导出诊断报告",
            default_name,
            "PDF 文件 (*.pdf);;文本文件 (*.txt);;HTML 文件 (*.html)"
        )
        if not file_path:
            return

        try:
            is_pdf = "PDF" in selected_filter or file_path.lower().endswith(".pdf")
            is_html = "HTML" in selected_filter or file_path.lower().endswith(".html")
            if is_pdf:
                if not file_path.lower().endswith(".pdf"):
                    file_path += ".pdf"
                content = export_as_pdf(
                    code=code, knowledge=knowledge,
                    ai_suggestion=ai_suggestion,
                    vehicle_info=self._get_vehicle_info(),
                    symptoms=symptoms, timestamp=timestamp,
                )
                with open(file_path, "wb") as f:
                    f.write(content)
            elif is_html:
                if not file_path.lower().endswith(".html"):
                    file_path += ".html"
                content = export_as_html(
                    code=code, knowledge=knowledge,
                    ai_suggestion=ai_suggestion,
                    vehicle_info=self._get_vehicle_info(),
                    symptoms=symptoms, timestamp=timestamp,
                )
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
            else:
                if not file_path.lower().endswith(".txt"):
                    file_path += ".txt"
                content = export_as_text(
                    code=code, knowledge=knowledge,
                    ai_suggestion=ai_suggestion,
                    vehicle_info=self._get_vehicle_info(),
                    symptoms=symptoms, timestamp=timestamp,
                )
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
            QMessageBox.information(self, "导出成功", f"报告已保存至：\n{file_path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"导出过程出错：{e}")

    def _get_vehicle_info(self) -> str:
        return ""

    # ── 样式辅助 ──

    def _get_colors(self):
        from src.ui.theme_helper import get_theme_colors
        return get_theme_colors()

    def _group_btn_style(self) -> str:
        c = self._get_colors()
        return f"""
            QPushButton {{
                font-size: 13px; text-align: left; padding: 8px 12px;
                background-color: {c['CARD_BG']}; color: {c['TEXT_PRIMARY']};
                border: 1px solid {c['CARD_BORDER']}; border-radius: 6px;
            }}
            QPushButton:hover {{ background-color: {c['PRIMARY_BG']}; color: {c['PRIMARY']}; border-color: {c['PRIMARY']}; }}
        """

    def _option_btn_style(self) -> str:
        c = self._get_colors()
        return f"""
            QPushButton {{
                font-size: 13px; text-align: left; padding: 8px 12px;
                background-color: {c['INPUT_BG']}; color: {c['TEXT_PRIMARY']};
                border: 1px solid {c['INPUT_BORDER']}; border-radius: 6px;
            }}
            QPushButton:hover {{ background-color: {c['PRIMARY_BG']}; color: {c['PRIMARY']}; border-color: {c['PRIMARY']}; }}
        """

    def _back_btn_style(self) -> str:
        c = self._get_colors()
        return f"""
            QPushButton {{
                font-size: 12px; padding: 4px 14px;
                background-color: {c['CARD_BG']}; color: {c['TEXT_SECONDARY']};
                border: 1px solid {c['CARD_BORDER']}; border-radius: 6px;
            }}
            QPushButton:hover {{ background-color: {c['PRIMARY_BG']}; color: {c['PRIMARY']}; }}
        """

    def refresh_theme(self):
        """刷新主题样式"""
        c = self._get_colors()

        self._page_scroll.setStyleSheet(f"""
            QScrollArea {{ background-color: transparent; border: none; }}
        """)

        self._header.setStyleSheet(f"background-color: {c['CARD_BG']}; border: 1px solid {c['CARD_BORDER']}; border-radius: 10px;")
        self._name_label.setStyleSheet(f"font-size: 17px; font-weight: bold; color: {c['TEXT_PRIMARY']};")
        self._stats_label.setStyleSheet(f"font-size: 12px; color: {c['TEXT_SECONDARY']}; margin-left: 12px;")

        self._guide_banner.setStyleSheet(f"background-color: {c['PRIMARY_BG']}; border: 1px solid {c['PRIMARY']}; border-radius: 10px;")
        self._guide_banner_text.setStyleSheet(f"font-size: 12px; color: {c['PRIMARY']};")

        self._inner_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {c['CARD_BORDER']};
                border-radius: 4px;
                background-color: {c['CARD_BG']};
            }}
            QTabBar::tab {{
                padding: 8px 16px; font-size: 13px;
                border: 1px solid transparent;
                border-bottom: none; color: {c['TEXT_SECONDARY']};
            }}
            QTabBar::tab:selected {{
                background-color: {c['CARD_BG']};
                border-color: {c['CARD_BORDER']};
                border-bottom: 2px solid {c['PRIMARY']};
                color: {c['PRIMARY']}; font-weight: bold;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {c['PRIMARY_BG']};
            }}
        """)

        self._page_content.setStyleSheet(f"background-color: {c['CARD_BG']};")
        self._wizard_page.setStyleSheet(f"background-color: {c['CARD_BG']};")
        self._overview_page.setStyleSheet(f"background-color: {c['CARD_BG']};")
        self._result_page.setStyleSheet(f"background-color: {c['CARD_BG']};")

        self._step_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {c['PRIMARY']};")
        self._wizard_hint.setStyleSheet(f"font-size: 12px; color: {c['TEXT_MUTED']};")

        self._overview_scroll.setStyleSheet(f"""
            QScrollArea {{ background-color: transparent; border: none; }}
        """)
        self._overview_card.setStyleSheet(f"background-color: {c['CARD_BG']}; border: 1px solid {c['CARD_BORDER']}; border-radius: 10px;")
        self._coverage_label.setStyleSheet(f"font-size: 12px; color: {c['TEXT_SECONDARY']}; line-height: 1.7;")
        self._common_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: transparent; border: none;
                font-size: 12px; color: {c['TEXT_PRIMARY']};
            }}
        """)

        self.result_panel.refresh_theme()
        self._render_overview()

        # 重绘向导当前步骤，让动态创建的按钮/标签应用新主题
        self._clear_wizard_body()
        if self._current_option is not None and self._current_group is not None:
            self._show_option(self._current_group, self._current_option)
        elif self._current_group is not None:
            self._show_group(self._current_group)
        else:
            self._reset_wizard()
        self._wizard_body.setEnabled(self.worker is None or not self.worker.isRunning())


class ThreeElectricPanel(QWidget):
    """三电诊断主面板：顶部子系统切换 + 各子系统子页"""

    def __init__(self, engine: DiagnosticEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.pages: Dict[str, ElectricSystemPage] = {}
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        # 顶部子系统切换按钮
        self._subsystem_bar = QFrame()
        self._subsystem_bar.setStyleSheet(f"background-color: {CARD_BG}; border: 1px solid {CARD_BORDER}; border-radius: 10px;")
        bar_layout = QHBoxLayout(self._subsystem_bar)
        bar_layout.setContentsMargins(12, 10, 12, 10)
        bar_layout.setSpacing(8)

        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)

        for sub in three_electric.get_subsystems():
            btn = QPushButton(f"{sub['icon']}  {sub['name']}")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._sub_btn_style())
            self._btn_group.addButton(btn)
            bar_layout.addWidget(btn)
            page = ElectricSystemPage(self.engine, sub["key"])
            self.pages[sub["key"]] = page
            btn.clicked.connect(lambda checked=False, key=sub["key"]: self._switch_to(key))

        bar_layout.addStretch()
        outer.addWidget(self._subsystem_bar)

        # 子系统子页
        self._stack = QStackedWidget()
        for sub in three_electric.get_subsystems():
            self._stack.addWidget(self.pages[sub["key"]])
        outer.addWidget(self._stack, 1)

        first_btn = self._btn_group.buttons()[0] if self._btn_group.buttons() else None
        if first_btn:
            first_btn.setChecked(True)
        self._switch_to(three_electric.get_subsystems()[0]["key"])

    def _sub_btn_style(self) -> str:
        c = self._get_colors()
        return f"""
            QPushButton {{
                font-size: 13px; font-weight: bold; padding: 6px 18px;
                background-color: {c['CARD_BG']}; color: {c['TEXT_SECONDARY']};
                border: 1px solid {c['CARD_BORDER']}; border-radius: 8px;
            }}
            QPushButton:hover {{ background-color: {c['PRIMARY_BG']}; color: {c['PRIMARY']}; }}
            QPushButton:checked {{
                background-color: {c['PRIMARY']}; color: white; border-color: {c['PRIMARY']};
            }}
        """

    def _get_colors(self):
        from src.ui.theme_helper import get_theme_colors
        return get_theme_colors()

    def _switch_to(self, key: str):
        page = self.pages.get(key)
        if page is not None:
            self._stack.setCurrentWidget(page)

    def _stop_worker(self):
        """停止所有子页的 worker 线程（主窗口关闭时调用）"""
        for page in self.pages.values():
            page._stop_worker()

    def refresh_theme(self):
        """刷新主题样式"""
        c = self._get_colors()
        self._subsystem_bar.setStyleSheet(f"background-color: {c['CARD_BG']}; border: 1px solid {c['CARD_BORDER']}; border-radius: 10px;")
        for btn in self._btn_group.buttons():
            btn.setStyleSheet(self._sub_btn_style())
        for page in self.pages.values():
            page.refresh_theme()
