"""
tests/test_ui_agent_chat.py
AgentChatPanel 单元测试（使用 qtbot + offscreen）
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock, PropertyMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from src.engine.diagnostic import DiagnosticResult
from src.ui.agent_chat import AgentChatPanel


def _make_mock_engine():
    """创建 mock DiagnosticEngine"""
    engine = MagicMock()
    engine.kb = MagicMock()
    engine.llm = MagicMock()
    return engine


def _make_panel(mock_agent=True):
    """
    创建 AgentChatPanel，mock DiagnosticAgent 避免真实 LLM 调用
    mock_agent=True 时 agent 属性为 MagicMock
    """
    engine = _make_mock_engine()
    if mock_agent:
        with patch("src.ui.agent_chat.DiagnosticAgent") as MockAgent:
            mock_agent_instance = MagicMock()
            MockAgent.return_value = mock_agent_instance
            panel = AgentChatPanel(engine)
            # panel.agent 现在是 MagicMock
            return panel
    else:
        return AgentChatPanel(engine)


class TestAgentChatPanelInit(unittest.TestCase):
    """初始化"""

    def test_creates_widgets(self):
        panel = _make_panel()
        self.assertIsNotNone(panel.chat_edit)
        self.assertIsNotNone(panel.message_input)
        self.assertIsNotNone(panel.send_btn)
        self.assertIsNotNone(panel.btn_start)
        self.assertIsNotNone(panel.btn_history)
        self.assertIsNotNone(panel.btn_clear)

    def test_initial_state(self):
        panel = _make_panel()
        self.assertIsNone(panel.worker)
        self.assertEqual(panel._messages, [])
        self.assertEqual(panel._stream_content, "")

    def test_welcome_message_shown(self):
        panel = _make_panel()
        html = panel.chat_edit.toHtml()
        self.assertIn("诊断助手", html)


class TestAgentChatPanelClearDisplay(unittest.TestCase):
    """_clear_display"""

    def test_clear_resets_all(self):
        panel = _make_panel()
        panel._messages = [("user", "test")]
        panel._stream_content = "streaming"
        panel._clear_display()
        self.assertEqual(panel._messages, [])
        self.assertEqual(panel._stream_content, "")


class TestAgentChatPanelAppendMessage(unittest.TestCase):
    """_append_message / _append_message_html"""

    def test_append_message_records_and_renders(self):
        panel = _make_panel()
        panel._append_message("user", "Hello")
        self.assertEqual(len(panel._messages), 1)
        self.assertEqual(panel._messages[0], ("user", "Hello"))
        html = panel.chat_edit.toHtml()
        self.assertIn("Hello", html)

    def test_append_assistant_message(self):
        panel = _make_panel()
        panel._append_message("assistant", "I can help")
        self.assertEqual(panel._messages[0], ("assistant", "I can help"))

    def test_append_system_message(self):
        panel = _make_panel()
        panel._append_message("system", "Session started")
        self.assertEqual(panel._messages[0], ("system", "Session started"))

    def test_append_message_html_only_does_not_record(self):
        panel = _make_panel()
        panel._append_message_html("user", "test only")
        # 不记录到 _messages
        self.assertEqual(panel._messages, [])
        html = panel.chat_edit.toHtml()
        self.assertIn("test only", html)


class TestAgentChatPanelRebuildDisplay(unittest.TestCase):
    """_rebuild_display"""

    def test_rebuild_restores_messages(self):
        panel = _make_panel()
        panel._append_message("user", "msg1")
        panel._append_message("assistant", "msg2")
        count_before = len(panel._messages)
        panel._rebuild_display()
        # 重建后消息列表不变
        self.assertEqual(len(panel._messages), count_before)


class TestAgentChatPanelOnSend(unittest.TestCase):
    """on_send_message"""

    def test_empty_message_noop(self):
        panel = _make_panel()
        panel.message_input.setText("")
        panel.on_send_message()
        # 没有新增消息（只有 welcome）
        self.assertEqual(len(panel._messages), 0)

    def test_valid_message_recorded(self):
        panel = _make_panel()
        with patch.object(panel, "_stop_worker"), \
             patch.object(panel, "_start_stream_message"), \
             patch("src.ui.agent_chat.AgentStreamWorker") as MockWorker:
            mock_instance = MagicMock()
            MockWorker.return_value = mock_instance
            panel.message_input.setText("P0300")
            panel.on_send_message()
            self.assertEqual(panel._messages[0], ("user", "P0300"))
            self.assertEqual(panel.message_input.text(), "")

    def test_send_message_disables_input(self):
        panel = _make_panel()
        with patch.object(panel, "_stop_worker"), \
             patch.object(panel, "_start_stream_message"), \
             patch("src.ui.agent_chat.AgentStreamWorker") as MockWorker:
            MockWorker.return_value = MagicMock()
            panel.message_input.setText("P0300")
            panel.on_send_message()
            self.assertFalse(panel.message_input.isEnabled())
            self.assertFalse(panel.send_btn.isEnabled())
            self.assertIn("思考中", panel.send_btn.text())


class TestAgentChatPanelSetInputEnabled(unittest.TestCase):
    """_set_input_enabled"""

    def test_enable(self):
        panel = _make_panel()
        panel._set_input_enabled(True)
        self.assertTrue(panel.message_input.isEnabled())
        self.assertTrue(panel.send_btn.isEnabled())
        self.assertEqual(panel.send_btn.text(), "发送")

    def test_disable(self):
        panel = _make_panel()
        panel._set_input_enabled(False)
        self.assertFalse(panel.message_input.isEnabled())
        self.assertIn("思考中", panel.send_btn.text())


class TestAgentChatPanelStreamHandling(unittest.TestCase):
    """流式处理"""

    def test_start_stream_message(self):
        panel = _make_panel()
        panel._start_stream_message()
        self.assertEqual(panel._stream_content, "")
        self.assertIsNotNone(panel._stream_renderer)

    def test_append_stream_token(self):
        panel = _make_panel()
        panel._start_stream_message()
        panel._append_stream_token("Hello")
        self.assertEqual(panel._stream_content, "Hello")

    def test_finalize_stream_message_records(self):
        panel = _make_panel()
        panel._start_stream_message()
        panel._stream_content = "Hello World"
        panel._finalize_stream_message()
        self.assertEqual(panel._messages[-1], ("assistant", "Hello World"))
        # _finalize_stream_message 不清空 _stream_content（只有 _clear_display 才清）
        self.assertEqual(panel._stream_content, "Hello World")

    def test_finalize_empty_noop(self):
        panel = _make_panel()
        panel._stream_content = ""
        panel._finalize_stream_message()
        # 没有新增消息
        self.assertEqual(len(panel._messages), 0)


class TestAgentChatPanelStreamCallbacks(unittest.TestCase):
    """_on_stream_chunk / _on_tool_call / _on_tool_result / _on_stream_finished / _on_agent_error"""

    def setUp(self):
        self.panel = _make_panel()
        self.panel._start_stream_message()

    def test_on_stream_chunk(self):
        self.panel._on_stream_chunk("test")
        self.assertEqual(self.panel._stream_content, "test")

    def test_on_tool_call_displays_status(self):
        self.panel._on_tool_call("lookup_code", "code=P0300")
        # 应追加一条 system 消息
        system_msgs = [m for m in self.panel._messages if m[0] == "system"]
        self.assertTrue(len(system_msgs) > 0)

    def test_on_tool_result_displays_status(self):
        self.panel._on_tool_result("lookup_code", "Found P0300")
        system_msgs = [m for m in self.panel._messages if m[0] == "system"]
        self.assertTrue(len(system_msgs) > 0)

    def test_on_stream_finished_finalizes(self):
        self.panel._stream_content = "Hello"
        self.panel._on_stream_finished()
        self.assertEqual(self.panel._messages[-1], ("assistant", "Hello"))

    def test_on_agent_error_records_partial(self):
        self.panel._stream_content = "partial content"
        self.panel._on_agent_error("timeout")
        # partial content 应被记录
        assistant_msgs = [m for m in self.panel._messages if m[0] == "assistant"]
        self.assertTrue(any("partial content" in m[1] for m in assistant_msgs))
        # error 消息也应记录
        system_msgs = [m for m in self.panel._messages if m[0] == "system"]
        self.assertTrue(any("timeout" in m[1] for m in system_msgs))

    def test_on_agent_error_no_partial(self):
        self.panel._stream_content = ""
        self.panel._on_agent_error("timeout")
        system_msgs = [m for m in self.panel._messages if m[0] == "system"]
        self.assertTrue(any("timeout" in m[1] for m in system_msgs))


class TestAgentChatPanelStopWorker(unittest.TestCase):
    """_stop_worker"""

    def test_no_worker_noop(self):
        panel = _make_panel()
        panel.worker = None
        panel._stop_worker()  # 不应报错

    def test_running_worker_quit(self):
        panel = _make_panel()
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        mock_worker.wait.return_value = True
        panel.worker = mock_worker
        panel._stop_worker()
        mock_worker.quit.assert_called_once()

    def test_worker_wait_timeout_terminate(self):
        panel = _make_panel()
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        mock_worker.wait.return_value = False  # wait 超时
        panel.worker = mock_worker
        panel._stop_worker()
        mock_worker.terminate.assert_called_once()


class TestAgentChatPanelNewDiagnosis(unittest.TestCase):
    """_on_new_diagnosis"""

    def test_new_diagnosis_resets_session(self):
        panel = _make_panel()
        panel._messages = [("user", "old")]
        panel._on_new_diagnosis()
        panel.agent.reset_session.assert_called_once()
        # 应有 "已开始新的诊断会话" 系统消息
        system_msgs = [m for m in panel._messages if m[0] == "system"]
        self.assertTrue(any("新的诊断会话" in m[1] for m in system_msgs))


class TestAgentChatPanelShowSession(unittest.TestCase):
    """_on_show_session"""

    def test_no_active_session(self):
        panel = _make_panel()
        panel.agent.get_session_summary.return_value = {"status": "no_active_session"}
        panel._on_show_session()
        system_msgs = [m for m in panel._messages if m[0] == "system"]
        self.assertTrue(any("没有活跃" in m[1] for m in system_msgs))

    def test_active_session(self):
        panel = _make_panel()
        panel.agent.get_session_summary.return_value = {
            "status": "active",
            "code": "P0300",
            "vehicle_info": "Tesla M3",
            "turns": 3,
            "knowledge_found": True,
        }
        panel._on_show_session()
        system_msgs = [m for m in panel._messages if m[0] == "system"]
        joined = " ".join(m[1] for m in system_msgs)
        self.assertIn("P0300", joined)
        self.assertIn("Tesla M3", joined)


class TestAgentChatPanelClearChat(unittest.TestCase):
    """_on_clear_chat"""

    def test_clear_chat(self):
        panel = _make_panel()
        panel._messages = [("user", "old")]
        panel._on_clear_chat()
        panel.agent.reset_session.assert_called_once()
        self.assertEqual(panel._messages, [])


class TestAgentChatPanelSyncDiagnosis(unittest.TestCase):
    """sync_diagnosis"""

    def test_sync_with_knowledge(self):
        panel = _make_panel()
        result = DiagnosticResult(
            code="P0300",
            knowledge={"description": "Misfire", "common_causes": ["Spark plugs"]},
            ai_suggestion=None,
            ai_available=False,
        )
        with patch.object(panel, "_stop_worker"), \
             patch.object(panel, "on_send_message"):
            panel.sync_diagnosis(result)
            panel.agent.start_diagnosis.assert_called_once_with("P0300")
            self.assertIn("P0300", panel.message_input.text())

    def test_sync_without_knowledge_noop(self):
        panel = _make_panel()
        result = DiagnosticResult(code="P9999", knowledge=None, ai_suggestion=None, ai_available=False)
        with patch.object(panel, "_stop_worker"):
            panel.sync_diagnosis(result)
            panel.agent.start_diagnosis.assert_not_called()


class TestAgentChatPanelRefreshTheme(unittest.TestCase):
    """refresh_theme"""

    def test_refresh_theme_no_error(self):
        panel = _make_panel()
        panel.refresh_theme()  # 不应抛异常


class TestAgentChatPanelOnToolCallDisplay(unittest.TestCase):
    """_on_tool_call 工具名映射"""

    def test_known_tool_names(self):
        panel = _make_panel()
        panel._start_stream_message()
        tools = ["lookup_code", "search_by_symptom", "get_vehicle_info", "get_related_codes",
                  "get_diagnostic_steps", "get_wiring_info", "record_symptom", "get_common_fixes",
                  "search_codes_by_system"]
        for tool in tools:
            panel._on_tool_call(tool, "args")
        system_msgs = [m for m in panel._messages if m[0] == "system"]
        self.assertEqual(len(system_msgs), len(tools))

    def test_unknown_tool_name(self):
        panel = _make_panel()
        panel._start_stream_message()
        panel._on_tool_call("custom_tool", "args")
        system_msgs = [m for m in panel._messages if m[0] == "system"]
        self.assertTrue(any("custom_tool" in m[1] for m in system_msgs))


if __name__ == "__main__":
    unittest.main()
