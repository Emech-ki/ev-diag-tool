"""
三电诊断 UI 测试（v3.5.0，offscreen）

覆盖:
- ThreeElectricPanel 初始化（子系统按钮/子页堆栈/默认选中）
- 子系统切换
- ElectricSystemPage 向导流程（reset → group → option → 诊断触发）
- _stop_worker 生命周期安全
- refresh_theme 不报错
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from src.engine.diagnostic import DiagnosticEngine
from src.ui.three_electric_panel import ThreeElectricPanel, ElectricSystemPage


def _make_engine():
    engine = DiagnosticEngine()
    engine.llm = MagicMock()
    engine.llm.is_available.return_value = False
    return engine


class TestThreeElectricPanelInit(unittest.TestCase):
    """面板初始化"""

    def setUp(self):
        self.panel = ThreeElectricPanel(_make_engine())

    def test_creates_three_pages(self):
        self.assertEqual(sorted(self.panel.pages.keys()), ["battery", "motor", "vcu"])

    def test_buttons_exist(self):
        self.assertEqual(self.panel._btn_group.buttons().__len__(), 3)

    def test_default_selected_battery(self):
        self.assertEqual(self.panel._stack.currentWidget(), self.panel.pages["battery"])

    def test_each_page_has_result_panel(self):
        for page in self.panel.pages.values():
            self.assertIsNotNone(page.result_panel)

    def test_each_page_has_inner_tabs(self):
        for page in self.panel.pages.values():
            self.assertEqual(page._inner_tabs.count(), 3)


class TestThreeElectricPanelSwitch(unittest.TestCase):
    """子系统切换"""

    def setUp(self):
        self.panel = ThreeElectricPanel(_make_engine())

    def test_switch_to_vcu(self):
        self.panel._switch_to("vcu")
        self.assertEqual(self.panel._stack.currentWidget(), self.panel.pages["vcu"])

    def test_switch_to_unknown_noop(self):
        self.panel._switch_to("nope")
        self.assertEqual(self.panel._stack.currentWidget(), self.panel.pages["battery"])


class TestElectricSystemPageWizard(unittest.TestCase):
    """向导流程"""

    def setUp(self):
        self.page = ElectricSystemPage(_make_engine(), "battery")

    def test_overview_rendered(self):
        self.assertIn("250", self.page._stats_label.text())
        html = self.page._common_browser.toHtml()
        self.assertIn("EV-BMS", html)

    def test_inner_tabs_layout(self):
        """内嵌 Tab：快速排查 / 系统概览 / 诊断结果"""
        self.assertEqual(self.page._inner_tabs.count(), 3)
        self.assertEqual(self.page._inner_tabs.tabText(0), "快速排查")
        self.assertEqual(self.page._inner_tabs.tabText(1), "系统概览")
        self.assertEqual(self.page._inner_tabs.tabText(2), "诊断结果")

    def test_page_is_scrollable(self):
        """页面级滚动：窗口过小时内部内容不压缩，改为滚轮滚动整页"""
        from PyQt6.QtWidgets import QScrollArea
        self.assertIsInstance(self.page._page_scroll, QScrollArea)
        self.assertTrue(self.page._page_scroll.widgetResizable())
        self.assertIsNotNone(self.page._page_scroll.widget())

    def test_inner_tabs_min_height(self):
        """内嵌 Tab 保留可用高度，更矮时由页面滚动条接管"""
        self.assertGreaterEqual(self.page._inner_tabs.minimumHeight(), 300)

    def test_small_window_enables_scroll(self):
        """小窗口下页面出现垂直滚动条"""
        self.page.resize(900, 320)
        self.page.show()
        QApplication.processEvents()
        sb = self.page._page_scroll.verticalScrollBar()
        self.assertGreater(sb.maximum(), 0)
        self.page.close()

    def test_default_tab_is_wizard(self):
        self.assertEqual(self.page._inner_tabs.currentIndex(), 0)

    def test_guide_banner_present(self):
        self.assertIn("使用方法", self.page._guide_banner_text.text())
        self.assertIn("诊断结果", self.page._guide_banner_text.text())

    def test_step_indicator_initial(self):
        self.assertIn("1/3", self.page._step_label.text())

    def test_initial_state_group_buttons(self):
        self.assertIsNone(self.page._current_group)
        self.assertEqual(self.page._guide.get("name"), "电池系统")

    def test_show_group_sets_question(self):
        group = self.page._guide["symptom_groups"][0]
        self.page._show_group(group)
        self.assertEqual(self.page._current_group, group)
        self.assertIn(group["question"], self.page._wizard_hint.text())
        self.assertIn("2/3", self.page._step_label.text())

    def test_show_option_sets_hint_and_diagnosis_button(self):
        group = self.page._guide["symptom_groups"][0]
        option = group["options"][0]
        self.page._show_option(group, option)
        self.assertEqual(self.page._current_option, option)
        hint = self.page._wizard_hint.text()
        self.assertIn(option["label"], hint)
        self.assertIn(group["final_hint"], hint)
        self.assertIn("3/3", self.page._step_label.text())

    def test_reset_wizard_clears_state(self):
        group = self.page._guide["symptom_groups"][0]
        self.page._show_option(group, group["options"][0])
        self.page._reset_wizard()
        self.assertIsNone(self.page._current_group)
        self.assertIsNone(self.page._current_option)
        self.assertIn("1/3", self.page._step_label.text())

    @patch("src.ui.three_electric_panel.ThreeElectricDiagnoseWorker")
    def test_start_diagnosis_creates_worker(self, MockWorker):
        group = self.page._guide["symptom_groups"][0]
        option = group["options"][0]
        self.page._show_option(group, option)
        self.page._start_diagnosis(option["candidate_codes"])
        self.assertEqual(MockWorker.call_args[0][0], self.page.engine)
        self.assertEqual(MockWorker.call_args[0][1], option["candidate_codes"])

    @patch("src.ui.three_electric_panel.ThreeElectricDiagnoseWorker")
    def test_start_diagnosis_passes_symptom_context(self, MockWorker):
        """开始诊断时携带症状上下文（现象/具体表现/排查提示），供 AI 对症下药"""
        group = self.page._guide["symptom_groups"][0]
        option = group["options"][0]
        self.page._show_option(group, option)
        self.page._start_diagnosis(option["candidate_codes"])
        ctx = MockWorker.call_args[0][2]
        self.assertIn(self.page._overview["name"], ctx)
        self.assertIn(group["label"], ctx)
        self.assertIn(option["label"], ctx)
        self.assertIn(group["final_hint"], ctx)

    @patch("src.ui.three_electric_panel.ThreeElectricDiagnoseWorker")
    def test_result_shows_symptom_banner(self, MockWorker):
        """诊断结果知识库区展示「诊断对象」症状横幅"""
        group = self.page._guide["symptom_groups"][0]
        option = group["options"][0]
        self.page._show_option(group, option)
        self.page._start_diagnosis(option["candidate_codes"])
        ctx = MockWorker.call_args[0][2]

        result = self.page.engine.diagnose_multiple(
            codes=option["candidate_codes"], additional_info=ctx
        )
        self.page._on_diagnose_finished(result)
        html = self.page.result_panel.knowledge_browser.toHtml()
        self.assertIn("诊断对象", html)
        self.assertIn("故障现象", html)

    @patch("src.ui.three_electric_panel.ThreeElectricDiagnoseWorker")
    def test_start_diagnosis_switches_to_result_tab(self, MockWorker):
        """点击开始诊断后自动切换到「诊断结果」页"""
        group = self.page._guide["symptom_groups"][0]
        option = group["options"][0]
        self.page._show_option(group, option)
        self.assertEqual(self.page._inner_tabs.currentIndex(), 0)
        self.page._start_diagnosis(option["candidate_codes"])
        self.assertEqual(self.page._inner_tabs.currentIndex(), 2)

    def test_stop_worker_no_worker_safe(self):
        self.page._stop_worker()  # 不应抛异常

    def test_stop_worker_with_running_worker(self):
        from src.ui.three_electric_panel import ThreeElectricDiagnoseWorker
        worker = ThreeElectricDiagnoseWorker(_make_engine(), ["EV-VCU-001"])
        self.page.worker = worker
        self.page._stop_worker()
        self.assertIsNone(self.page.worker)


class TestThreeElectricPageTheme(unittest.TestCase):
    """refresh_theme"""

    def setUp(self):
        self.page = ElectricSystemPage(_make_engine(), "battery")
        self.panel = ThreeElectricPanel(_make_engine())

    def test_page_refresh_theme(self):
        self.page.refresh_theme()  # 不应抛异常

    def test_panel_refresh_theme(self):
        self.panel.refresh_theme()  # 不应抛异常


class TestThreeElectricPanelStopWorker(unittest.TestCase):
    """面板级 _stop_worker"""

    def test_stops_all_pages(self):
        panel = ThreeElectricPanel(_make_engine())
        for page in panel.pages.values():
            page.worker = MagicMock()
            page.worker.isRunning.return_value = False
        panel._stop_worker()
        for page in panel.pages.values():
            self.assertIsNone(page.worker)


if __name__ == "__main__":
    unittest.main()
