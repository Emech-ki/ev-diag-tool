"""
scripts/generate_ev_system_codes.py 同步/合并逻辑测试
"""

import sys
import os
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from generate_ev_system_codes import _merge_sync_rows


def _row(code, detail="", **kw):
    r = {"code": code, "system": "EV-BMS", "code_type": "generic", "description": "",
         "detail": detail, "severity": "medium", "common_causes": [],
         "diagnostic_steps": [], "related_codes": [], "symptoms": []}
    r.update(kw)
    return r


class TestMergeSyncRows(unittest.TestCase):
    """do_sync_db 的合并逻辑（纯逻辑）"""

    def setUp(self):
        self.generated = [
            _row("EV-BMS-001", detail="", description="生成描述"),
            _row("EV-BMS-002", detail="", description="生成描述"),
            _row("EV-BMS-003", detail="", description="生成描述"),
        ]

    def test_db_with_detail_overwrites_csv(self):
        existing = {r["code"]: r for r in self.generated}
        by_code = {
            "EV-BMS-001": _row("EV-BMS-001", detail="DB 详情 A"),
            "EV-BMS-002": _row("EV-BMS-002", detail=""),  # DB 无详情
        }
        out = _merge_sync_rows(self.generated, by_code, existing)
        by_code_out = {r["code"]: r for r in out}
        self.assertEqual(by_code_out["EV-BMS-001"]["detail"], "DB 详情 A")
        # DB 无详情 → 保留 CSV 原值
        self.assertEqual(by_code_out["EV-BMS-002"]["description"], "生成描述")
        self.assertEqual(by_code_out["EV-BMS-003"]["description"], "生成描述")

    def test_missing_in_db_keeps_existing(self):
        existing = {r["code"]: r for r in self.generated}
        by_code = {}
        out = _merge_sync_rows(self.generated, by_code, existing)
        self.assertEqual(len(out), 3)
        self.assertEqual(out[0]["description"], "生成描述")

    def test_missing_everywhere_uses_generated(self):
        out = _merge_sync_rows(self.generated, {}, {})
        self.assertEqual(len(out), 3)
        self.assertEqual(out[0]["code"], "EV-BMS-001")


if __name__ == "__main__":
    unittest.main()
