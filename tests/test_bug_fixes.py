"""
tests/test_bug_fixes.py
回归测试：覆盖 v3.4.3 修复的 5 个 bug

- Bug1: 多码诊断后"导出报告"崩溃（MultiCodeDiagnosticResult 无 code/knowledge 字段）
- Bug2: 历史导出拆分正则不一致（{3,4} → {4}），EV 码匹配不到
- Bug3: show_multi_code_result 未重置症状区
- Bug4: agent_chat._on_tool_result 死代码
- Bug5: 多码历史导出缺少故障码详情（聚合知识库）
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch

from src.engine.diagnostic import DiagnosticResult, MultiCodeDiagnosticResult


# ── Bug 2: _split_history_codes ──


class TestSplitHistoryCodes:
    """main_window._split_history_codes 故障码拆分"""

    @staticmethod
    def _make_window():
        from src.ui.main_window import MainWindow
        return MainWindow.__new__(MainWindow)

    def test_single_standard_code(self):
        win = self._make_window()
        assert win._split_history_codes("P0300") == ["P0300"]

    def test_multi_comma_separated(self):
        win = self._make_window()
        assert win._split_history_codes("P0300, P0171") == ["P0300", "P0171"]

    def test_hex_letter_code_keeps_full_length(self):
        """旧正则 {3,4} 会把 P0300 截成 P030；新正则 {4} 必须保留完整 P0300"""
        win = self._make_window()
        assert win._split_history_codes("P0300, P0A00") == ["P0300", "P0A00"]

    def test_ev_code_detected(self):
        """EV 码必须被识别，不再被当成整体查询"""
        win = self._make_window()
        assert win._split_history_codes("EV-BMS-001") == ["EV-BMS-001"]

    def test_multi_ev_codes(self):
        win = self._make_window()
        assert win._split_history_codes("EV-BMS-001, EV-MOTOR-001") == [
            "EV-BMS-001", "EV-MOTOR-001",
        ]

    def test_mixed_standard_and_ev(self):
        win = self._make_window()
        assert win._split_history_codes("P0300, EV-BMS-001") == ["P0300", "EV-BMS-001"]

    def test_lowercase_input(self):
        win = self._make_window()
        assert win._split_history_codes("p0300") == ["P0300"]


# ── Bug 1 + Bug 5: _aggregate_knowledge ──


class TestAggregateKnowledge:
    """main_window._aggregate_knowledge 多码知识库聚合"""

    @staticmethod
    def _make_window():
        from src.ui.main_window import MainWindow
        return MainWindow.__new__(MainWindow)

    def _kb(self, **kw):
        base = {"code": "", "system": "P", "description": "desc", "detail": "",
                "severity": "medium", "common_causes": [], "diagnostic_steps": [],
                "related_codes": []}
        base.update(kw)
        return base

    def test_merges_descriptions_and_takes_highest_severity(self):
        win = self._make_window()
        r1 = type("_R", (), {"knowledge": self._kb(
            description="失火", severity="high", system="P",
            common_causes=["火花塞"], diagnostic_steps=["检查火花塞"])})()
        r2 = type("_R", (), {"knowledge": self._kb(
            description="混合气稀", severity="medium", system="P",
            common_causes=["真空泄漏"], diagnostic_steps=["检查真空"])})()
        agg = win._aggregate_knowledge([r1, r2], code="P0300, P0171")
        assert agg["code"] == "P0300, P0171"
        assert "失火" in agg["description"]
        assert "混合气稀" in agg["description"]
        assert agg["severity"] == "high"
        assert "火花塞" in agg["common_causes"]
        assert "真空泄漏" in agg["common_causes"]

    def test_ignores_none_knowledge(self):
        win = self._make_window()
        r1 = type("_R", (), {"knowledge": None})()
        r2 = type("_R", (), {"knowledge": self._kb(description="有效")})()
        agg = win._aggregate_knowledge([r1, r2])
        assert agg is not None
        assert "有效" in agg["description"]

    def test_returns_none_when_all_empty(self):
        win = self._make_window()
        r1 = type("_R", (), {"knowledge": None})()
        r2 = type("_R", (), {"knowledge": None})()
        assert win._aggregate_knowledge([r1, r2]) is None


# ── Bug 1: 多码诊断后导出报告 ──


class TestExportCurrentResultMultiCode:
    """_export_current_result 对多码结果不再抛 AttributeError"""

    def _make_multi(self):
        r1 = DiagnosticResult(
            code="P0300",
            knowledge={"code": "P0300", "system": "P", "description": "随机失火",
                       "detail": "", "severity": "high",
                       "common_causes": ["火花塞故障"], "diagnostic_steps": ["检查火花塞"],
                       "related_codes": ["P0301"]},
            ai_suggestion=None, ai_available=False,
        )
        r2 = DiagnosticResult(
            code="P0171",
            knowledge={"code": "P0171", "system": "P", "description": "混合气过稀",
                       "detail": "", "severity": "medium",
                       "common_causes": ["真空泄漏"], "diagnostic_steps": ["检查真空"],
                       "related_codes": []},
            ai_suggestion=None, ai_available=False,
        )
        return MultiCodeDiagnosticResult(
            codes=["P0300", "P0171"], results=[r1, r2],
            ai_suggestion="两个码均指向燃油混合气问题", ai_available=True,
        )

    def _make_win(self, multi):
        from src.ui.main_window import MainWindow
        win = MainWindow.__new__(MainWindow)
        win.result_panel = MagicMock()
        win.result_panel.get_current_result.return_value = multi
        win.symptom_input = MagicMock()
        win.symptom_input.text.return_value = ""
        win.status_bar = MagicMock()
        win.make_selector = MagicMock()
        win.make_selector.currentText.return_value = ""
        win.model_selector_vehicle = MagicMock()
        win.model_selector_vehicle.currentText.return_value = ""
        return win

    def test_multi_code_export_txt(self, tmp_path):
        from src.ui.main_window import MainWindow
        win = self._make_win(self._make_multi())
        out = str(tmp_path / "report.txt")

        with patch.object(
            MainWindow, "_get_vehicle_info", return_value="比亚迪 秦PLUS EV"
        ), patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName",
                 return_value=(out, "文本文件 (*.txt)")):
            win._export_current_result()  # 不应抛异常

        assert os.path.exists(out)
        content = open(out, encoding="utf-8").read()
        assert "P0300" in content
        assert "P0171" in content
        assert "随机失火" in content
        assert "混合气过稀" in content
        win.status_bar.showMessage.assert_called()

    def test_multi_code_all_unknown_export_txt(self, tmp_path):
        """多码全部未收录时聚合返回 None，导出不崩溃"""
        r1 = DiagnosticResult(code="P9999", knowledge=None, ai_suggestion=None, ai_available=False)
        r2 = DiagnosticResult(code="P8888", knowledge=None, ai_suggestion=None, ai_available=False)
        multi = MultiCodeDiagnosticResult(
            codes=["P9999", "P8888"], results=[r1, r2],
            ai_suggestion=None, ai_available=False,
        )
        win = self._make_win(multi)
        out = str(tmp_path / "report2.txt")

        with patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName",
                   return_value=(out, "文本文件 (*.txt)")):
            win._export_current_result()  # 不应抛异常

        assert os.path.exists(out)


# ── Bug 2 + Bug 5: 多码历史记录导出 ──


class TestExportHistoryRecordMultiCode:
    """_export_history_record 对多码/EV 码历史记录正确拆分并聚合详情"""

    def _make_win(self):
        from src.ui.main_window import MainWindow
        win = MainWindow.__new__(MainWindow)
        win.engine = MagicMock()
        win.status_bar = MagicMock()
        return win

    def test_multi_code_history_aggregates_details(self, tmp_path):
        win = self._make_win()
        kb_map = {
            "P0300": {"code": "P0300", "system": "P", "description": "随机失火",
                      "detail": "", "severity": "high",
                      "common_causes": ["火花塞故障"], "diagnostic_steps": ["检查火花塞"],
                      "related_codes": []},
            "P0171": {"code": "P0171", "system": "P", "description": "混合气过稀",
                      "detail": "", "severity": "medium",
                      "common_causes": ["真空泄漏"], "diagnostic_steps": ["检查真空"],
                      "related_codes": []},
        }
        win.engine.kb.lookup.side_effect = lambda c: kb_map.get(c)

        record = {
            "code": "P0300, P0171",
            "vehicle_info": "比亚迪 秦PLUS EV",
            "symptoms": "冷车抖动",
            "ai_suggestion": "建议先查燃油压力",
            "created_at": "2026-08-05 10:00:00",
        }
        out = str(tmp_path / "history.txt")

        with patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName",
                   return_value=(out, "文本文件 (*.txt)")):
            win._export_history_record(record)  # 不应抛异常

        assert os.path.exists(out)
        content = open(out, encoding="utf-8").read()
        # 聚合详情出现在报告中
        assert "随机失火" in content
        assert "混合气过稀" in content
        # AI 建议保留
        assert "建议先查燃油压力" in content

    def test_ev_code_history_export(self, tmp_path):
        win = self._make_win()
        kb_map = {
            "EV-BMS-001": {"code": "EV-BMS-001", "system": "EV-BMS",
                           "description": "绝缘电阻过低", "detail": "", "severity": "critical",
                           "common_causes": ["绝缘膜破损"], "diagnostic_steps": ["测绝缘电阻"],
                           "related_codes": []},
        }
        win.engine.kb.lookup.side_effect = lambda c: kb_map.get(c)

        record = {
            "code": "EV-BMS-001",
            "vehicle_info": "比亚迪 秦PLUS EV",
            "symptoms": "",
            "ai_suggestion": "",
            "created_at": "2026-08-05 10:00:00",
        }
        out = str(tmp_path / "ev.txt")

        with patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName",
                   return_value=(out, "文本文件 (*.txt)")):
            win._export_history_record(record)  # 不应抛异常，且不应整体查 "EV-BMS-001"

        assert os.path.exists(out)
        content = open(out, encoding="utf-8").read()
        assert "EV-BMS-001" in content
        assert "绝缘电阻过低" in content


# ── Bug 3: show_multi_code_result 重置症状区 ──


class TestResultPanelMultiCodeResetsSymptoms:
    """show_multi_code_result 后 _current_code 应为 None，症状区重置"""

    def setup_method(self):
        from src.ui.result_panel import ResultPanel
        self.panel = ResultPanel()
        self.panel.kb = MagicMock()

    def test_multi_code_resets_current_code(self):
        r1 = DiagnosticResult(
            code="P0300",
            knowledge={"description": "Misfire", "severity": "high", "system": "engine",
                       "code_type": "powertrain"},
            ai_suggestion=None, ai_available=False,
        )
        # 先模拟单码诊断，留下 _current_code
        single = DiagnosticResult(
            code="P0300",
            knowledge={"description": "Misfire", "severity": "high", "system": "engine",
                       "code_type": "powertrain"},
            ai_suggestion=None, ai_available=False,
        )
        self.panel.show_result(single)
        assert self.panel._current_code == "P0300"

        multi = MultiCodeDiagnosticResult(
            codes=["P0300", "P0171"], results=[r1], ai_suggestion=None, ai_available=False,
        )
        self.panel.show_multi_code_result(multi)
        assert self.panel._current_code is None
        # 症状录入区显示"暂无记录"（多码不支持单码症状录入）
        assert "暂无记录" in self.panel.symptom_display.text()
        assert not self.panel.symptom_btn.isEnabled()


# ── Bug 4: _on_tool_result 死代码 ──


class TestAgentChatToolResult:
    """_on_tool_result 移除死代码后行为不变"""

    def test_on_tool_result_appends_message(self):
        from src.ui.agent_chat import AgentChatPanel
        panel = AgentChatPanel.__new__(AgentChatPanel)
        panel._append_message = MagicMock()
        panel._on_tool_result("lookup_code", "some long result summary")
        panel._append_message.assert_called_once_with(
            "system", "✅ lookup_code 查询完成"
        )


# ── v3.4.3: parse_fault_codes 支持 EV 码 ──


class TestParseFaultCodesEV:
    """主诊断输入支持 EV-XXX-NNN 格式"""

    def test_single_ev_code(self):
        from src.engine.diagnostic import parse_fault_codes
        assert parse_fault_codes("EV-BMS-001") == ["EV-BMS-001"]

    def test_multi_ev_codes(self):
        from src.engine.diagnostic import parse_fault_codes
        assert parse_fault_codes("EV-BMS-001, EV-MOTOR-002") == [
            "EV-BMS-001", "EV-MOTOR-002",
        ]

    def test_mixed_ev_and_standard(self):
        from src.engine.diagnostic import parse_fault_codes
        assert parse_fault_codes("EV-BMS-001 P0300") == ["EV-BMS-001", "P0300"]

    def test_ev_code_lowercase(self):
        from src.engine.diagnostic import parse_fault_codes
        assert parse_fault_codes("ev-bms-001") == ["EV-BMS-001"]

    def test_ev_code_deduplicated(self):
        from src.engine.diagnostic import parse_fault_codes
        assert parse_fault_codes("EV-BMS-001 ev-bms-001") == ["EV-BMS-001"]

    def test_ev_code_embedded_in_text(self):
        from src.engine.diagnostic import parse_fault_codes
        assert parse_fault_codes("故障 EV-BMS-001 绝缘报警") == ["EV-BMS-001"]

    def test_standard_code_not_broken(self):
        from src.engine.diagnostic import parse_fault_codes
        assert parse_fault_codes("P0A0F P0300 B001A") == ["P0A0F", "P0300", "B001A"]

