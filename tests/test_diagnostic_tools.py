"""
诊断工具集测试
覆盖 diagnostic_tools.py 全部 10 个工具实现函数
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.db_fixtures import setup_test_db, make_test_kb
from src.ai.diagnostic_tools import (
    register_diagnostic_tools,
    _load_expert_context,
    _lookup_code,
    _search_by_symptom,
    _get_vehicle_info,
    _get_related_codes,
    _get_diagnostic_steps,
    _get_wiring_info,
    _record_symptom,
    _get_common_fixes,
    _search_codes_by_system,
    _get_expert_context,
)


class TestDiagnosticTools(unittest.TestCase):
    """诊断工具实现函数测试（基于临时数据库）"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        setup_test_db(self.db_path)
        self.kb = make_test_kb(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def _parse(self, text):
        return json.loads(text)

    # ── 工具1: lookup_code ──

    def test_lookup_code_found(self):
        result = self._parse(_lookup_code(self.kb, " p0300 "))
        self.assertTrue(result["found"])
        self.assertEqual(result["code"], "P0300")
        self.assertEqual(result["severity"], "high")
        self.assertIsInstance(result["common_causes"], list)
        self.assertIsInstance(result["related_codes"], list)

    def test_lookup_code_not_found(self):
        result = self._parse(_lookup_code(self.kb, "P9999"))
        self.assertFalse(result["found"])
        self.assertIn("未找到", result["message"])

    # ── 工具2: search_by_symptom ──

    def test_search_by_symptom_empty_keyword(self):
        result = self._parse(_search_by_symptom(self.kb, "   "))
        self.assertIn("error", result)

    def test_search_by_symptom_found(self):
        result = self._parse(_search_by_symptom(self.kb, "失火"))
        self.assertTrue(result["found"])
        self.assertGreater(result["count"], 0)

    def test_search_by_symptom_mapping(self):
        """'抖动' 应被映射为 '缺火'（未命中即走未找到分支）"""
        result = self._parse(_search_by_symptom(self.kb, "怠速抖动"))
        self.assertEqual(result["keyword"], "缺火")
        self.assertFalse(result["found"])

    def test_search_by_symptom_not_found(self):
        result = self._parse(_search_by_symptom(self.kb, "不存在的症状词"))
        self.assertFalse(result["found"])
        self.assertIn("未找到", result["message"])

    # ── 工具3: get_vehicle_info ──

    def test_get_vehicle_info_found(self):
        result = self._parse(_get_vehicle_info(self.kb, "比亚迪", "秦PLUS EV"))
        self.assertTrue(result["found"])
        self.assertEqual(result["make"], "比亚迪")
        self.assertEqual(result["powertrain"], "BEV")
        self.assertIsInstance(result["common_codes"], list)

    def test_get_vehicle_info_make_exists_model_not(self):
        result = self._parse(_get_vehicle_info(self.kb, "比亚迪", "不存在的车型"))
        self.assertFalse(result["found"])
        self.assertIn("available_models", result)
        self.assertIn("秦PLUS EV", result["available_models"])

    def test_get_vehicle_info_make_not_found(self):
        result = self._parse(_get_vehicle_info(self.kb, "不存在的品牌", "某车型"))
        self.assertFalse(result["found"])
        self.assertIn("未找到品牌", result["message"])

    # ── 工具4: get_related_codes ──

    def test_get_related_codes_found(self):
        result = self._parse(_get_related_codes(self.kb, "P0300"))
        self.assertGreater(result["related_count"], 0)
        # P0301 不在库中 → 标注"未收录"
        descriptions = {r["code"]: r["description"] for r in result["related_codes"]}
        self.assertEqual(descriptions.get("P0301"), "未收录")

    def test_get_related_codes_no_related(self):
        result = self._parse(_get_related_codes(self.kb, "U0100"))
        self.assertEqual(result["related_codes"], [])
        self.assertIn("没有已知的关联故障码", result["message"])

    def test_get_related_codes_not_found(self):
        result = self._parse(_get_related_codes(self.kb, "P9999"))
        self.assertIn("error", result)

    # ── 工具5: get_diagnostic_steps ──

    def test_get_diagnostic_steps_found(self):
        result = self._parse(_get_diagnostic_steps(self.kb, "P0300"))
        self.assertEqual(len(result["diagnostic_steps"]), 2)
        self.assertEqual(result["severity"], "high")

    def test_get_diagnostic_steps_no_steps(self):
        result = self._parse(_get_diagnostic_steps(self.kb, "U0100"))
        self.assertEqual(result["diagnostic_steps"], [])
        self.assertIn("没有标准诊断步骤", result["message"])

    def test_get_diagnostic_steps_not_found(self):
        result = self._parse(_get_diagnostic_steps(self.kb, "P9999"))
        self.assertIn("error", result)

    # ── 工具6: get_wiring_info ──

    def test_get_wiring_info_traditional(self):
        result = self._parse(_get_wiring_info(self.kb, "P0300"))
        self.assertIn("动力总成系统", result["wiring_hint"])
        result_b = self._parse(_get_wiring_info(self.kb, "B1100"))
        self.assertIn("车身系统", result_b["wiring_hint"])

    def test_get_wiring_info_ev(self):
        result = self._parse(_get_wiring_info(self.kb, "EV-BMS-001"))
        self.assertIn("BMS", result["wiring_hint"])

    def test_get_wiring_info_not_found(self):
        result = self._parse(_get_wiring_info(self.kb, "P9999"))
        self.assertIn("error", result)

    # ── 工具7: record_symptom ──

    def test_record_symptom_empty(self):
        result = self._parse(_record_symptom(self.kb, "P0300", "  "))
        self.assertIn("error", result)

    def test_record_symptom_success(self):
        result = self._parse(_record_symptom(self.kb, "p0300", "加速异响"))
        self.assertTrue(result["success"])
        self.assertIn("加速异响", result["all_symptoms"])

    def test_record_symptom_code_not_found(self):
        result = self._parse(_record_symptom(self.kb, "P9999", "异响"))
        self.assertFalse(result["success"])

    # ── 工具8: get_common_fixes ──

    def test_get_common_fixes_found(self):
        result = self._parse(_get_common_fixes(self.kb, "P0300"))
        self.assertEqual(len(result["fixes_summary"]), 2)
        self.assertEqual(result["fixes_summary"][0]["issue"], "火花塞故障")
        self.assertEqual(result["fixes_summary"][0]["check_step"], "读取冻结帧")

    def test_get_common_fixes_mismatch_length(self):
        """原因多于步骤时，缺步骤的不含 check_step"""
        result = self._parse(_get_common_fixes(self.kb, "C1201"))
        self.assertEqual(len(result["fixes_summary"]), 3)
        self.assertNotIn("check_step", result["fixes_summary"][2])

    def test_get_common_fixes_not_found(self):
        result = self._parse(_get_common_fixes(self.kb, "P9999"))
        self.assertIn("error", result)

    # ── 工具9: search_codes_by_system ──

    def test_search_by_system_traditional(self):
        result = self._parse(_search_codes_by_system(self.kb, "P"))
        self.assertTrue(result["found"])
        self.assertGreater(result["count"], 0)

    def test_search_by_system_ev(self):
        result = self._parse(_search_codes_by_system(self.kb, "EV-BMS"))
        self.assertTrue(result["found"])
        self.assertEqual(result["codes"][0]["code"], "EV-BMS-001")

    def test_search_by_system_not_found(self):
        result = self._parse(_search_codes_by_system(self.kb, "EV-UNKNOWN"))
        self.assertFalse(result["found"])

    def test_search_by_system_fallback(self):
        """db.execute_query 抛异常 → 降级到 kb.search()"""
        kb = MagicMock()
        kb.db.execute_query.side_effect = RuntimeError("db error")
        kb.search.return_value = [{"code": "P0300", "description": "失火", "severity": "high"}]
        result = self._parse(_search_codes_by_system(kb, "P"))
        self.assertTrue(result["found"])

    # ── 工具10: get_expert_context ──

    def test_get_expert_context_known(self):
        result = self._parse(_get_expert_context(" BMS "))
        self.assertEqual(result["expert"], "bms")
        self.assertIn("name", result)
        self.assertIn("context", result)

    def test_get_expert_context_unknown(self):
        result = self._parse(_get_expert_context("unknown"))
        self.assertIn("error", result)
        self.assertIn("available", result)

    # ── 专家上下文缓存 ──

    def test_load_expert_context_cache(self):
        import src.ai.diagnostic_tools as diag_tools
        diag_tools._EXPERT_CONTEXT_CACHE = None
        first = _load_expert_context()
        self.assertGreater(len(first), 0)
        self.assertIn("bms", first)
        # 第二次读取命中缓存（同一对象）
        second = _load_expert_context()
        self.assertIs(first, second)
        diag_tools._EXPERT_CONTEXT_CACHE = None

    def test_load_expert_context_missing_file(self):
        import src.ai.diagnostic_tools as diag_tools
        with patch.object(diag_tools, "_EXPERT_CONTEXT_CACHE", None):
            with patch.object(diag_tools.Path, "exists", return_value=False):
                ctx = _load_expert_context()
        self.assertEqual(ctx, {})


class TestRegisterDiagnosticTools(unittest.TestCase):
    """注册函数测试（含 kb=None 自动创建）"""

    def test_register_with_explicit_kb(self):
        from src.ai.tools import ToolRegistry
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test.db")
        setup_test_db(db_path)
        kb = make_test_kb(db_path)
        try:
            registry = ToolRegistry()
            register_diagnostic_tools(registry, kb)
            self.assertEqual(len(registry), 10)
            result = registry.execute("lookup_code", {"code": "P0300"})
            self.assertIn("P0300", result)
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)
            os.rmdir(temp_dir)


if __name__ == "__main__":
    unittest.main()
