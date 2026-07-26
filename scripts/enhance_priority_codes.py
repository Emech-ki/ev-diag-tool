"""
增强高频故障码数据质量
为优先级故障码添加详细的诊断信息

用法:
    python scripts/enhance_priority_codes.py
"""

import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "obd_codes.db"
ENHANCEMENT_FILE = DATA_DIR / "seed" / "priority_enhancement.json"


def load_enhancement_data():
    """加载增强数据"""
    if not ENHANCEMENT_FILE.exists():
        print(f"[ERROR] Enhancement file not found: {ENHANCEMENT_FILE}")
        sys.exit(1)

    with open(ENHANCEMENT_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def enhance_codes(db_path, enhancement_data):
    """更新数据库中的故障码信息"""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    success_count = 0
    error_count = 0

    for code, data in enhancement_data.items():
        try:
            # 检查故障码是否存在
            cursor.execute("SELECT code FROM obd_codes WHERE code = ?", (code,))
            if cursor.fetchone() is None:
                print(f"  [SKIP] {code}: Not found in database")
                continue

            # 更新字段
            cursor.execute("""
                UPDATE obd_codes
                SET detail = ?,
                    severity = ?,
                    common_causes = ?,
                    diagnostic_steps = ?,
                    related_codes = ?,
                    symptoms = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE code = ?
            """, (
                data.get("detail", ""),
                data.get("severity", "medium"),
                json.dumps(data.get("common_causes", []), ensure_ascii=False),
                json.dumps(data.get("diagnostic_steps", []), ensure_ascii=False),
                ",".join(data.get("related_codes", [])),
                json.dumps(data.get("symptoms", []), ensure_ascii=False),
                code
            ))

            success_count += 1
            print(f"  [OK] {code}: Enhanced")

        except Exception as e:
            error_count += 1
            print(f"  [ERROR] {code}: {e}")

    conn.commit()
    conn.close()

    return success_count, error_count


def main():
    print("=" * 60)
    print("Priority Code Enhancement Tool")
    print("=" * 60)

    # 加载增强数据
    print(f"\nLoading enhancement data from: {ENHANCEMENT_FILE}")
    enhancement_data = load_enhancement_data()
    print(f"  Found {len(enhancement_data)} codes to enhance")

    # 检查数据库
    if not DB_PATH.exists():
        print(f"\n[ERROR] Database not found: {DB_PATH}")
        print("  Please run: python scripts/seed_db.py")
        sys.exit(1)

    # 执行增强
    print(f"\nEnhancing codes in: {DB_PATH}")
    success_count, error_count = enhance_codes(DB_PATH, enhancement_data)

    # 输出结果
    print(f"\n{'=' * 60}")
    print(f"Enhancement complete!")
    print(f"  Success: {success_count}")
    print(f"  Errors: {error_count}")
    print(f"  Total: {len(enhancement_data)}")
    print(f"\nNext steps:")
    print(f"  1. Run tests: python -m pytest tests/")
    print(f"  2. Verify: python scripts/verify_features.py")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
