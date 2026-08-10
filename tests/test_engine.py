"""
诊断引擎和知识库测试
"""

import os
import sys
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.database.schema import (
    CREATE_TABLE_OBD_CODES, CREATE_INDEX_CODE, CREATE_INDEX_SYSTEM,
    CREATE_TABLE_HISTORY, CREATE_INDEX_HISTORY_CODE, CREATE_INDEX_HISTORY_TIME,
    CREATE_TABLE_VEHICLE_MODELS, CREATE_INDEX_VEHICLE_MAKE, CREATE_INDEX_VEHICLE_MODEL
)
from src.database.db_manager import DatabaseManager
from src.engine.knowledge_base import KnowledgeBase
from src.engine.diagnostic import DiagnosticEngine


def _setup_test_db(db_path):
    """创建测试数据库并插入测试数据"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(CREATE_TABLE_OBD_CODES)
    cursor.execute(CREATE_INDEX_CODE)
    cursor.execute(CREATE_INDEX_SYSTEM)
    cursor.execute(CREATE_TABLE_HISTORY)
    cursor.execute(CREATE_INDEX_HISTORY_CODE)
    cursor.execute(CREATE_INDEX_HISTORY_TIME)
    cursor.execute(CREATE_TABLE_VEHICLE_MODELS)
    cursor.execute(CREATE_INDEX_VEHICLE_MAKE)
    cursor.execute(CREATE_INDEX_VEHICLE_MODEL)

    # 传统故障码
    cursor.execute("""
        INSERT INTO obd_codes (code, system, code_type, description, detail,
                               severity, common_causes, diagnostic_steps, related_codes, symptoms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "P0300", "P", "generic", "随机/多缸失火", "ECU检测到多个气缸失火",
        "high",
        json.dumps(["火花塞故障", "点火线圈故障"], ensure_ascii=False),
        json.dumps(["第一步：读取冻结帧", "第二步：检查火花塞"], ensure_ascii=False),
        "P0301,P0302",
        json.dumps(["发动机抖动"], ensure_ascii=False)
    ))

    cursor.execute("""
        INSERT INTO obd_codes (code, system, code_type, description, detail,
                               severity, common_causes, diagnostic_steps, related_codes, symptoms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "B1100", "B", "manufacturer", "左前门锁执行器电路故障", "门锁电机电路异常",
        "low",
        json.dumps(["门锁执行器故障"], ensure_ascii=False),
        json.dumps(["第一步：检查门锁开关"], ensure_ascii=False),
        "B1101",
        json.dumps(["车门无法上锁"], ensure_ascii=False)
    ))

    # 新能源故障码
    cursor.execute("""
        INSERT INTO obd_codes (code, system, code_type, description, detail,
                               severity, common_causes, diagnostic_steps, related_codes, symptoms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "P0A00", "P", "generic", "混合动力电池组电压异常", "BMS检测到电池组总电压超出正常范围",
        "critical",
        json.dumps(["电池单体电压不一致", "高压接触器接触不良"], ensure_ascii=False),
        json.dumps(["读取BMS数据流", "检查单体电压极差"], ensure_ascii=False),
        "P0A01,P0A02",
        json.dumps(["仪表显示电池故障灯", "动力输出受限"], ensure_ascii=False)
    ))

    # 车型数据
    cursor.execute("""
        INSERT INTO vehicle_models (make, model, year_start, year_end, powertrain,
                                    battery_type, motor_type, common_codes, known_issues, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "比亚迪", "秦PLUS EV", 2021, None, "BEV",
        "磷酸铁锂", "永磁同步",
        json.dumps(["P0A00", "P0A01", "P0A0E"], ensure_ascii=False),
        json.dumps(["冬季续航衰减明显"], ensure_ascii=False),
        "紧凑型轿车"
    ))

    cursor.execute("""
        INSERT INTO vehicle_models (make, model, year_start, year_end, powertrain,
                                    battery_type, motor_type, common_codes, known_issues, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "特斯拉", "Model 3", 2019, None, "BEV",
        "三元锂", "永磁同步",
        json.dumps(["P0A00", "P0A01", "P0A32"], ensure_ascii=False),
        json.dumps(["悬挂异响"], ensure_ascii=False),
        "中型轿车"
    ))

    conn.commit()
    conn.close()


