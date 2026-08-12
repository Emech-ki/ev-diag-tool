"""
三电诊断 — 引擎层测试（v3.5.1）

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

    def test_expert_domains_match_mapping(self):
        """专家路由域映射 = THREE_ELECTRIC 单一真源"""
        domains = three_electric.get_expert_domains()
        self.assertEqual(set(domains.keys()), set(EXPECTED_SUBSYSTEMS.keys()))
        for sub, systems in EXPECTED_SUBSYSTEMS.items():
            self.assertEqual(set(domains[sub]), systems)

    def test_subsystem_for_system_routing(self):
        """按系统码前缀路由（EV-BMS-001 → battery）"""
        cases = {
            "EV-BMS-001": "battery",
            "EV-HV-002": "battery",
            "EV-OBC-003": "battery",
            "EV-DCDC-004": "battery",
            "EV-THERMAL-005": "battery",
            "EV-MOTOR-001": "motor",
            "EV-REGEN-002": "motor",
            "EV-VCU-003": "vcu",
        }
        for system, expected in cases.items():
            self.assertEqual(three_electric.get_subsystem_for_system(system), expected, system)

    def test_subsystem_for_system_unknown(self):
        self.assertIsNone(three_electric.get_subsystem_for_system("EV-AIRCON-001"))
        self.assertIsNone(three_electric.get_subsystem_for_system("P0300"))
        self.assertIsNone(three_electric.get_subsystem_for_system(""))

    def test_get_expert_name(self):
        self.assertEqual(three_electric.get_expert_name("battery"), "电池系统专家")
        self.assertEqual(three_electric.get_expert_name("motor"), "电机驱动专家")
        self.assertEqual(three_electric.get_expert_name("vcu"), "电控系统专家")
        self.assertEqual(three_electric.get_expert_name("nope"), "通用诊断专家")

    def test_get_expert_keywords_present(self):
        """每个子系统都有诊断关键词（专家路由消息匹配的单一真源）"""
        for sub in ("battery", "motor", "vcu"):
            self.assertTrue(three_electric.get_expert_keywords(sub),
                            f"{sub} 缺少关键词")
        self.assertEqual(three_electric.get_expert_keywords("nope"), ())

    def test_keywords_route_match(self):
        """关键词消息路由：电池/电机/电控关键词 → 对应子系统"""
        cases = {
            "电池充不进电": "battery",
            "电池单体电压高": "battery",
            "绝缘报警": "battery",
            "充电很慢": "battery",
            "电机异响": "motor",
            "扭矩传感器故障": "motor",
            "旋变信号异常": "motor",
            "整车无法上电": "vcu",
            "挡位挂不上": "vcu",
            "CAN 网络丢失": "vcu",
        }
        for msg, expected in cases.items():
            self.assertEqual(three_electric.match_keywords(msg), expected, msg)

    def test_keywords_route_unknown_general(self):
        self.assertIsNone(three_electric.match_keywords(""))
        self.assertIsNone(three_electric.match_keywords("冷车启动抖动"))


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
                    codes = three_electric.get_option_codes(o)
                    self.assertTrue(codes, f"{sub}/{g['id']} 候选码解析为空")
                    for code in codes:
                        self.assertIsInstance(code, str)
                        self.assertRegex(code, r"^EV-[A-Z-]+-\d{3}$")
                    weights = three_electric.get_option_weights(o)
                    self.assertEqual(set(weights.keys()), set(codes), f"{sub}/{g['id']} weight 与码不一致")
                    # 显式置信度在 (0, 100] 区间，且按 weight 降序
                    for w in weights.values():
                        self.assertTrue(0 < w <= 100, f"{sub}/{g['id']} weight 越界: {w}")
                    parsed_weights = [weights[c] for c in codes]
                    self.assertEqual(parsed_weights, sorted(parsed_weights, reverse=True),
                                     f"{sub}/{g['id']} 未按 weight 降序")

    def test_guide_loads_through_module(self):
        guide = three_electric.load_three_electric_guide()
        self.assertEqual(guide, self.guide)

    def test_get_guide_for_unknown_returns_empty(self):
        self.assertEqual(three_electric.get_guide_for("nope"), {})

    def test_get_option_codes_sorts_by_weight_desc(self):
        """对象式候选码按 weight 降序，旧式字符串按位置回退"""
        obj = {"candidate_codes": [
            {"code": "EV-BMS-006", "weight": 70},
            {"code": "EV-BMS-015", "weight": 95},
            {"code": "EV-BMS-041", "weight": 60},
        ]}
        self.assertEqual(three_electric.get_option_codes(obj),
                         ["EV-BMS-015", "EV-BMS-006", "EV-BMS-041"])
        self.assertEqual(three_electric.get_option_weights(obj),
                         {"EV-BMS-015": 95, "EV-BMS-006": 70, "EV-BMS-041": 60})

    def test_get_option_codes_legacy_strings(self):
        """旧式字符串数组也能解析（兼容降级）"""
        legacy = {"candidate_codes": ["EV-OBC-001", "EV-OBC-021", "EV-OBC-023"]}
        self.assertEqual(three_electric.get_option_codes(legacy),
                         ["EV-OBC-001", "EV-OBC-021", "EV-OBC-023"])
        weights = three_electric.get_option_weights(legacy)
        self.assertEqual(weights["EV-OBC-001"], 90)
        self.assertEqual(weights["EV-OBC-021"], 80)
        self.assertEqual(weights["EV-OBC-023"], 70)

    def test_get_option_codes_missing_field(self):
        self.assertEqual(three_electric.get_option_codes({}), [])
        self.assertEqual(three_electric.get_option_weights({}), {})


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
                    for code in three_electric.get_option_codes(o):
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
        engine.diagnose_multiple.assert_called_once_with(
            codes=["EV-BMS-001"], additional_info=ctx, priority_codes=[],
            priority_weights={}
        )

    def test_worker_forwards_priority_codes(self):
        """worker 把向导候选码顺序作为高疑似标记透传给 diagnose_multiple"""
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QEventLoop
        app = QApplication.instance() or QApplication(sys.argv)

        from src.engine.diagnostic import DiagnosticEngine
        from src.ui.three_electric_panel import ThreeElectricDiagnoseWorker

        engine = DiagnosticEngine()
        engine.diagnose_multiple = MagicMock()
        engine.diagnose_multiple.return_value.has_knowledge.return_value = True
        engine.diagnose_multiple.return_value.codes = ["EV-BMS-001"]

        worker = ThreeElectricDiagnoseWorker(
            engine, ["EV-BMS-001", "EV-BMS-015"],
            symptom_context="ctx",
            priority_codes=["EV-BMS-001", "EV-BMS-015"],
            priority_weights={"EV-BMS-001": 95, "EV-BMS-015": 85},
        )
        loop = QEventLoop()
        result = {}
        worker.finished.connect(lambda r: (result.__setitem__("result", r), loop.quit()))
        worker.error.connect(lambda e: (result.__setitem__("error", e), loop.quit()))
        worker.start()
        loop.exec()

        self.assertNotIn("error", result)
        engine.diagnose_multiple.assert_called_once_with(
            codes=["EV-BMS-001", "EV-BMS-015"],
            additional_info="ctx",
            priority_codes=["EV-BMS-001", "EV-BMS-015"],
            priority_weights={"EV-BMS-001": 95, "EV-BMS-015": 85},
        )


if __name__ == "__main__":
    unittest.main()
