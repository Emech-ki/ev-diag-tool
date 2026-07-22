"""
Main Window — v1.0.0 Original Layout
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QStatusBar, QMessageBox,
    QTabWidget, QFrame
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from src.engine.diagnostic import DiagnosticEngine, DiagnosticResult
from src.ui.result_panel import ResultPanel
from src.ui.agent_chat import AgentChatPanel
from src.ui.styles import (
    PRIMARY, PRIMARY_DARK, PRIMARY_BG,
    BG, CARD_BG, CARD_BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, FONT_MONO,
    SUCCESS, SUCCESS_BG, WARNING, WARNING_BG
)

from src.version import VERSION_LINE


class DiagnoseWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, engine: DiagnosticEngine, code: str, vehicle: str = "", extra: str = ""):
        super().__init__()
        self.engine = engine
        self.code = code
        self.vehicle = vehicle
        self.extra = extra

    def run(self):
        try:
            result = self.engine.diagnose(code=self.code, vehicle_info=self.vehicle, additional_info=self.extra)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.engine = DiagnosticEngine()
        self.worker = None
        self._init_ui()
        self._check_database()
        self._check_ollama()

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

        main_layout.addWidget(brand)

        # ── Content ──
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(28, 20, 28, 20)

        # ── Search Card ──
        search_card = QFrame()
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

        self.vehicle_input = QLineEdit()
        self.vehicle_input.setPlaceholderText("车型（如：比亚迪秦PLUS EV 2023）")
        self.vehicle_input.setStyleSheet(f"""
            QLineEdit {{
                font-size: 13px; padding: 6px 10px;
                border: 1px solid {CARD_BORDER}; border-radius: 8px;
                background: white; min-height: 22px;
            }}
            QLineEdit:focus {{ border-color: {PRIMARY}; }}
        """)
        extra_row.addWidget(self.vehicle_input, 1)

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
        self.tab_widget.addTab(self.result_panel, "诊断结果")

        self.agent_panel = AgentChatPanel(self.engine)
        self.tab_widget.addTab(self.agent_panel, "AI 助手")

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

    def _check_ollama(self):
        QTimer.singleShot(500, self._do_check_ollama)

    def _do_check_ollama(self):
        try:
            llm = self.engine.llm
            if llm.is_available():
                self._set_dot_status(self.ollama_dot, self.ollama_status_label, True, "AI Ready")
            else:
                self._set_dot_status(self.ollama_dot, self.ollama_status_label, False, "AI offline")
        except Exception:
            self._set_dot_status(self.ollama_dot, self.ollama_status_label, False, "AI offline")

    # ── Diagnosis ──

    def on_diagnose(self):
        code = self.code_input.text().strip()
        if not code:
            QMessageBox.warning(self, "提示", "请输入故障码")
            return

        self.search_btn.setEnabled(False)
        self.search_btn.setText("诊断中...")
        self.status_bar.showMessage(f"正在诊断 {code}...")

        self.result_panel.clear()

        self.worker = DiagnoseWorker(
            engine=self.engine,
            code=code,
            vehicle=self.vehicle_input.text().strip(),
            extra=self.symptom_input.text().strip()
        )
        self.worker.finished.connect(self._on_diagnose_finished)
        self.worker.error.connect(self._on_diagnose_error)
        self.worker.start()

    def _on_diagnose_finished(self, result: DiagnosticResult):
        self.search_btn.setEnabled(True)
        self.search_btn.setText("诊断")
        self.status_bar.showMessage(f"诊断完成: {result.code}")

        self.result_panel.show_result(result)

        if result.has_ai() or result.has_knowledge():
            self.agent_panel.sync_diagnosis(result)

        if result.has_knowledge():
            self.tab_widget.setCurrentIndex(0)

    def _on_diagnose_error(self, error_msg: str):
        self.search_btn.setEnabled(True)
        self.search_btn.setText("诊断")
        self.status_bar.showMessage("诊断失败")
        QMessageBox.critical(self, "诊断错误", f"错误信息:\n{error_msg}")
