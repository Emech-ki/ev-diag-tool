"""
AI 诊断助手对话面板 (方案C)
实现与 AI Agent 的对话式交互（流式响应）
"""

import html as html_mod

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextBrowser, QLineEdit, QPushButton,
    QFrame, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QTextCursor

from src.engine.diagnostic import DiagnosticEngine, DiagnosticResult
from src.ai.agent import DiagnosticAgent
from src.ui.markdown_renderer import md_to_html
from src.ui.styles import PRIMARY, PRIMARY_DARK, PRIMARY_BG, CARD_BORDER, CARD_BG, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, BG, WARNING, WARNING_BG


class AgentStreamWorker(QThread):
    """AI Agent 流式工作线程 — 全链路流式"""
    chunk = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    tool_call_signal = pyqtSignal(str, str)    # (工具名, 参数描述)
    tool_result_signal = pyqtSignal(str, str)  # (工具名, 结果摘要)

    def __init__(self, agent: DiagnosticAgent, message: str):
        super().__init__()
        self.agent = agent
        self.message = message

    def run(self):
        try:
            def on_tool_call(name, args):
                args_desc = ", ".join(f"{k}={v}" for k, v in args.items())
                self.tool_call_signal.emit(name, args_desc)

            def on_tool_result(name, result):
                self.tool_result_signal.emit(name, result)

            # 使用流式 run_stream，逐 token emit
            for event in self.agent.run_stream(
                self.message,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
            ):
                if event.type == "content":
                    self.chunk.emit(event.content)
                # tool_calls 和 done 事件由 Agent 内部处理

            self.finished.emit()
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
        self._messages = []  # (role, content) 消息列表，用于可靠重建
        self._stream_content = ""  # 流式消息缓冲区
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

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

        self.chat_edit = QTextEdit()
        self.chat_edit.setReadOnly(True)
        self.chat_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: transparent;
                border: none;
                padding: 8px;
                font-size: 14px;
                line-height: 1.6;
                color: {TEXT_PRIMARY};
            }}
        """)
        layout.addWidget(self.chat_edit, 1)

        self._append_welcome()

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

    def _clear_display(self):
        self.chat_edit.clear()
        self._messages.clear()
        self._stream_content = ""

    def _append_html(self, html: str):
        cursor = self.chat_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(html)
        self.chat_edit.ensureCursorVisible()

    def _rebuild_display(self):
        """从消息列表重建整个聊天显示"""
        self.chat_edit.setUpdatesEnabled(False)
        self.chat_edit.clear()
        self._append_welcome()
        for role, content in self._messages:
            self._append_message_html(role, content)
        self.chat_edit.setUpdatesEnabled(True)

    def _append_welcome(self):
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
        self._append_html(welcome)

    def _append_message(self, role: str, content: str):
        """记录消息并渲染"""
        self._messages.append((role, content))
        self._append_message_html(role, content)

    def _append_message_html(self, role: str, content: str):
        """仅渲染消息到界面（不记录）"""
        if role == "assistant":
            # AI 回复使用完整 Markdown 渲染
            rendered = md_to_html(content)
        else:
            # 用户消息和系统消息只做基础转义
            rendered = html_mod.escape(content)
            rendered = rendered.replace('\n', '<br>')

        if role == "user":
            html = f"""
            <div style="margin: 8px 0; text-align: right;">
                <div style="display: inline-block; background-color: {PRIMARY_BG};
                            color: {PRIMARY}; padding: 10px 16px; border-radius: 14px 14px 4px 14px;
                            max-width: 70%; text-align: left; font-size: 14px; line-height: 1.6;">
                    {rendered}
                </div>
            </div>
            """
        elif role == "assistant":
            html = f"""
            <div style="margin: 8px 0;">
                <div style="display: inline-block; background-color: #F5F5F5;
                            color: {TEXT_PRIMARY}; padding: 10px 16px; border-radius: 14px 14px 14px 4px;
                            max-width: 70%; text-align: left; font-size: 14px; line-height: 1.6;">
                    {rendered}
                </div>
            </div>
            """
        else:
            html = f"""
            <div style="margin: 8px 0; text-align: center;">
                <div style="display: inline-block; background-color: {WARNING_BG};
                            color: {WARNING}; padding: 6px 12px; border-radius: 6px;
                            font-size: 12px;">
                    {rendered}
                </div>
            </div>
            """

        self._append_html(html)

    def _start_stream_message(self):
        """开始流式消息"""
        self._stream_content = ""
        self._pending_bold_buf = ""  # 跨 token 粗体缓冲区

    def _append_stream_token(self, token: str):
        """追加流式 token 到当前消息（支持跨 token 的 **粗体** 标记）"""
        self._stream_content += token

        # 如果有未闭合的粗体缓冲，先拼接
        work = self._pending_bold_buf + token
        self._pending_bold_buf = ""

        # 按 ** 分割，奇数段需要加粗
        parts = work.split("**")

        # 如果 parts 长度为偶数，说明最后一个是未闭合的（缺少右 **）
        # 需要缓冲到下一个 token
        if len(parts) % 2 == 0:
            # 最后一段缺少右 **，缓冲起来
            self._pending_bold_buf = parts[-1]
            parts = parts[:-1]

        html_parts = []
        for i, part in enumerate(parts):
            escaped = html_mod.escape(part)
            escaped = escaped.replace('\n', '<br>')
            if i % 2 == 1:
                # 奇数段 → 粗体
                html_parts.append(f"<strong>{escaped}</strong>")
            else:
                html_parts.append(escaped)

        rendered = "".join(html_parts)
        if not rendered:
            return

        cursor = self.chat_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(rendered)
        self.chat_edit.ensureCursorVisible()

    def _finalize_stream_message(self):
        """流式完成后，用完整 Markdown 渲染重建最后一条消息"""
        if not self._stream_content:
            return

        # 将流式内容记录到消息列表
        self._messages.append(("assistant", self._stream_content))
        self._pending_bold_buf = ""

        # 删除流式阶段的原始文本（选中最后一条消息区域并替换）
        # 简单方案：重建整个显示
        self._rebuild_display()

    def _stop_worker(self):
        """安全停止当前 worker 线程"""
        if self.worker is not None:
            try:
                self.worker.chunk.disconnect(self._on_stream_chunk)
                self.worker.finished.disconnect(self._on_stream_finished)
                self.worker.error.disconnect(self._on_agent_error)
                self.worker.tool_call_signal.disconnect(self._on_tool_call)
                self.worker.tool_result_signal.disconnect(self._on_tool_result)
            except TypeError:
                pass
            if self.worker.isRunning():
                self.worker.quit()
                if not self.worker.wait(5000):
                    # wait 超时 → 强制终止
                    self.worker.terminate()
                    self.worker.wait(1000)

    def on_send_message(self):
        message = self.message_input.text().strip()
        if not message:
            return

        self._append_message("user", message)
        self.message_input.clear()

        self._set_input_enabled(False)
        self._start_stream_message()
        self._stop_worker()

        self.worker = AgentStreamWorker(self.agent, message)
        self.worker.chunk.connect(self._on_stream_chunk)
        self.worker.finished.connect(self._on_stream_finished)
        self.worker.error.connect(self._on_agent_error)
        self.worker.tool_call_signal.connect(self._on_tool_call)
        self.worker.tool_result_signal.connect(self._on_tool_result)
        self.worker.start()

    def _on_stream_chunk(self, token: str):
        self._append_stream_token(token)

    def _on_tool_call(self, tool_name: str, args_desc: str):
        """工具调用时显示中间状态"""
        tool_display = {
            "lookup_code": "🔍 查询故障码",
            "search_by_symptom": "🔎 按症状搜索",
            "get_vehicle_info": "🚗 查询车型信息",
            "get_related_codes": "🔗 查询关联故障码",
            "get_diagnostic_steps": "📋 获取诊断步骤",
            "get_wiring_info": "🔌 查询电路信息",
            "record_symptom": "📝 记录症状",
            "get_common_fixes": "🔧 查询修复方案",
            "search_codes_by_system": "📂 按系统浏览",
        }
        display_name = tool_display.get(tool_name, f"🛠️ 调用 {tool_name}")
        self._append_message("system", f"{display_name}: {args_desc}")

    def _on_tool_result(self, tool_name: str, result_summary: str):
        """工具返回结果时显示"""
        # 截取第一行作为摘要
        first_line = result_summary.split("\n")[0][:100]
        self._append_message("system", f"✅ {tool_name} 查询完成")

    def _on_stream_finished(self):
        self._finalize_stream_message()
        self._set_input_enabled(True)

    def _on_agent_error(self, error_msg: str):
        # 记录部分流式内容到消息列表，避免重建时丢失
        if self._stream_content:
            self._messages.append(("assistant", self._stream_content))
            self._stream_content = ""
        self._append_message("system", f"⚠️ 错误: {error_msg}")
        self._set_input_enabled(True)

    def _set_input_enabled(self, enabled: bool):
        self.message_input.setEnabled(enabled)
        self.send_btn.setEnabled(enabled)
        if enabled:
            self.message_input.setFocus()
            self.send_btn.setText("发送")
        else:
            self.send_btn.setText("⏳ 思考中...")

    def sync_diagnosis(self, result: DiagnosticResult):
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

            self._stop_worker()  # 先停止旧 worker，再替换 session
            self.agent.start_diagnosis(result.code)
            self.message_input.setText(msg)
            self.on_send_message()

    def _on_new_diagnosis(self):
        self._stop_worker()  # 先停止 worker，再重置 session
        self.agent.reset_session()
        self._clear_display()
        self._append_welcome()
        self._append_message("system", "🆕 已开始新的诊断会话")

    def _on_show_session(self):
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
        self._stop_worker()  # 先停止 worker，再重置 session
        self.agent.reset_session()
        self._clear_display()
        self._append_welcome()