class TestParseFaultCodes(unittest.TestCase):
    """parse_fault_codes 故障码解析测试"""

    def test_simple_codes(self):
        """纯数字故障码"""
        from src.engine.diagnostic import parse_fault_codes
        self.assertEqual(parse_fault_codes("P0300 P0171 C1201 U0100"),
                         ["P0300", "P0171", "C1201", "U0100"])

    def test_hex_codes(self):
        """含十六进制字母的故障码（EV 码 P0A00/P0A0F 等）"""
        from src.engine.diagnostic import parse_fault_codes
        self.assertEqual(parse_fault_codes("P0A0F P0A1F B001A U01A6"),
                         ["P0A0F", "P0A1F", "B001A", "U01A6"])

    def test_mixed_with_text(self):
        """中文/英文混杂输入"""
        from src.engine.diagnostic import parse_fault_codes
        self.assertEqual(parse_fault_codes("请检查 P0300 和 P0A0F"),
                         ["P0300", "P0A0F"])

    def test_deduplicate_preserve_order(self):
        """去重并保持顺序"""
        from src.engine.diagnostic import parse_fault_codes
        self.assertEqual(parse_fault_codes("P0300 p0300 P0171"),
                         ["P0300", "P0171"])

    def test_empty_input(self):
        """空输入"""
        from src.engine.diagnostic import parse_fault_codes
        self.assertEqual(parse_fault_codes(""), [])
        self.assertEqual(parse_fault_codes("   "), [])

    def test_invalid_input(self):
        """无有效故障码"""
        from src.engine.diagnostic import parse_fault_codes
        self.assertEqual(parse_fault_codes("hello world"), [])


