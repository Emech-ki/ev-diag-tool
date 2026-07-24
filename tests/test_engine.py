"""
诊断引擎和知识库测试
"""

import os
import sys
import json
import sqlite3
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.database.schema import (
    CREATE_TABLE_OBD_CODES, CREATE_INDEX_CODE, CREATE_INDEX_SYSTEM,
    CREATE_TABLE_HISTORY, CREATE_INDEX_HISTORY_CODE, CREATE_INDEX_HISTORY_TIME
)
from src.database.db_manager import DatabaseManager
from src.engine.knowledge_base import KnowledgeBase
from src.engine.diagnostic import DiagnosticEngine


class TestKnowledgeBase(unittest.TestCase):
    """KnowledgeBase 测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(CREATE_TABLE_OBD_CODES)
        cursor.execute(CREATE_INDEX_CODE)
        cursor.execute(CREATE_INDEX_SYSTEM)
        cursor.execute(CREATE_TABLE_HISTORY)
        cursor.execute(CREATE_INDEX_HISTORY_CODE)
        cursor.execute(CREATE_INDEX_HISTORY_TIME)

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

        conn.commit()
        conn.close()

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

    def test_lookup_not_found(self):
        """测试查询不存在的故障码"""
        result = self.kb.lookup("P9999")
        self.assertIsNone(result)

    def test_search(self):
        """测试搜索"""
        results = self.kb.search("失火")
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


class TestDiagnosticEngine(unittest.TestCase):
    """DiagnosticEngine 测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(CREATE_TABLE_OBD_CODES)
        cursor.execute(CREATE_INDEX_CODE)
        cursor.execute(CREATE_INDEX_SYSTEM)
        cursor.execute(CREATE_TABLE_HISTORY)
        cursor.execute(CREATE_INDEX_HISTORY_CODE)
        cursor.execute(CREATE_INDEX_HISTORY_TIME)

        cursor.execute("""
            INSERT INTO obd_codes (code, system, code_type, description, detail,
                                   severity, common_causes, diagnostic_steps, related_codes, symptoms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "P0300", "P", "generic", "随机/多缸失火", "ECU检测到多个气缸失火",
            "high",
            json.dumps(["火花塞故障"], ensure_ascii=False),
            json.dumps(["第一步：读取冻结帧"], ensure_ascii=False),
            "P0301",
            json.dumps(["发动机抖动"], ensure_ascii=False)
        ))

        conn.commit()
        conn.close()

        DatabaseManager._instance = None
        DatabaseManager._instance_lock = __import__('threading').Lock()
        self.db = DatabaseManager(db_path=self.db_path)
        self.kb = KnowledgeBase(db=self.db)
        self.engine = DiagnosticEngine(knowledge_base=self.kb, llm=None)

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

    def test_search_codes(self):
        """测试搜索故障码"""
        results = self.engine.search_codes("失火")
        self.assertGreater(len(results), 0)

    def test_check_database_status(self):
        """测试数据库状态检查"""
        status = self.engine.check_database_status()
        self.assertTrue(status["exists"])
        self.assertGreater(status["total_codes"], 0)


if __name__ == "__main__":
    unittest.main()
