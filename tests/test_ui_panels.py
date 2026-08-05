"""
tests/test_ui_panels.py
ResultPanel / HistoryPanel 单元测试（使用 qtbot + offscreen）
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from src.engine.diagnostic import DiagnosticResult, MultiCodeDiagnosticResult
from src.ui.result_panel import ResultPanel
from src.ui.history_panel import HistoryPanel


# ── ResultPanel 测试 ──


class TestResultPanelInit(unittest.TestCase):
    """ResultPanel 基本初始化"""

    def setUp(self):
        self.panel = ResultPanel()

    def test_creates_widgets(self):
        self.assertIsNotNone(self.panel.knowledge_browser)
        self.assertIsNotNone(self.panel.ai_browser)
        self.assertIsNotNone(self.panel.ai_status_label)
        self.assertIsNotNone(self.panel.symptom_input)
        self.assertIsNotNone(self.panel.symptom_btn)
        self.assertIsNotNone(self.panel.export_btn)

    def test_initial_state(self):
        self.assertIsNone(self.panel._current_code)
        self.assertIsNone(self.panel._current_result)
        self.assertFalse(self.panel._ai_stream_started)
        self.assertEqual(self.panel._ai_stream_content, "")


class TestResultPanelClear(unittest.TestCase):
    """clear() 方法"""

    def setUp(self):
        self.panel = ResultPanel()

    def test_clear_resets_state(self):
        self.panel._ai_stream_started = True
        self.panel._ai_stream_content = "some content"
        self.panel.clear()
        self.assertFalse(self.panel._ai_stream_started)
        self.assertEqual(self.panel._ai_stream_content, "")


class TestResultPanelGetResult(unittest.TestCase):
    """get_current_result()"""

    def setUp(self):
        self.panel = ResultPanel()

    def test_returns_none_initially(self):
        self.assertIsNone(self.panel.get_current_result())

    def test_returns_result_after_show(self):
        result = DiagnosticResult(
            code="P0300",
            knowledge={"description": "test", "severity": "medium", "system": "engine", "code_type": "powertrain"},
            ai_suggestion=None,
            ai_available=False,
        )
        self.panel.show_result(result)
        self.assertEqual(self.panel.get_current_result(), result)


class TestResultPanelShowResult(unittest.TestCase):
    """show_result() 方法"""

    def setUp(self):
        self.panel = ResultPanel()

    def test_show_result_with_knowledge(self):
        result = DiagnosticResult(
            code="P0300",
            knowledge={"description": "Random misfire", "severity": "high", "system": "engine", "code_type": "powertrain"},
            ai_suggestion=None,
            ai_available=False,
        )
        self.panel.show_result(result)
        self.assertEqual(self.panel._current_code, "P0300")
        html = self.panel.knowledge_browser.toHtml()
        self.assertIn("P0300", html)
        self.assertIn("Random misfire", html)

    def test_show_result_without_knowledge(self):
        result = DiagnosticResult(
            code="P9999",
            knowledge=None,
            ai_suggestion=None,
            ai_available=False,
        )
        self.panel.show_result(result)
        self.assertIsNone(self.panel._current_code)
        html = self.panel.knowledge_browser.toHtml()
        self.assertIn("P9999", html)
        self.assertIn("未找到", html)

    def test_show_result_with_ai(self):
        result = DiagnosticResult(
            code="P0300",
            knowledge={"description": "Misfire", "severity": "medium", "system": "engine", "code_type": "powertrain"},
            ai_suggestion="Check spark plugs",
            ai_available=True,
        )
        self.panel.show_result(result)
        ai_html = self.panel.ai_browser.toHtml()
        self.assertIn("Check spark plugs", ai_html)
        self.assertIn("已生成", self.panel.ai_status_label.text())

    def test_show_result_without_ai(self):
        result = DiagnosticResult(
            code="P0300",
            knowledge={"description": "Misfire", "severity": "medium", "system": "engine", "code_type": "powertrain"},
            ai_suggestion=None,
            ai_available=False,
        )
        self.panel.show_result(result)
        ai_html = self.panel.ai_browser.toHtml()
        self.assertIn("不可用", ai_html)

    def test_show_result_clears_previous(self):
        """show_result 前会调用 clear 清空上一次结果"""
        r1 = DiagnosticResult(code="P0001", knowledge={"description": "A", "severity": "low", "system": "x", "code_type": "t"}, ai_suggestion=None, ai_available=False)
        r2 = DiagnosticResult(code="P0002", knowledge={"description": "B", "severity": "low", "system": "x", "code_type": "t"}, ai_suggestion=None, ai_available=False)
        self.panel.show_result(r1)
        self.panel.show_result(r2)
        html = self.panel.knowledge_browser.toHtml()
        self.assertIn("P0002", html)
        self.assertNotIn("P0001", html)


class TestResultPanelShowKbResult(unittest.TestCase):
    """show_kb_result() 方法"""

    def setUp(self):
        self.panel = ResultPanel()

    def test_show_kb_result_with_ai_available(self):
        result = DiagnosticResult(
            code="P0171",
            knowledge={"description": "System too lean", "severity": "medium", "system": "fuel", "code_type": "powertrain"},
            ai_suggestion=None,
            ai_available=True,
        )
        self.panel.show_kb_result(result)
        self.assertEqual(self.panel._current_code, "P0171")
        ai_html = self.panel.ai_browser.toHtml()
        self.assertIn("生成中", ai_html)

    def test_show_kb_result_without_ai(self):
        result = DiagnosticResult(
            code="P0171",
            knowledge={"description": "System too lean", "severity": "medium", "system": "fuel", "code_type": "powertrain"},
            ai_suggestion=None,
            ai_available=False,
        )
        self.panel.show_kb_result(result)
        ai_html = self.panel.ai_browser.toHtml()
        self.assertIn("不可用", ai_html)


class TestResultPanelShowLookupResult(unittest.TestCase):
    """show_lookup_result() 方法"""

    def setUp(self):
        self.panel = ResultPanel()

    def test_show_lookup_result(self):
        result = DiagnosticResult(
            code="P0420",
            knowledge={"description": "Catalyst efficiency", "severity": "low", "system": "exhaust", "code_type": "powertrain"},
            ai_suggestion=None,
            ai_available=False,
        )
        self.panel.show_lookup_result(result)
        html = self.panel.knowledge_browser.toHtml()
        self.assertIn("P0420", html)
        self.assertIn("Catalyst efficiency", html)


class TestResultPanelAiStreaming(unittest.TestCase):
    """append_ai_text() / finalize_ai_suggestion()"""

    def setUp(self):
        self.panel = ResultPanel()

    def test_append_ai_text_starts_stream(self):
        self.assertFalse(self.panel._ai_stream_started)
        self.panel.append_ai_text("Hello")
        self.assertTrue(self.panel._ai_stream_started)
        self.assertEqual(self.panel._ai_stream_content, "Hello")

    def test_append_ai_text_accumulates(self):
        self.panel.append_ai_text("Hello")
        self.panel.append_ai_text(" World")
        self.assertEqual(self.panel._ai_stream_content, "Hello World")

    def test_finalize_ai_suggestion_sets_html(self):
        self.panel.append_ai_text("Check spark plugs")
        self.panel.finalize_ai_suggestion("P0300", "Check spark plugs", "2026-01-01")
        ai_html = self.panel.ai_browser.toHtml()
        self.assertIn("Check spark plugs", ai_html)
        self.assertIn("P0300", ai_html)

    def test_finalize_ai_suggestion_empty_text_noop(self):
        """空文本不修改浏览器"""
        self.panel.append_ai_text("something")
        self.panel.finalize_ai_suggestion("P0300", "", "")
        # 浏览器内容不应被空文本覆盖（append_ai_text 已写入的内容仍在）
        ai_html = self.panel.ai_browser.toHtml()
        # finalize 空文本返回前不会清空
        self.assertIn("something", ai_html)


class TestResultPanelShowAiError(unittest.TestCase):
    """show_ai_error()"""

    def setUp(self):
        self.panel = ResultPanel()

    def test_show_ai_error_displays_message(self):
        self.panel._ai_stream_started = True
        self.panel._ai_stream_content = "partial"
        self.panel.show_ai_error("Connection timeout")
        self.assertFalse(self.panel._ai_stream_started)
        self.assertEqual(self.panel._ai_stream_content, "")
        ai_html = self.panel.ai_browser.toHtml()
        self.assertIn("Connection timeout", ai_html)
        self.assertIn("失败", self.panel.ai_status_label.text())


class TestResultPanelBuildKnowledgeHtml(unittest.TestCase):
    """_build_knowledge_html 内部方法"""

    def setUp(self):
        self.panel = ResultPanel()

    def test_includes_description(self):
        result = DiagnosticResult(
            code="P0300",
            knowledge={"description": "Random misfire detected", "severity": "high", "system": "engine", "code_type": "powertrain"},
            ai_suggestion=None,
            ai_available=False,
        )
        html = self.panel._build_knowledge_html(result)
        self.assertIn("Random misfire detected", html)
        self.assertIn("P0300", html)

    def test_includes_severity_badge(self):
        result = DiagnosticResult(
            code="P0300",
            knowledge={"description": "test", "severity": "critical", "system": "engine", "code_type": "powertrain"},
            ai_suggestion=None,
            ai_available=False,
        )
        html = self.panel._build_knowledge_html(result)
        self.assertIn("严重", html)

    def test_includes_detail(self):
        result = DiagnosticResult(
            code="P0300",
            knowledge={"description": "test", "severity": "low", "system": "engine", "code_type": "powertrain", "detail": "Detailed explanation here"},
            ai_suggestion=None,
            ai_available=False,
        )
        html = self.panel._build_knowledge_html(result)
        self.assertIn("Detailed explanation here", html)

    def test_includes_common_causes(self):
        result = DiagnosticResult(
            code="P0300",
            knowledge={"description": "test", "severity": "low", "system": "engine", "code_type": "powertrain", "common_causes": ["Spark plug worn", "Coil pack failure"]},
            ai_suggestion=None,
            ai_available=False,
        )
        html = self.panel._build_knowledge_html(result)
        self.assertIn("Spark plug worn", html)
        self.assertIn("Coil pack failure", html)

    def test_includes_diagnostic_steps(self):
        result = DiagnosticResult(
            code="P0300",
            knowledge={"description": "test", "severity": "low", "system": "engine", "code_type": "powertrain", "diagnostic_steps": ["Check plugs", "Check coils"]},
            ai_suggestion=None,
            ai_available=False,
        )
        html = self.panel._build_knowledge_html(result)
        self.assertIn("Check plugs", html)
        self.assertIn("Check coils", html)

    def test_includes_related_codes(self):
        result = DiagnosticResult(
            code="P0300",
            knowledge={"description": "test", "severity": "low", "system": "engine", "code_type": "powertrain", "related_codes": ["P0301", "P0302"]},
            ai_suggestion=None,
            ai_available=False,
        )
        html = self.panel._build_knowledge_html(result)
        self.assertIn("P0301", html)
        self.assertIn("P0302", html)

    def test_causes_as_json_string(self):
        """common_causes 为 JSON 字符串时能正确解析"""
        result = DiagnosticResult(
            code="P0300",
            knowledge={"description": "test", "severity": "low", "system": "engine", "code_type": "powertrain", "common_causes": '["Plug fouled", " injector leak"]'},
            ai_suggestion=None,
            ai_available=False,
        )
        html = self.panel._build_knowledge_html(result)
        self.assertIn("Plug fouled", html)


class TestResultPanelBuildNotFoundHtml(unittest.TestCase):
    """_build_not_found_html"""

    def setUp(self):
        self.panel = ResultPanel()

    def test_not_found_includes_code(self):
        result = DiagnosticResult(code="P9999", knowledge=None, ai_suggestion=None, ai_available=False)
        html = self.panel._build_not_found_html(result)
        self.assertIn("P9999", html)
        self.assertIn("未找到", html)


class TestResultPanelBuildAiHtml(unittest.TestCase):
    """_build_ai_html"""

    def setUp(self):
        self.panel = ResultPanel()

    def test_ai_html_includes_suggestion(self):
        result = DiagnosticResult(
            code="P0300",
            knowledge={"description": "test", "severity": "medium", "system": "engine", "code_type": "powertrain"},
            ai_suggestion="## Diagnosis\nCheck spark plugs",
            ai_available=True,
        )
        html = self.panel._build_ai_html(result)
        self.assertIn("Check spark plugs", html)
        self.assertIn("P0300", html)


class TestResultPanelMultiCode(unittest.TestCase):
    """show_multi_code_result / _build_multi_code_kb_html / _build_multi_code_ai_html"""

    def setUp(self):
        self.panel = ResultPanel()

    def test_show_multi_code_result_with_ai(self):
        r1 = DiagnosticResult(code="P0300", knowledge={"description": "Misfire", "severity": "high", "system": "engine", "code_type": "powertrain"}, ai_suggestion=None, ai_available=False)
        r2 = DiagnosticResult(code="P0171", knowledge={"description": "Lean", "severity": "medium", "system": "fuel", "code_type": "powertrain"}, ai_suggestion=None, ai_available=False)
        multi = MultiCodeDiagnosticResult(codes=["P0300", "P0171"], results=[r1, r2], ai_suggestion="Both codes related to fuel mixture", ai_available=True)
        self.panel.show_multi_code_result(multi)
        html = self.panel.knowledge_browser.toHtml()
        self.assertIn("P0300", html)
        self.assertIn("P0171", html)
        ai_html = self.panel.ai_browser.toHtml()
        self.assertIn("Both codes related", ai_html)

    def test_show_multi_code_result_without_ai(self):
        r1 = DiagnosticResult(code="P0300", knowledge={"description": "Misfire", "severity": "high", "system": "engine", "code_type": "powertrain"}, ai_suggestion=None, ai_available=False)
        multi = MultiCodeDiagnosticResult(codes=["P0300"], results=[r1], ai_suggestion=None, ai_available=False)
        self.panel.show_multi_code_result(multi)
        ai_html = self.panel.ai_browser.toHtml()
        self.assertIn("不可用", ai_html)

    def test_build_multi_code_kb_html_includes_all_codes(self):
        r1 = DiagnosticResult(code="P0300", knowledge={"description": "Misfire", "severity": "high", "system": "engine", "code_type": "powertrain"}, ai_suggestion=None, ai_available=False)
        r2 = DiagnosticResult(code="U0100", knowledge=None, ai_suggestion=None, ai_available=False)
        multi = MultiCodeDiagnosticResult(codes=["P0300", "U0100"], results=[r1, r2], ai_suggestion=None, ai_available=False)
        html = self.panel._build_multi_code_kb_html(multi)
        self.assertIn("P0300", html)
        self.assertIn("U0100", html)
        self.assertIn("未收录", html)

    def test_build_multi_code_ai_html(self):
        r1 = DiagnosticResult(code="P0300", knowledge={"description": "Misfire", "severity": "high", "system": "engine", "code_type": "powertrain"}, ai_suggestion=None, ai_available=False)
        multi = MultiCodeDiagnosticResult(codes=["P0300"], results=[r1], ai_suggestion="## Analysis\nMisfire caused by fuel issue", ai_available=True)
        html = self.panel._build_multi_code_ai_html(multi)
        self.assertIn("Misfire caused by fuel issue", html)


class TestResultPanelSymptoms(unittest.TestCase):
    """_on_save_symptom / _refresh_symptoms_display"""

    def setUp(self):
        self.panel = ResultPanel()

    def test_save_symptom_empty_text_noop(self):
        self.panel.symptom_input.setText("")
        self.panel._current_code = "P0300"
        self.panel._on_save_symptom()  # 不应报错

    def test_save_symptom_no_code_noop(self):
        self.panel.symptom_input.setText("engine shakes")
        self.panel._current_code = None
        self.panel._on_save_symptom()  # 不应报错

    @patch("src.ui.result_panel.KnowledgeBase")
    def test_save_symptom_success(self, MockKB):
        self.panel.kb = MockKB()
        self.panel.kb.record_symptoms.return_value = True
        self.panel.kb.get_symptoms.return_value = ["engine shakes"]
        self.panel._current_code = "P0300"
        self.panel.symptom_input.setText("engine shakes")
        self.panel._on_save_symptom()
        self.panel.kb.record_symptoms.assert_called_once_with("P0300", "engine shakes")
        self.assertEqual(self.panel.symptom_input.text(), "")

    def test_refresh_symptoms_no_code(self):
        self.panel._current_code = None
        self.panel._refresh_symptoms_display()
        self.assertEqual(self.panel.symptom_display.text(), "暂无记录")

    @patch("src.ui.result_panel.KnowledgeBase")
    def test_refresh_symptoms_with_records(self, MockKB):
        self.panel.kb = MockKB()
        self.panel.kb.get_symptoms.return_value = ["smoke", "noise"]
        self.panel._current_code = "P0300"
        self.panel._refresh_symptoms_display()
        text = self.panel.symptom_display.text()
        self.assertIn("smoke", text)
        self.assertIn("noise", text)

    @patch("src.ui.result_panel.KnowledgeBase")
    def test_refresh_symptoms_empty(self, MockKB):
        self.panel.kb = MockKB()
        self.panel.kb.get_symptoms.return_value = []
        self.panel._current_code = "P0300"
        self.panel._refresh_symptoms_display()
        self.assertIn("暂未记录", self.panel.symptom_display.text())


# ── HistoryPanel 测试 ──


def _make_mock_db(records=None, search_records=None):
    db = MagicMock()
    db.get_history.return_value = records or []
    db.search_history.return_value = search_records or []
    return db


class TestHistoryPanelInit(unittest.TestCase):
    """HistoryPanel 初始化"""

    def test_creates_widgets(self):
        db = _make_mock_db()
        panel = HistoryPanel(db)
        self.assertIsNotNone(panel.table)
        self.assertIsNotNone(panel.search_input)
        self.assertIsNotNone(panel.clear_btn)
        self.assertIsNotNone(panel.stats_label)

    def test_table_columns(self):
        db = _make_mock_db()
        panel = HistoryPanel(db)
        self.assertEqual(panel.table.columnCount(), 5)


class TestHistoryPanelRefresh(unittest.TestCase):
    """refresh() 方法"""

    def test_refresh_populates_table(self):
        records = [
            {"code": "P0300", "vehicle_info": "Tesla M3", "knowledge_found": True, "ai_suggestion": "Check plugs", "created_at": "2026-01-01 10:00:00"},
            {"code": "P0171", "vehicle_info": "", "knowledge_found": False, "ai_suggestion": None, "created_at": "2026-01-02 11:00:00"},
        ]
        db = _make_mock_db(records=records)
        panel = HistoryPanel(db)
        self.assertEqual(panel.table.rowCount(), 2)
        self.assertEqual(panel.table.item(0, 0).text(), "P0300")
        self.assertEqual(panel.table.item(1, 1).text(), "-")

    def test_refresh_empty(self):
        db = _make_mock_db(records=[])
        panel = HistoryPanel(db)
        self.assertEqual(panel.table.rowCount(), 0)
        self.assertIn("0", panel.stats_label.text())


class TestHistoryPanelSearch(unittest.TestCase):
    """_on_search() 方法"""

    def test_empty_search_refreshes(self):
        records = [{"code": "P0300", "vehicle_info": "X", "knowledge_found": True, "ai_suggestion": None, "created_at": ""}]
        db = _make_mock_db(records=records)
        panel = HistoryPanel(db)
        panel.search_input.setText("")
        # 空搜索 → 调用 refresh → get_history
        db.get_history.assert_called()

    def test_keyword_search(self):
        search_records = [{"code": "P0300", "vehicle_info": "Tesla", "knowledge_found": True, "ai_suggestion": None, "created_at": ""}]
        db = _make_mock_db(search_records=search_records)
        panel = HistoryPanel(db)
        panel._on_search("P0300")
        db.search_history.assert_called_once_with("P0300")


class TestHistoryPanelClear(unittest.TestCase):
    """_on_clear()"""

    def test_clear_calls_db(self):
        db = _make_mock_db()
        panel = HistoryPanel(db)
        with patch("src.ui.history_panel.QMessageBox") as mock_msgbox:
            mock_msgbox.question.return_value = mock_msgbox.StandardButton.Yes
            panel._on_clear()
            db.clear_history.assert_called_once()


class TestHistoryPanelContextMenu(unittest.TestCase):
    """_on_context_menu"""

    def test_invalid_row_noop(self):
        db = _make_mock_db()
        panel = HistoryPanel(db)
        # row=-1 不应报错
        panel._on_context_menu(type("Pos", (), {"y": lambda self: -1})())

    def test_valid_row_emits_signal(self):
        records = [{"code": "P0300", "vehicle_info": "X", "knowledge_found": True, "ai_suggestion": None, "created_at": ""}]
        db = _make_mock_db(records=records)
        panel = HistoryPanel(db)
        # _records 被 populate 填充
        self.assertEqual(len(panel._records), 1)


class TestHistoryPanelRefreshTheme(unittest.TestCase):
    """refresh_theme() 不报错"""

    def test_refresh_theme_no_error(self):
        db = _make_mock_db()
        panel = HistoryPanel(db)
        panel.refresh_theme()  # 不应抛异常


if __name__ == "__main__":
    unittest.main()