class TestKnowledgeBase(unittest.TestCase):
    """KnowledgeBase 测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        _setup_test_db(self.db_path)

        DatabaseManager._instance = None
        DatabaseManager._instance_lock = __import__('threading').Lock()
        self.db = DatabaseManager(db_path=self.db_path)
        self.kb = KnowledgeBase(db=self.db)

    def tearDown(self):
        DatabaseManager._instance = None
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_lookup_p0300(self):
        """测试查询 P0300"""
        result = self.kb.lookup("P0300")
        self.assertIsNotNone(result)
        self.assertEqual(result["code"], "P0300")
        self.assertEqual(result["description"], "随机/多缸失火")
        self.assertIsInstance(result["common_causes"], list)
        self.assertEqual(len(result["common_causes"]), 2)
        self.assertIsInstance(result["diagnostic_steps"], list)
        self.assertEqual(len(result["diagnostic_steps"]), 2)

    def test_lookup_b1100(self):
        """测试查询 B1100"""
        result = self.kb.lookup("B1100")
        self.assertIsNotNone(result)
        self.assertEqual(result["code"], "B1100")
        self.assertEqual(result["system"], "B")

    def test_lookup_ev_code_p0a00(self):
        """测试查询新能源故障码 P0A00"""
        result = self.kb.lookup("P0A00")
        self.assertIsNotNone(result)
        self.assertEqual(result["code"], "P0A00")
        self.assertEqual(result["severity"], "critical")
        self.assertIn("电池", result["description"])

    def test_lookup_not_found(self):
        """测试查询不存在的故障码"""
        result = self.kb.lookup("P9999")
        self.assertIsNone(result)

    def test_search(self):
        """测试搜索"""
        results = self.kb.search("失火")
        self.assertGreater(len(results), 0)

    def test_search_ev(self):
        """测试搜索新能源故障码"""
        results = self.kb.search("电池")
        self.assertGreater(len(results), 0)

    def test_get_suggestions(self):
        """测试自动补全"""
        suggestions = self.kb.get_suggestions("P03")
        self.assertIn("P0300", suggestions)

    def test_record_symptoms(self):
        """测试记录现象"""
        success = self.kb.record_symptoms("P0300", "加速抖动")
        self.assertTrue(success)

        symptoms = self.kb.get_symptoms("P0300")
        self.assertIn("加速抖动", symptoms)

    def test_get_severity_info(self):
        """测试严重程度信息"""
        info = self.kb.get_severity_info("high")
        self.assertEqual(info["label"], "高")
        self.assertIn("color", info)

    def test_get_system_info(self):
        """测试系统信息"""
        info = self.kb.get_system_info("P")
        self.assertEqual(info["name"], "动力总成")

        info = self.kb.get_system_info("B")
        self.assertEqual(info["name"], "车身")

    def test_get_system_info_ev(self):
        """测试新能源系统信息"""
        info = self.kb.get_system_info("EV-BMS")
        self.assertEqual(info["name"], "新能源动力")
        self.assertIn("⚡", info["icon"])

    # ── 车型数据库测试 ──

    def test_get_vehicle_makes(self):
        """测试获取品牌列表"""
        makes = self.kb.get_vehicle_makes()
        self.assertIsInstance(makes, list)
        self.assertIn("比亚迪", makes)
        self.assertIn("特斯拉", makes)

    def test_get_models_by_make(self):
        """测试获取品牌车型列表"""
        models = self.kb.get_models_by_make("比亚迪")
        self.assertGreater(len(models), 0)
        self.assertEqual(models[0]["model"], "秦PLUS EV")

    def test_get_models_by_make_empty(self):
        """测试获取不存在品牌的车型"""
        models = self.kb.get_models_by_make("不存在的品牌")
        self.assertEqual(len(models), 0)

    def test_get_vehicle_info(self):
        """测试获取车型详情"""
        info = self.kb.get_vehicle_info("比亚迪", "秦PLUS EV")
        self.assertIsNotNone(info)
        self.assertEqual(info["make"], "比亚迪")
        self.assertEqual(info["model"], "秦PLUS EV")
        self.assertEqual(info["powertrain"], "BEV")
        self.assertIsInstance(info["common_codes"], list)
        self.assertIsInstance(info["known_issues"], list)

    def test_get_vehicle_info_not_found(self):
        """测试获取不存在车型信息"""
        info = self.kb.get_vehicle_info("比亚迪", "不存在的车型")
        self.assertIsNone(info)

    def test_get_common_codes_for_vehicle(self):
        """测试获取车型常见故障码"""
        codes = self.kb.get_common_codes_for_vehicle("比亚迪", "秦PLUS EV")
        self.assertIsInstance(codes, list)
        self.assertIn("P0A00", codes)


class TestDiagnosticEngine(unittest.TestCase):
    """DiagnosticEngine 测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        _setup_test_db(self.db_path)

        DatabaseManager._instance = None
        DatabaseManager._instance_lock = __import__('threading').Lock()
        self.db = DatabaseManager(db_path=self.db_path)
        self.kb = KnowledgeBase(db=self.db)

        # 创建 mock LLM，避免实际调用 Ollama
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = False
        self.mock_llm = mock_llm
        self.engine = DiagnosticEngine(knowledge_base=self.kb, llm=mock_llm)

    def tearDown(self):
        DatabaseManager._instance = None
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_diagnose_with_knowledge(self):
        """测试有知识库数据的诊断"""
        result = self.engine.diagnose("P0300")
        self.assertTrue(result.has_knowledge())
        self.assertEqual(result.code, "P0300")
        self.assertIsNotNone(result.knowledge)

    def test_diagnose_without_knowledge(self):
        """测试无知识库数据的诊断"""
        result = self.engine.diagnose("P9999")
        self.assertFalse(result.has_knowledge())
        self.assertEqual(result.code, "P9999")

    def test_diagnose_code_uppercase(self):
        """测试故障码自动大写"""
        result = self.engine.diagnose("p0300")
        self.assertEqual(result.code, "P0300")

    def test_diagnose_ev_code(self):
        """测试新能源故障码诊断"""
        result = self.engine.diagnose("P0A00")
        self.assertTrue(result.has_knowledge())
        self.assertEqual(result.code, "P0A00")
        self.assertEqual(result.knowledge["severity"], "critical")

    def test_search_codes(self):
        """测试搜索故障码"""
        results = self.engine.search_codes("失火")
        self.assertGreater(len(results), 0)

    def test_check_database_status(self):
        """测试数据库状态检查"""
        status = self.engine.check_database_status()
        self.assertTrue(status["exists"])
        self.assertGreater(status["total_codes"], 0)

    # ── 单码 AI 路径 ──

    def test_diagnose_ai_available(self):
        """AI 可用时返回建议"""
        self.mock_llm.is_available.return_value = True
        self.mock_llm.get_diagnostic_suggestion.return_value = "AI 排查建议"
        result = self.engine.diagnose("P0300")
        self.assertTrue(result.has_ai())
        self.assertEqual(result.ai_suggestion, "AI 排查建议")
        self.assertTrue(result.ai_available)

    def test_diagnose_ai_exception(self):
        """AI 调用抛异常 → 降级为警告"""
        self.mock_llm.is_available.return_value = True
        self.mock_llm.get_diagnostic_suggestion.side_effect = RuntimeError("连接失败")
        result = self.engine.diagnose("P0300")
        self.assertFalse(result.ai_available)
        self.assertIn("暂时不可用", result.ai_suggestion)

    def test_diagnose_has_ai_false(self):
        """无 AI 建议时 has_ai 返回 False"""
        result = self.engine.diagnose("P0300")
        self.assertFalse(result.has_ai())

    def test_diagnose_has_ai_requires_suggestion(self):
        """ai_available 为 True 但建议为 None 时 has_ai 为 False"""
        result = self.engine.diagnose("P0300")
        result.ai_available = True
        self.assertFalse(result.has_ai())

    # ── 多码诊断 ──

    def test_diagnose_multiple_with_knowledge(self):
        """多码诊断：两个码都有知识库结果"""
        result = self.engine.diagnose_multiple(["P0300", "B1100"])
        self.assertTrue(result.has_knowledge())
        self.assertEqual(len(result.results), 2)
        self.assertTrue(result.results[0].has_knowledge())
        self.assertTrue(result.results[1].has_knowledge())

    def test_diagnose_multiple_mixed_knowledge(self):
        """多码诊断：部分码无知识库结果"""
        result = self.engine.diagnose_multiple(["P0300", "P9999"])
        self.assertTrue(result.results[0].has_knowledge())
        self.assertFalse(result.results[1].has_knowledge())

    def test_diagnose_multiple_ai_available(self):
        """AI 可用时多码综合分析"""
        self.mock_llm.is_available.return_value = True
        self.mock_llm.get_multi_code_analysis.return_value = "综合建议"
        result = self.engine.diagnose_multiple(["P0300", "B1100"])
        self.assertTrue(result.has_ai())
        self.assertEqual(result.ai_suggestion, "综合建议")
        # knowledge_list 应只含库中存在的码
        called = self.mock_llm.get_multi_code_analysis.call_args
        knowledge_list = called[1]["knowledge_list"]
        self.assertEqual(len(knowledge_list), 2)

    def test_diagnose_multiple_symptom_context(self):
        """多码诊断携带症状上下文 → 存入结果并透传给 AI"""
        self.mock_llm.is_available.return_value = True
        self.mock_llm.get_multi_code_analysis.return_value = "对症建议"
        ctx = "子系统：电池系统\n故障现象：充不进电\n具体表现：完全无法启动充电"
        result = self.engine.diagnose_multiple(["P0300"], additional_info=ctx)
        self.assertEqual(result.symptom_context, ctx)
        called = self.mock_llm.get_multi_code_analysis.call_args
        self.assertEqual(called[1]["additional_info"], ctx)
        # AI 不可用时症状上下文仍保留（供结果面板展示）
        self.mock_llm.is_available.return_value = False
        result2 = self.engine.diagnose_multiple(["P0300"], additional_info=ctx)
        self.assertEqual(result2.symptom_context, ctx)
        self.assertFalse(result2.has_ai())

    def test_diagnose_multiple_priority_codes(self):
        """多码诊断携带高疑似候选码 → 存入结果并透传给 AI"""
        self.mock_llm.is_available.return_value = True
        self.mock_llm.get_multi_code_analysis.return_value = "综合建议"
        priority = ["EV-BMS-006", "EV-BMS-015"]
        result = self.engine.diagnose_multiple(["EV-BMS-006", "EV-BMS-015", "EV-BMS-041"],
                                               additional_info="电量跳变", priority_codes=priority)
        self.assertEqual(result.priority_codes, priority)
        called = self.mock_llm.get_multi_code_analysis.call_args
        self.assertEqual(called[1]["priority_codes"], priority)

    def test_diagnose_multiple_priority_codes_default_empty(self):
        """未指定高疑似候选码时默认为空列表"""
        self.mock_llm.is_available.return_value = False
        result = self.engine.diagnose_multiple(["P0300"])
        self.assertEqual(result.priority_codes, [])

    def test_diagnose_multiple_ai_exception(self):
        """AI 综合分析抛异常 → 降级"""
        self.mock_llm.is_available.return_value = True
        self.mock_llm.get_multi_code_analysis.side_effect = RuntimeError("boom")
        result = self.engine.diagnose_multiple(["P0300"])
        self.assertFalse(result.ai_available)
        self.assertIn("暂时不可用", result.ai_suggestion)

    def test_diagnose_multiple_has_ai_false(self):
        """无 AI 建议时多码 has_ai 为 False"""
        result = self.engine.diagnose_multiple(["P0300"])
        self.assertFalse(result.has_ai())

    def test_diagnose_multiple_code_uppercase(self):
        """多码诊断自动转大写"""
        result = self.engine.diagnose_multiple(["p0300"])
        self.assertEqual(result.codes[0], "p0300")
        self.assertEqual(result.results[0].code, "p0300")
        self.assertTrue(result.results[0].has_knowledge())

    def test_get_auto_complete(self):
        """测试自动补全"""
        suggestions = self.engine.get_auto_complete("P03")
        self.assertIn("P0300", suggestions)


if __name__ == "__main__":
    unittest.main()
