"""
诊断历史记录面板
显示历史诊断记录，支持搜索和清空
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QAbstractItemView, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from src.database.db_manager import DatabaseManager
from src.ui.styles import (
    PRIMARY, PRIMARY_DARK, PRIMARY_BG, CARD_BG, CARD_BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, BG,
    SUCCESS, SUCCESS_BG, WARNING, WARNING_BG
)


class HistoryPanel(QWidget):
    """诊断历史记录面板"""

    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ── Header Card ──
        header_card = QFrame()
        header_card.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 10px;
            }}
        """)
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(10)

        title = QLabel("诊断历史")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT_PRIMARY};")
        header_layout.addWidget(title)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索故障码/车型...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                font-size: 13px; padding: 6px 12px;
                border: 1px solid {CARD_BORDER}; border-radius: 8px;
                background: white; min-height: 22px; max-width: 240px;
            }}
            QLineEdit:focus {{ border-color: {PRIMARY}; }}
        """)
        self.search_input.textChanged.connect(self._on_search)
        header_layout.addWidget(self.search_input)

        header_layout.addStretch()

        self.clear_btn = QPushButton("清空历史")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 12px; padding: 6px 14px;
                background-color: {WARNING_BG}; color: {WARNING};
                border: 1px solid {WARNING}; border-radius: 6px;
            }}
            QPushButton:hover {{ background-color: {WARNING}; color: white; }}
        """)
        self.clear_btn.clicked.connect(self._on_clear)
        header_layout.addWidget(self.clear_btn)

        layout.addWidget(header_card)

        # ── Table ──
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["故障码", "车型", "知识库", "AI建议", "时间"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {CARD_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 8px;
                gridline-color: {CARD_BORDER};
                font-size: 13px;
            }}
            QTableWidget::item {{
                padding: 8px 12px;
                color: {TEXT_PRIMARY};
            }}
            QTableWidget::item:selected {{
                background-color: {PRIMARY_BG};
            }}
            QTableWidget::item:alternate {{
                background-color: #F8F9FA;
            }}
            QHeaderView::section {{
                background-color: {BG};
                border: none;
                border-bottom: 1px solid {CARD_BORDER};
                padding: 8px 12px;
                font-size: 12px;
                font-weight: bold;
                color: {TEXT_SECONDARY};
            }}
        """)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        # ── Stats ──
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED}; padding: 4px 8px;")
        layout.addWidget(self.stats_label)

    def refresh(self):
        """刷新历史记录"""
        records = self.db.get_history(limit=100)
        self._populate_table(records)

    def _on_search(self, keyword: str):
        """搜索历史"""
        if not keyword.strip():
            self.refresh()
            return
        records = self.db.search_history(keyword.strip())
        self._populate_table(records)

    def _populate_table(self, records: list):
        """填充表格"""
        self.table.setRowCount(len(records))

        for i, record in enumerate(records):
            code_item = QTableWidgetItem(record.get("code", ""))
            code_item.setFont(__import__('PyQt6.QtGui', fromlist=['QFont']).QFont("Consolas", 12))
            self.table.setItem(i, 0, code_item)

            self.table.setItem(i, 1, QTableWidgetItem(record.get("vehicle_info", "") or "-"))

            kb_item = QTableWidgetItem("✅" if record.get("knowledge_found") else "❌")
            kb_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 2, kb_item)

            has_ai = bool(record.get("ai_suggestion"))
            ai_item = QTableWidgetItem("✅" if has_ai else "❌")
            ai_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 3, ai_item)

            time_str = record.get("created_at", "")
            if time_str:
                time_str = time_str[:16]
            self.table.setItem(i, 4, QTableWidgetItem(time_str or "-"))

        self.stats_label.setText(f"共 {len(records)} 条记录")

    def _on_clear(self):
        """清空历史"""
        reply = QMessageBox.question(
            self, "确认清空",
            "确定要清空所有诊断历史吗？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.clear_history()
            self.refresh()
