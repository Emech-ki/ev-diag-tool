"""
添加/编辑远程 API 端点对话框
支持配置 OpenAI 兼容的第三方 API（DeepSeek、OpenAI 等）
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFormLayout, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt

from src.ui.styles import (
    PRIMARY, PRIMARY_DARK, PRIMARY_BG,
    CARD_BG, CARD_BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    BG, FONT_MONO
)


class AddEndpointDialog(QDialog):
    """添加/编辑远程 API 端点对话框"""

    def __init__(self, parent=None, endpoint_data: dict = None):
        """
        Args:
            parent: 父窗口
            endpoint_data: 编辑模式时传入现有端点数据 {"name", "base_url", "api_key", "model_name"}
                          为 None 时为添加模式
        """
        super().__init__(parent)
        self.result_data = None
        self._edit_mode = endpoint_data is not None
        self._endpoint_data = endpoint_data or {}
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("编辑远程模型" if self._edit_mode else "添加远程模型")
        self.setMinimumWidth(420)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # 标题
        title = QLabel("配置 OpenAI 兼容 API")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        desc = QLabel("支持 OpenAI、DeepSeek、LM Studio 等任何 OpenAI 兼容接口。")
        desc.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # 表单
        form_frame = QFrame()
        form_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 8px;
                padding: 4px;
            }}
        """)
        form_layout = QFormLayout(form_frame)
        form_layout.setContentsMargins(16, 16, 16, 16)
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        label_style = f"font-size: 13px; color: {TEXT_PRIMARY}; font-weight: bold;"
        input_style = f"""
            QLineEdit {{
                font-size: 13px; padding: 6px 10px;
                border: 1px solid {CARD_BORDER}; border-radius: 6px;
                background: white; min-height: 22px;
            }}
            QLineEdit:focus {{ border-color: {PRIMARY}; }}
        """

        # 显示名称
        name_label = QLabel("显示名称:")
        name_label.setStyleSheet(label_style)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("如：DeepSeek")
        self.name_input.setStyleSheet(input_style)
        if self._edit_mode:
            self.name_input.setText(self._endpoint_data.get("name", ""))
            self.name_input.setReadOnly(True)
            self.name_input.setStyleSheet(input_style + "QLineEdit { color: #999; background: #f5f5f5; }")
        form_layout.addRow(name_label, self.name_input)

        # API 地址
        url_label = QLabel("API 地址:")
        url_label.setStyleSheet(label_style)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("如：https://api.deepseek.com/v1")
        self.url_input.setStyleSheet(input_style)
        if self._edit_mode:
            self.url_input.setText(self._endpoint_data.get("base_url", ""))
        form_layout.addRow(url_label, self.url_input)

        # API Key
        key_label = QLabel("API Key:")
        key_label.setStyleSheet(label_style)
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("如：sk-your-api-key")
        self.key_input.setStyleSheet(input_style)
        if self._edit_mode:
            self.key_input.setText(self._endpoint_data.get("api_key", ""))
        form_layout.addRow(key_label, self.key_input)

        # 模型名称
        model_label = QLabel("模型名称:")
        model_label.setStyleSheet(label_style)
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("如：deepseek-chat")
        self.model_input.setStyleSheet(input_style)
        if self._edit_mode:
            self.model_input.setText(self._endpoint_data.get("model_name", ""))
        form_layout.addRow(model_label, self.model_input)

        layout.addWidget(form_frame)

        # 提示
        if self._edit_mode:
            hint = QLabel("修改将更新到 .env 文件。端点名称不可修改。")
        else:
            hint = QLabel("配置将保存到 .env 文件，重启后仍然有效。")
        hint.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
        layout.addWidget(hint)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 13px; padding: 6px 20px;
                background-color: {CARD_BG}; color: {TEXT_SECONDARY};
                border: 1px solid {CARD_BORDER}; border-radius: 6px;
                min-height: 30px;
            }}
            QPushButton:hover {{ background-color: {BG}; }}
        """)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        btn_layout.addSpacing(8)

        self.confirm_btn = QPushButton("保存" if self._edit_mode else "添加")
        self.confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.confirm_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 13px; font-weight: bold; padding: 6px 24px;
                background-color: {PRIMARY}; color: white;
                border: none; border-radius: 6px;
                min-height: 30px;
            }}
            QPushButton:hover {{ background-color: {PRIMARY_DARK}; }}
        """)
        self.confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(self.confirm_btn)

        layout.addLayout(btn_layout)

        # 回车确认
        if not self._edit_mode:
            self.name_input.returnPressed.connect(self.url_input.setFocus)
        self.url_input.returnPressed.connect(self.key_input.setFocus)
        self.key_input.returnPressed.connect(self.model_input.setFocus)
        self.model_input.returnPressed.connect(self._on_confirm)

        # 默认焦点
        if self._edit_mode:
            self.url_input.setFocus()
        else:
            self.name_input.setFocus()

    def _on_confirm(self):
        name = self.name_input.text().strip()
        url = self.url_input.text().strip()
        key = self.key_input.text().strip()
        model = self.model_input.text().strip()

        # 验证
        if not name:
            QMessageBox.warning(self, "提示", "请输入显示名称")
            self.name_input.setFocus()
            return
        if not url:
            QMessageBox.warning(self, "提示", "请输入 API 地址")
            self.url_input.setFocus()
            return
        if not key:
            QMessageBox.warning(self, "提示", "请输入 API Key")
            self.key_input.setFocus()
            return
        if not model:
            QMessageBox.warning(self, "提示", "请输入模型名称")
            self.model_input.setFocus()
            return

        # 基本 URL 格式检查
        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(self, "提示", "API 地址需以 http:// 或 https:// 开头")
            self.url_input.setFocus()
            return

        self.result_data = {
            "name": name,
            "base_url": url,
            "api_key": key,
            "model_name": model,
        }
        self.accept()

    def get_result(self):
        """返回对话框结果，None 表示用户取消"""
        return self.result_data
