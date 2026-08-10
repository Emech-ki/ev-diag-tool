"""
EV 系统码知识库测试（v3.4.3）

覆盖:
- ev_system_codes.csv 数据完整性（格式/唯一性/系统对齐/详情覆盖）
- seed 后可完整导入临时数据库
- 新增系统与 expert_context 路由域名对齐
- DiagnosticAgent._select_expert 对新增 EV 系统的路由
"""

import os
import sys
import csv
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

SEED_CSV = os.path.join(PROJECT_ROOT, "data", "seed", "ev_system_codes.csv")
EXPERT_JSON = os.path.join(PROJECT_ROOT, "data", "seed", "expert_context.json")

EXPECTED_SYSTEMS = {
    "EV-BMS", "EV-MOTOR", "EV-OBC", "EV-DCDC",
    "EV-THERMAL", "EV-HV", "EV-REGEN", "EV-VCU",
}


def _load_rows():
    with open(SEED_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TestEVSystemCodesCSV(unittest.TestCase):
    """ev_system_codes.csv 数据完整性"""

    def test_file_exists(self):
        self.assertTrue(os.path.exists(SEED_CSV))

    def test_columns_match_schema(self):
        with open(SEED_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.assertEqual(reader.fieldnames, [
                "code", "system", "code_type", "description", "detail", "severity",
                "common_causes", "diagnostic_steps", "related_codes", "symptoms",
            ])

    def test_code_format_and_unique(self):
        import re
        rows = _load_rows()
        self.assertGreater(len(rows), 0)
        codes = [r["code"] for r in rows]
        self.assertEqual(len(codes), len(set(codes)), "故障码重复")
        for c in codes:
            self.assertRegex(c, r"^EV-[A-Z]+-\d{3}$", f"格式错误: {c}")

    def test_system_is_known(self):
        rows = _load_rows()
        for r in rows:
            self.assertIn(r["system"], EXPECTED_SYSTEMS, f"未知系统: {r['system']}")

    def test_system_matches_code_prefix(self):
        rows = _load_rows()
        for r in rows:
            prefix = r["code"].rsplit("-", 1)[0]
            self.assertEqual(prefix, r["system"], f"system 与码前缀不一致: {r['code']}")

    def test_severity_valid(self):
        rows = _load_rows()
        valid = {"low", "medium", "high", "critical"}
        for r in rows:
            self.assertIn(r["severity"], valid, f"无效严重度: {r['code']}")

    def test_all_have_detail(self):
        rows = _load_rows()
        for r in rows:
            self.assertTrue(r.get("detail", "").strip(), f"缺少详情: {r['code']}")

    def test_all_have_causes_steps_symptoms(self):
        rows = _load_rows()
        for r in rows:
            self.assertIsInstance(json.loads(r["common_causes"]), list, f"原因格式错误: {r['code']}")
            self.assertIsInstance(json.loads(r["diagnostic_steps"]), list, f"步骤格式错误: {r['code']}")
            self.assertIsInstance(json.loads(r["symptoms"]), list, f"症状格式错误: {r['code']}")
            self.assertGreaterEqual(len(json.loads(r["common_causes"])), 3, f"原因过少: {r['code']}")
            self.assertGreaterEqual(len(json.loads(r["diagnostic_steps"])), 3, f"步骤过少: {r['code']}")

    def test_each_system_has_min_count(self):
        rows = _load_rows()
        counts = {}
        for r in rows:
            counts[r["system"]] = counts.get(r["system"], 0) + 1
        for sys_name in EXPECTED_SYSTEMS:
            self.assertGreaterEqual(counts.get(sys_name, 0), 50, f"{sys_name} 条数不足")

    def test_total_codes_ge_300(self):
        rows = _load_rows()
        self.assertGreaterEqual(len(rows), 300, f"EV 系统码总数不足: {len(rows)}")

    def test_total_codes_ge_400(self):
        rows = _load_rows()
        self.assertGreaterEqual(len(rows), 400, f"EV 系统码总数不足（三电含 EV-VCU）: {len(rows)}")


class TestEVSystemCodesSeedable(unittest.TestCase):
    """种子 CSV 可完整导入临时数据库"""

    def test_import_to_temp_db(self):
        if not os.path.exists(SEED_CSV):
            self.skipTest("ev_system_codes.csv 不存在")
        from src.database.schema import CREATE_TABLE_OBD_CODES

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        conn = sqlite3.connect(tmp.name)
        conn.execute(CREATE_TABLE_OBD_CODES)
        with open(SEED_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                conn.execute("""
                    INSERT OR REPLACE INTO obd_codes
                        (code, system, code_type, description, detail, severity,
                         common_causes, diagnostic_steps, related_codes, symptoms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row["code"], row["system"], row["code_type"], row["description"],
                    row["detail"], row["severity"], row["common_causes"],
                    row["diagnostic_steps"], row["related_codes"], row["symptoms"],
                ))
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM obd_codes").fetchone()[0]
        self.assertEqual(n, len(_load_rows()))
        conn.close()
        os.unlink(tmp.name)

    def test_lookup_roundtrip(self):
        """KnowledgeBase 能查到 EV 码（验证查询链路）"""
        if not os.path.exists(SEED_CSV):
            self.skipTest("ev_system_codes.csv 不存在")

        from src.database.db_manager import DatabaseManager
        from src.database.schema import CREATE_TABLE_OBD_CODES
        from src.engine.knowledge_base import KnowledgeBase

        # 保存并重置单例，避免污染其他测试
        saved_instance = getattr(DatabaseManager, "_instance", None)
        saved_lock = getattr(DatabaseManager, "_instance_lock", None)
        DatabaseManager._instance = None

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            db = DatabaseManager(db_path=tmp.name)
            conn = db.get_connection()
            conn.execute(CREATE_TABLE_OBD_CODES)
            with open(SEED_CSV, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    conn.execute("""
                        INSERT OR REPLACE INTO obd_codes
                            (code, system, code_type, description, detail, severity,
                             common_causes, diagnostic_steps, related_codes, symptoms)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row["code"], row["system"], row["code_type"], row["description"],
                        row["detail"], row["severity"], row["common_causes"],
                        row["diagnostic_steps"], row["related_codes"], row["symptoms"],
                    ))
            conn.commit()

            kb = KnowledgeBase(db)
            result = kb.lookup("EV-BMS-001")
            self.assertIsNotNone(result)
            self.assertEqual(result["system"], "EV-BMS")
            self.assertIn("severity", result)
            conn.close()
        finally:
            DatabaseManager._instance = saved_instance
            DatabaseManager._instance_lock = saved_lock
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)


class TestEVExpertRouting(unittest.TestCase):
    """新增 EV 系统与专家路由对齐"""

    def test_expert_domains_cover_new_systems(self):
        with open(EXPERT_JSON, encoding="utf-8") as f:
            ctx = json.load(f)
        all_domains = set()
        for expert in ctx.values():
            all_domains.update(expert.get("domains", []))
        for sys_name in EXPECTED_SYSTEMS:
            self.assertIn(sys_name, all_domains, f"系统 {sys_name} 无专家路由域名")

    def test_obc_dcdc_to_bms_regen_to_motor(self):
        with open(EXPERT_JSON, encoding="utf-8") as f:
            ctx = json.load(f)
        self.assertIn("EV-OBC", ctx["battery"]["domains"])
        self.assertIn("EV-DCDC", ctx["battery"]["domains"])
        self.assertIn("EV-REGEN", ctx["motor"]["domains"])
        self.assertIn("EV-HV", ctx["battery"]["domains"])
        self.assertIn("EV-THERMAL", ctx["battery"]["domains"])

    def test_vcu_domain_exists(self):
        with open(EXPERT_JSON, encoding="utf-8") as f:
            ctx = json.load(f)
        self.assertIn("EV-VCU", ctx["vcu"]["domains"])

    def test_expert_domains_match_three_electric(self):
        """expert_context.json domains 必须与 three_electric 单一真源一致"""
        from src.engine.three_electric import get_expert_domains
        with open(EXPERT_JSON, encoding="utf-8") as f:
            ctx = json.load(f)
        for expert, systems in get_expert_domains().items():
            self.assertEqual(set(ctx[expert]["domains"]), set(systems),
                             f"{expert} 域名与 three_electric 不一致")

    def _make_agent(self, system):
        from src.ai.agent import DiagnosticAgent
        agent = DiagnosticAgent.__new__(DiagnosticAgent)
        kb = MagicMock()
        kb.lookup.return_value = {"system": system, "description": "test"}
        agent.kb = kb
        return agent

    def test_select_expert_routes_new_systems(self):
        cases = {
            "EV-BMS": "battery",
            "EV-HV": "battery",
            "EV-OBC": "battery",
            "EV-DCDC": "battery",
            "EV-THERMAL": "battery",
            "EV-MOTOR": "motor",
            "EV-REGEN": "motor",
            "EV-VCU": "vcu",
        }
        for system, expected in cases.items():
            agent = self._make_agent(system)
            result = agent._select_expert("EV-XXX-001", "diagnose")
            self.assertEqual(result, expected, f"{system} 应路由到 {expected}")

    def test_select_expert_unknown_system_general(self):
        agent = self._make_agent("UNKNOWN-SYS")
        result = agent._select_expert("EV-XXX-001", "diagnose")
        self.assertEqual(result, "general")


if __name__ == "__main__":
    unittest.main()
