"""
数据库模块测试
"""

import os
import sys
import json
import sqlite3
import tempfile
import unittest

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.database.schema import (
    CREATE_TABLE_OBD_CODES, CREATE_INDEX_CODE, CREATE_INDEX_SYSTEM,
    CREATE_TABLE_HISTORY, CREATE_INDEX_HISTORY_CODE, CREATE_INDEX_HISTORY_TIME
)


class TestDatabaseManager(unittest.TestCase):
    """DatabaseManager 测试"""

    def setUp(self):
        """每个测试前创建临时数据库"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")

        # 创建测试数据库
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(CREATE_TABLE_OBD_CODES)
        cursor.execute(CREATE_INDEX_CODE)
        cursor.execute(CREATE_INDEX_SYSTEM)
        cursor.execute(CREATE_TABLE_HISTORY)
        cursor.execute(CREATE_INDEX_HISTORY_CODE)
        cursor.execute(CREATE_INDEX_HISTORY_TIME)

        # 插入测试数据
        cursor.execute("""
            INSERT INTO obd_codes (code, system, code_type, description, detail,
                                   severity, common_causes, diagnostic_steps, related_codes, symptoms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "P0300", "P", "generic", "随机/多缸失火", "ECU检测到多个气缸失火",
            "high",
            json.dumps(["火花塞故障", "点火线圈故障", "燃油系统问题"], ensure_ascii=False),
            json.dumps(["第一步：读取冻结帧数据", "第二步：检查火花塞"], ensure_ascii=False),
            "P0301,P0302,P0303",
            json.dumps(["发动机抖动", "动力不足"], ensure_ascii=False)
        ))

        cursor.execute("""
            INSERT INTO obd_codes (code, system, code_type, description, detail,
                                   severity, common_causes, diagnostic_steps, related_codes, symptoms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "B1100", "B", "manufacturer", "左前门锁执行器电路故障", "左前门锁电机电路异常",
            "low",
            json.dumps(["门锁执行器电机故障", "线路断路"], ensure_ascii=False),
            json.dumps(["第一步：检查门锁开关"], ensure_ascii=False),
            "B1101,B1102",
            json.dumps(["车门无法上锁", "门锁异响"], ensure_ascii=False)
        ))

        conn.commit()
        conn.close()

        # 重置单例，使用测试数据库
        from src.database.db_manager import DatabaseManager
        DatabaseManager._instance = None
        DatabaseManager._instance_lock = __import__('threading').Lock()
        self.db = DatabaseManager(db_path=self.db_path)

    def tearDown(self):
        """清理临时数据库"""
        from src.database.db_manager import DatabaseManager
        DatabaseManager._instance = None
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_query_by_code_found(self):
        """测试查询存在的故障码"""
        result = self.db.query_by_code("P0300")
        self.assertIsNotNone(result)
        self.assertEqual(result["code"], "P0300")
        self.assertEqual(result["system"], "P")
        self.assertEqual(result["severity"], "high")

    def test_query_by_code_not_found(self):
        """测试查询不存在的故障码"""
        result = self.db.query_by_code("P9999")
        self.assertIsNone(result)

    def test_query_by_code_case_insensitive(self):
        """测试查询不区分大小写"""
        result = self.db.query_by_code("p0300")
        self.assertIsNotNone(result)
        self.assertEqual(result["code"], "P0300")

    def test_search_codes(self):
        """测试模糊搜索"""
        results = self.db.search_codes("失火")
        self.assertGreater(len(results), 0)
        codes = [r["code"] for r in results]
        self.assertIn("P0300", codes)

    def test_search_codes_by_code(self):
        """测试按故障码搜索"""
        results = self.db.search_codes("B11")
        self.assertGreater(len(results), 0)
        codes = [r["code"] for r in results]
        self.assertIn("B1100", codes)

    def test_get_all_codes(self):
        """测试获取所有故障码"""
        codes = self.db.get_all_codes()
        self.assertEqual(len(codes), 2)
        code_list = [c[0] for c in codes]
        self.assertIn("P0300", code_list)
        self.assertIn("B1100", code_list)

    def test_get_total_count(self):
        """测试获取总数"""
        count = self.db.get_total_count()
        self.assertEqual(count, 2)

    def test_record_symptoms(self):
        """测试记录现象"""
        success = self.db.record_symptoms("P0300", "加速时抖动")
        self.assertTrue(success)

        symptoms = self.db.get_symptoms("P0300")
        self.assertIn("加速时抖动", symptoms)

    def test_record_symptoms_duplicate(self):
        """测试重复记录现象"""
        self.db.record_symptoms("P0300", "加速时抖动")
        self.db.record_symptoms("P0300", "加速时抖动")

        symptoms = self.db.get_symptoms("P0300")
        count = sum(1 for s in symptoms if s == "加速时抖动")
        self.assertEqual(count, 1)

    def test_record_symptoms_validation(self):
        """测试现象验证"""
        success = self.db.record_symptoms("P0300", "")
        self.assertFalse(success)

        success = self.db.record_symptoms("P0300", "   ")
        self.assertFalse(success)

    def test_parse_json_field(self):
        """测试 JSON 解析"""
        result = self.db.parse_json_field('["a", "b", "c"]')
        self.assertEqual(result, ["a", "b", "c"])

    def test_parse_json_field_empty(self):
        """测试空 JSON 解析"""
        result = self.db.parse_json_field("")
        self.assertEqual(result, [])

        result = self.db.parse_json_field(None)
        self.assertEqual(result, [])

    def test_parse_json_field_invalid(self):
        """测试无效 JSON 解析"""
        result = self.db.parse_json_field("not json")
        self.assertEqual(result, [])

    def test_database_exists(self):
        """测试数据库存在检查"""
        self.assertTrue(self.db.database_exists())

    def test_get_database_info(self):
        """测试获取数据库信息"""
        info = self.db.get_database_info()
        self.assertTrue(info["exists"])
        self.assertEqual(info["total_codes"], 2)

    def test_save_history(self):
        """测试保存历史记录"""
        success = self.db.save_history(
            code="P0300",
            vehicle_info="比亚迪秦",
            symptoms="抖动",
            knowledge_found=True,
            ai_suggestion="建议检查火花塞"
        )
        self.assertTrue(success)

    def test_get_history(self):
        """测试获取历史记录"""
        self.db.save_history(code="P0300", vehicle_info="比亚迪秦")
        self.db.save_history(code="B1100", vehicle_info="特斯拉")

        records = self.db.get_history()
        self.assertEqual(len(records), 2)

    def test_search_history(self):
        """测试搜索历史记录"""
        self.db.save_history(code="P0300", vehicle_info="比亚迪秦")
        self.db.save_history(code="B1100", vehicle_info="特斯拉")

        records = self.db.search_history("比亚迪")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["code"], "P0300")

    def test_clear_history(self):
        """测试清空历史"""
        self.db.save_history(code="P0300")
        self.db.save_history(code="B1100")

        success = self.db.clear_history()
        self.assertTrue(success)

        records = self.db.get_history()
        self.assertEqual(len(records), 0)


if __name__ == "__main__":
    unittest.main()
