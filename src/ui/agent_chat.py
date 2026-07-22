"""
AI 诊断助手对话面板 (方案C)
实现与 AI Agent 的对话式交互
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextBrowser, QLineEdit, QPushButton, QGroupBox,
    QFrame, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont

from src.engine.diagnostic import DiagnosticEngine, DiagnosticResult
from src.ai.agent import DiagnosticAgent
from src.ui.styles import PRIMARY, PRIMARY_DARK, PRIMARY_BG, CARD_BORDER, CARD_BG, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, BG, FONT_MONO, WARNING, WARNING_BG
import re


class AgentWorker(QThread):
    """AI Agent 后台工作线程"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, agent: DiagnosticAgent, message: str):
        super().__init__()
        self.agent = agent
        self.message = message

    def run(self):
        try:
            response = self.agent.chat(self.message)
            self.finished.emit(response)
        except Exception as e:
            self.error.emit(str(e))


class AgentChatPanel(QWidget):
    """AI Agent 对话面板"""

    def __init__(self, engine: DiagnosticEngine):
        super().__init__()
        self.engine = engine
        self.agent = DiagnosticAgent(
            kb=engine.kb,
            llm=engine.llm
        )
        self.worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 信息提示
        info_card = QFrame()
        info_card.setStyleSheet(f"background-color: {PRIMARY_BG}; border-radius: 8px;")
        info_card_layout = QHBoxLayout(info_card)
        info_card_layout.setContentsMargins(14, 10, 14, 10)

        info_label = QLabel(
            "AI 诊断助手会通过提问引导你一步步排查故障。\n"
            "输入故障码开始对话，或直接描述你遇到的问题。"
        )
        info_label.setStyleSheet(f"color: {PRIMARY}; font-size: 12px;")
        info_label.setWordWrap(True)
        info_card_layout.addWidget(info_label)
        layout.addWidget(info_card)

        # 对话显示区
        self.chat_browser = QTextBrowser()
        self.chat_browser.setOpenExternalLinks(True)
        self.chat_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: transparent;
                border: none;
                padding: 8px;
                font-size: 14px;
                line-height: 1.6;
                color: {TEXT_PRIMARY};
            }}
        """)
        layout.addWidget(self.chat_browser, 1)

        self._append_welcome()

        # 输入区
        input_card = QFrame()
        input_card.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 10px;
            }}
        """)
        input_card_layout = QHBoxLayout(input_card)
        input_card_layout.setContentsMargins(12, 6, 6, 6)

        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("输入故障码或描述故障现象...")
        self.message_input.setStyleSheet(f"""
            QLineEdit {{
                font-size: 14px; padding: 6px 10px;
                border: 1px solid {CARD_BORDER}; border-radius: 6px;
                background-color: {BG}; min-height: 24px;
            }}
            QLineEdit:focus {{ border-color: {PRIMARY}; background-color: white; }}
        """)
        self.message_input.returnPressed.connect(self.on_send_message)
        input_card_layout.addWidget(self.message_input, 1)

        self.send_btn = QPushButton("发送")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setMinimumHeight(36)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 14px; font-weight: bold;
                background-color: {PRIMARY}; color: white;
                border: none; border-radius: 8px;
                padding: 4px 20px; min-height: 36px;
            }}
            QPushButton:hover {{ background-color: {PRIMARY_DARK}; }}
            QPushButton:disabled {{ background-color: #90CAF9; }}
        """)
        self.send_btn.clicked.connect(self.on_send_message)
        input_card_layout.addWidget(self.send_btn)

        layout.addWidget(input_card)

        # 快捷按钮区
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(8)

        btn_style = f"""
            QPushButton {{
                font-size: 12px;
                background-color: {CARD_BG};
                color: {TEXT_SECONDARY};
                border: 1px solid {CARD_BORDER};
                border-radius: 6px;
                padding: 4px 14px;
            }}
            QPushButton:hover {{ background-color: {PRIMARY_BG}; color: {PRIMARY}; }}
        """

        self.btn_start = QPushButton("新诊断")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.setStyleSheet(btn_style)
        self.btn_start.clicked.connect(self._on_new_diagnosis)
        quick_layout.addWidget(self.btn_start)

        self.btn_history = QPushButton("会话信息")
        self.btn_history.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_history.setStyleSheet(btn_style)
        self.btn_history.clicked.connect(self._on_show_session)
        quick_layout.addWidget(self.btn_history)

        self.btn_clear = QPushButton("清空")
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.setStyleSheet(btn_style)
        self.btn_clear.clicked.connect(self._on_clear_chat)
        quick_layout.addWidget(self.btn_clear)

        quick_layout.addStretch()
        layout.addLayout(quick_layout)

    def _append_welcome(self):
        """显示欢迎消息"""
        welcome = f"""
        <div style="font-family: 'Microsoft YaHei UI', sans-serif; color: {TEXT_PRIMARY};">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span style="font-size: 16px;">AI</span>
                <span style="font-size: 16px; font-weight: bold; color: {PRIMARY};">诊断助手</span>
            </div>
            <p style="color: {TEXT_SECONDARY};">我可以帮助你诊断汽车故障码：</p>
            <ul style="color: {TEXT_SECONDARY}; line-height: 1.8;">
                <li><strong>输入故障码</strong> — 如 <code style="font-family: Consolas; background-color: {BG}; padding: 1px 6px; border-radius: 3px;">P0300</code></li>
                <li><strong>描述症状</strong> — 如"冷车启动抖动"，我帮你分析可能原因</li>
            </ul>
            <div style="height: 1px; background-color: {CARD_BORDER}; margin: 8px 0;"></div>
            <p style="font-size: 12px; color: {TEXT_SECONDARY};">
                提示：建议先在"诊断结果"页查询故障码，然后来这里深入对话
            </p>
        </div>
        """
        self.chat_browser.setHtml(welcome)

    def _append_message(self, role: str, content: str):
        """
        在对话区追加消息

        Args:
            role: "user" 或 "assistant" 或 "system"
            content: 消息内容
        """
        content = content.replace('\n', '<br>')
        content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)

        if role == "user":
            html = f"""
            <div style="margin: 8px 0; text-align: right;">
                <div style="display: inline-block; background-color: {PRIMARY_BG};
                            color: {PRIMARY}; padding: 10px 16px; border-radius: 14px 14px 4px 14px;
                            max-width: 70%; text-align: left; font-size: 14px; line-height: 1.6;">
                    {content}
                </div>
            </div>
            """
        elif role == "assistant":
            html = f"""
            <div style="margin: 8px 0;">
                <div style="display: inline-block; background-color: #F5F5F5;
                            color: {TEXT_PRIMARY}; padding: 10px 16px; border-radius: 14px 14px 14px 4px;
                            max-width: 70%; text-align: left; font-size: 14px; line-height: 1.6;">
                    {content}
                </div>
            </div>
            """
        else:
            html = f"""
            <div style="margin: 8px 0; text-align: center;">
                <div style="display: inline-block; background-color: {WARNING_BG};
                            color: {WARNING}; padding: 6px 12px; border-radius: 6px;
                            font-size: 12px;">
                    {content}
                </div>
            </div>
            """

        # 追加到现有内容
        current = self.chat_browser.toHtml()
        # 找到 </body> 标签，在之前插入
        if "</body>" in current:
            insert_pos = current.rfind("</body>")
            new_html = current[:insert_pos] + html + current[insert_pos:]
            self.chat_browser.setHtml(new_html)
        else:
            # 保底方案
            existing = self.chat_browser.toPlainText()
            if existing.strip():
                self.chat_browser.append(html)
            else:
                self.chat_browser.setHtml(html)

        # 滚动到底部
        scrollbar = self.chat_browser.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def on_send_message(self):
        """发送消息"""
        message = self.message_input.text().strip()
        if not message:
            return

        # 显示用户消息
        self._append_message("user", message)
        self.message_input.clear()

        # 禁用输入
        self._set_input_enabled(False)

        # 启动后台线程
        self.worker = AgentWorker(self.agent, message)
        self.worker.finished.connect(self._on_agent_response)
        self.worker.error.connect(self._on_agent_error)
        self.worker.start()

    def _on_agent_response(self, response: str):
        """AI Agent 回复回调"""
        self._append_message("assistant", response)
        self._set_input_enabled(True)

    def _on_agent_error(self, error_msg: str):
        """AI Agent 错误回调"""
        self._append_message("system", f"⚠️ 错误: {error_msg}")
        self._set_input_enabled(True)

    def _set_input_enabled(self, enabled: bool):
        """启用/禁用输入"""
        self.message_input.setEnabled(enabled)
        self.send_btn.setEnabled(enabled)
        if enabled:
            self.message_input.setFocus()
            self.send_btn.setText("发送")
        else:
            self.send_btn.setText("⏳ 思考中...")

    def sync_diagnosis(self, result: DiagnosticResult):
        """
        从诊断结果页同步信息到 AI 对话

        Args:
            result: 诊断结果
        """
        if result.has_knowledge():
            kb = result.knowledge
            msg = (
                f"我刚查询了故障码 {result.code}：\n"
                f"• 描述: {kb.get('description', '')}\n"
            )
            causes = kb.get("common_causes", [])
            if causes:
                msg += f"• 常见原因: {causes[0]}等\n"
            msg += "请帮我分析一下，看看从哪里开始排查比较好。"

            self.message_input.setText(msg)
            self.on_send_message()

    def _on_new_diagnosis(self):
        """开始新诊断"""
        self.agent.reset_session()
        self.chat_browser.clear()
        self._append_welcome()
        self._append_message("system", "🆕 已开始新的诊断会话")

    def _on_show_session(self):
        """显示当前会话信息"""
        summary = self.agent.get_session_summary()
        if summary.get("status") == "no_active_session":
            self._append_message("system", "当前没有活跃的诊断会话。输入故障码开始吧！")
        else:
            info = (
                f"📋 当前诊断会话\n"
                f"• 故障码: {summary.get('code', '无')}\n"
                f"• 车型信息: {summary.get('vehicle_info', '无') or '无'}\n"
                f"• 对话轮次: {summary.get('turns', 0)}\n"
                f"• 知识库匹配: {'✅ 已找到' if summary.get('knowledge_found') else '❌ 未找到'}"
            )
            self._append_message("system", info)

    def _on_clear_chat(self):
        """清空对话"""
        self.chat_browser.clear()
        self._append_welcome()
