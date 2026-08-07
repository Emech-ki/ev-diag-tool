"""
三电诊断 — 引擎层测试（v3.5.0）

覆盖:
- THREE_ELECTRIC 域映射完整性（battery/motor/vcu → 系统码）
- 向导 JSON 数据完整性（3 子系统 × 每组含问题/选项/候选码/final_hint）
- 向导候选码全部命中知识库真实故障码
- build_overview 覆盖统计（总数/有详情/高频码）
- ThreeElectricDiagnoseWorker 多码诊断（KB 链路，stub LLM）
"""

import sys
import os
import json
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.engine import three_electric
from src.engine.knowledge_base import KnowledgeBase

GUIDE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "seed", "three_electric_guide.json")

EXPECTED_SUBSYSTEMS = {
    "battery": {"EV-BMS", "EV-HV", "EV-OBC", "EV-DCDC", "EV-THERMAL"},
    "motor": {"EV-MOTOR", "EV-REGEN"},
    "vcu": {"EV-VCU"},
}


class TestThreeElectricMapping(unittest.TestCase):
    """THREE_ELECTRIC 域映射"""

    def test_subsystems_present(self):
        self.assertEqual(set(three_electric.THREE_ELECTRIC.keys()), set(EXPECTED_SUBSYSTEMS.keys()))

    def test_systems_mapping(self):
        for sub, systems in EXPECTED_SUBSYSTEMS.items():
            self.assertEqual(set(three_electric.get_systems_for(sub)), systems)

    def test_get_subsystems_order_and_fields(self):
        subs = three_electric.get_subsystems()
        self.assertEqual([s["key"] for s in subs], ["battery", "motor", "vcu"])
        for s in subs:
            self.assertIn("name", s)
            self.assertIn("icon", s)

    def test_unknown_subsystem_returns_empty(self):
        self.assertEqual(three_electric.get_systems_for("nope"), ())


class TestThreeElectricGuide(unittest.TestCase):
    """向导 JSON 数据完整性"""

    def setUp(self):
        with open(GUIDE_PATH, encoding="utf-8") as f:
            self.guide = json.load(f)

    def test_guide_has_three_subsystems(self):
        self.assertEqual(set(self.guide.keys()), set(EXPECTED_SUBSYSTEMS.keys()))
        for sub in self.guide:
            self.assertIn("name", self.guide[sub])
            self.assertIn("icon", self.guide[sub])

    def test_each_subsystem_has_3_plus_groups(self):
        for sub, data in self.guide.items():
            self.assertGreaterEqual(len(data["symptom_groups"]), 3, f"{sub} 症状流不足")

    def test_each_group_well_formed(self):
        for sub, data in self.guide.items():
            for g in data["symptom_groups"]:
                self.assertIn("id", g, f"{sub}")
                self.assertIn("label", g, f"{sub}")
                self.assertIn("question", g, f"{sub}")
                self.assertIn("final_hint", g, f"{sub}")
                self.assertGreaterEqual(len(g["options"]), 2, f"{sub}/{g['id']} 选项不足")
                for o in g["options"]:
                    self.assertIn("label", o, f"{sub}/{g['id']}")
                    self.assertTrue(o["candidate_codes"], f"{sub}/{g['id']} 候选码为空")

    def test_guide_loads_through_module(self):
        guide = three_electric.load_three_electric_guide()
        self.assertEqual(guide, self.guide)

    def test_get_guide_for_unknown_returns_empty(self):
        self.assertEqual(three_electric.get_guide_for("nope"), {})


class TestThreeElectricGuideCodesReachKB(unittest.TestCase):
    """向导候选码必须全部命中知识库真实故障码"""

    def test_all_candidate_codes_exist_in_db(self):
        kb = KnowledgeBase()
        real = {r["code"] for r in kb.get_codes_by_system_prefix("EV", limit=9999)}
        guide = three_electric.load_three_electric_guide()
        missing = []
        for sub, data in guide.items():
            for g in data["symptom_groups"]:
                for o in g["options"]:
                    for code in o["candidate_codes"]:
                        if code not in real:
                            missing.append((sub, g["id"], code))
        self.assertEqual(missing, [], f"向导候选码不在知识库: {missing}")


