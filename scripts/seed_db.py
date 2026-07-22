"""
数据库初始化脚本
将 CSV 种子数据导入 SQLite 数据库

用法:
    python scripts/seed_db.py

如果数据库已存在，可以选择覆盖或跳过
"""

import csv
import json
import sqlite3
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SEED_DIR = DATA_DIR / "seed"
DB_PATH = DATA_DIR / "obd_codes.db"

sys.path.insert(0, str(PROJECT_ROOT))
from src.database.schema import CREATE_TABLE_OBD_CODES, CREATE_INDEX_CODE, CREATE_INDEX_SYSTEM


def create_database():
    """创建 SQLite 数据库和表结构"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute(CREATE_TABLE_OBD_CODES)
    cursor.execute(CREATE_INDEX_CODE)
    cursor.execute(CREATE_INDEX_SYSTEM)

    conn.commit()
    conn.close()
    print(f"[OK] Database created: {DB_PATH}")


def parse_json_field(value):
    """
    解析 CSV 中的 JSON 字符串字段
    如果是空值或无效，返回默认空值
    """
    if not value or value.strip() == '':
        return '[]'
    try:
        # 验证 JSON 是否有效
        parsed = json.loads(value)
        return json.dumps(parsed, ensure_ascii=False)
    except json.JSONDecodeError:
        # 如果解析失败，尝试修复常见问题
        # 例如单引号替换为双引号
        try:
            fixed = value.replace("'", '"')
            parsed = json.loads(fixed)
            return json.dumps(parsed, ensure_ascii=False)
        except json.JSONDecodeError:
            print(f"  [WARN] JSON parse failed, using empty array: {value[:50]}...")
            return '[]'


def _open_csv(path: Path):
    """尝试多种编码打开 CSV 文件"""
    for enc in ('utf-8-sig', 'gbk', 'latin-1'):
        try:
            return open(str(path), 'r', encoding=enc)
        except UnicodeDecodeError:
            continue
    return open(str(path), 'r', encoding='utf-8-sig', errors='replace')


def import_csv_to_db(csv_path, conn):
    """
    将单个 CSV 文件导入数据库
    返回导入的行数
    """
    if not csv_path.exists():
        print(f"  [ERROR] File not found: {csv_path}")
        sys.exit(1)

    count = 0
    with _open_csv(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row.get('code', '').strip()
            if not code:
                continue

            # 解析 JSON 字段
            common_causes = parse_json_field(row.get('common_causes', '[]'))
            diagnostic_steps = parse_json_field(row.get('diagnostic_steps', '[]'))
            symptoms = parse_json_field(row.get('symptoms', '[]'))

            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO obd_codes
                    (code, system, code_type, description, detail,
                     severity, common_causes, diagnostic_steps, related_codes, symptoms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                code,
                row.get('system', 'Unknown'),
                row.get('code_type', 'generic'),
                row.get('description', ''),
                row.get('detail', ''),
                row.get('severity', 'medium'),
                common_causes,
                diagnostic_steps,
                row.get('related_codes', ''),
                symptoms
            ))
            count += 1

    return count


def main():
    print("=" * 50)
    print("[TOOL] EV-Diag-Tool Database Initializer")
    print("=" * 50)

    # 检查是否需要覆盖
    if DB_PATH.exists():
        response = input(f"[WARN] Database exists: {DB_PATH}\n   Overwrite? (y/N): ").strip().lower()
        if response != 'y':
            print("[CANCEL] Operation cancelled")
            return
        DB_PATH.unlink()
        print("[DEL] Old database deleted")

    print("\n[CREATE] Creating database structure...")
    create_database()

    conn = sqlite3.connect(str(DB_PATH))

    csv_files = [
        ("P-codes (Powertrain)", SEED_DIR / "p_codes.csv"),
        ("B-codes (Body)", SEED_DIR / "b_codes.csv"),
        ("C-codes (Chassis)", SEED_DIR / "c_codes.csv"),
        ("U-codes (Network)", SEED_DIR / "u_codes.csv"),
    ]

    total_count = 0
    for name, path in csv_files:
        print(f"\n[IMPORT] {name}...")
        count = import_csv_to_db(path, conn)
        print(f"   [OK] Imported {count} records")
        total_count += count

    conn.commit()
    conn.close()

    print(f"\n{'=' * 50}")
    print(f"[DONE] Database initialized!")
    print(f"   Path: {DB_PATH}")
    print(f"   Total records: {total_count}")
    print(f"\nNow run: python src/main.py")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