class TestThreeElectricOverview(unittest.TestCase):
    """build_overview 覆盖统计"""

    def setUp(self):
        self.kb = KnowledgeBase()

    def test_battery_overview_counts(self):
        ov = three_electric.build_overview(self.kb, "battery")
        self.assertEqual(ov["subsystem"], "battery")
        self.assertEqual(ov["total_codes"], 250)
        self.assertEqual(ov["codes_with_detail"], 250)
        self.assertEqual(len(ov["systems"]), 5)
        self.assertGreaterEqual(len(ov["common_codes"]), 1)

    def test_motor_overview_counts(self):
        ov = three_electric.build_overview(self.kb, "motor")
        self.assertEqual(ov["total_codes"], 100)
        self.assertEqual(ov["codes_with_detail"], 100)
        self.assertEqual(len(ov["systems"]), 2)

    def test_vcu_overview_counts(self):
        ov = three_electric.build_overview(self.kb, "vcu")
        self.assertEqual(ov["total_codes"], 50)
        self.assertEqual(ov["codes_with_detail"], 50)
        self.assertEqual(len(ov["systems"]), 1)
        self.assertEqual(ov["systems"][0]["system"], "EV-VCU")

    def test_unknown_subsystem_empty(self):
        ov = three_electric.build_overview(self.kb, "nope")
        self.assertEqual(ov["total_codes"], 0)
        self.assertEqual(ov["common_codes"], [])

    def test_common_codes_are_real(self):
        ov = three_electric.build_overview(self.kb, "vcu")
        real = {r["code"] for r in self.kb.get_codes_by_system_prefix("EV-VCU", limit=100)}
        for r in ov["common_codes"]:
            self.assertIn(r["code"], real)


class TestThreeElectricWorker(unittest.TestCase):
    """ThreeElectricDiagnoseWorker 多码诊断（stub LLM）"""

    def test_worker_runs_kb_diagnosis(self):
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QEventLoop
        app = QApplication.instance() or QApplication(sys.argv)

        from src.engine.diagnostic import DiagnosticEngine
        from src.ui.three_electric_panel import ThreeElectricDiagnoseWorker

        engine = DiagnosticEngine()
        engine.llm = MagicMock()
        engine.llm.is_available.return_value = False

        worker = ThreeElectricDiagnoseWorker(engine, ["EV-VCU-001", "EV-VCU-027"])
        loop = QEventLoop()
        result = {}
        worker.finished.connect(lambda r: (result.__setitem__("result", r), loop.quit()))
        worker.error.connect(lambda e: (result.__setitem__("error", e), loop.quit()))
        worker.start()
        loop.exec()

        if "error" in result:
            self.fail(f"worker error: {result['error']}")
        r = result["result"]
        self.assertEqual(r.codes, ["EV-VCU-001", "EV-VCU-027"])
        self.assertTrue(r.has_knowledge())
        for rr in r.results:
            self.assertIsNotNone(rr.knowledge)

    def test_worker_emits_error_on_exception(self):
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QEventLoop
        app = QApplication.instance() or QApplication(sys.argv)

        from src.engine.diagnostic import DiagnosticEngine
        from src.ui.three_electric_panel import ThreeElectricDiagnoseWorker

        engine = DiagnosticEngine()
        engine.diagnose_multiple = MagicMock(side_effect=RuntimeError("boom"))

        worker = ThreeElectricDiagnoseWorker(engine, ["EV-VCU-001"])
        loop = QEventLoop()
        result = {}
        worker.finished.connect(lambda r: (result.__setitem__("result", r), loop.quit()))
        worker.error.connect(lambda e: (result.__setitem__("error", e), loop.quit()))
        worker.start()
        loop.exec()
        self.assertIn("error", result)
        self.assertIn("boom", result["error"])

    def test_worker_forwards_symptom_context(self):
        """worker 把症状上下文透传给 diagnose_multiple"""
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QEventLoop
        app = QApplication.instance() or QApplication(sys.argv)

        from src.engine.diagnostic import DiagnosticEngine
        from src.ui.three_electric_panel import ThreeElectricDiagnoseWorker

        engine = DiagnosticEngine()
        engine.diagnose_multiple = MagicMock()
        engine.diagnose_multiple.return_value.has_knowledge.return_value = True
        engine.diagnose_multiple.return_value.codes = ["EV-BMS-001"]

        ctx = "子系统：电池系统\n故障现象：续航骤降\n具体表现：电量跳变"
        worker = ThreeElectricDiagnoseWorker(engine, ["EV-BMS-001"], symptom_context=ctx)
        loop = QEventLoop()
        result = {}
        worker.finished.connect(lambda r: (result.__setitem__("result", r), loop.quit()))
        worker.error.connect(lambda e: (result.__setitem__("error", e), loop.quit()))
        worker.start()
        loop.exec()

        self.assertNotIn("error", result)
        engine.diagnose_multiple.assert_called_once_with(codes=["EV-BMS-001"], additional_info=ctx)


if __name__ == "__main__":
    unittest.main()
