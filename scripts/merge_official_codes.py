"""
合并官方 OBD-II 故障码数据与现有中文数据

数据来源: Wal33D/dtc-database (GitHub)
格式: "CODE - English Description"

合并策略:
1. 保留现有的详细中文数据（description, detail, common_causes, diagnostic_steps, symptoms）
2. 对于只有英文描述的故障码，使用英文作为 description
3. 去重（以 code 为主键）
"""

import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = PROJECT_ROOT / "data" / "seed"
RAW_DIR = PROJECT_ROOT / "data" / "raw"


def parse_official_file(filepath: Path) -> dict:
    """解析官方数据文件，返回 {code: description} 字典"""
    codes = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or ' - ' not in line:
                continue
            parts = line.split(' - ', 1)
            if len(parts) == 2:
                code = parts[0].strip()
                desc = parts[1].strip()
                codes[code] = desc
    return codes


def load_existing_csv(filepath: Path) -> dict:
    """加载现有 CSV 数据，返回 {code: row_dict} 字典"""
    codes = {}
    if not filepath.exists():
        return codes

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row.get('code', '').strip()
            if code:
                # 移除 None 键（由重复列名导致）
                cleaned = {k: v for k, v in row.items() if k is not None}
                codes[code] = cleaned
    return codes


def merge_codes(existing: dict, official: dict, system: str) -> list:
    """合并现有数据和官方数据"""
    merged = []

    # 先添加所有现有数据（优先保留中文详细信息）
    for code, row in existing.items():
        merged.append(row)

    # 添加官方数据中不在现有数据中的条目
    for code, desc in official.items():
        if code not in existing:
            merged.append({
                'code': code,
                'system': system,
                'code_type': 'generic',
                'description': desc,
                'detail': '',
                'severity': 'medium',
                'common_causes': '[]',
                'diagnostic_steps': '[]',
                'related_codes': '',
                'symptoms': '[]',
            })

    # 按故障码排序
    merged.sort(key=lambda x: x.get('code', ''))
    return merged


def write_csv(filepath: Path, data: list, fieldnames: list):
    """写入 CSV 文件"""
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for row in data:
            # 过滤掉 None 键和不在 fieldnames 中的字段
            clean_row = {k: v for k, v in row.items() if k is not None and k in fieldnames}
            writer.writerow(clean_row)


def main():
    print("=" * 60)
    print("OBD-II 故障码数据合并工具")
    print("=" * 60)

    # 定义字段名
    fieldnames = ['code', 'system', 'code_type', 'description', 'detail',
                  'severity', 'common_causes', 'diagnostic_steps',
                  'related_codes', 'symptoms']

    # 处理各类故障码
    files = [
        ('p_codes.csv', 'p_codes.txt', 'Powertrain'),
        ('b_codes.csv', 'b_codes.txt', 'Body'),
        ('c_codes.csv', 'c_codes.txt', 'Chassis'),
        ('u_codes.csv', 'u_codes.txt', 'Network'),
    ]

    total_existing = 0
    total_official = 0
    total_merged = 0

    for csv_name, txt_name, system in files:
        csv_path = SEED_DIR / csv_name
        txt_path = RAW_DIR / txt_name

        print(f"\n[{system}] Processing {csv_name}...")

        # 加载数据
        existing = load_existing_csv(csv_path)
        official = parse_official_file(txt_path) if txt_path.exists() else {}

        print(f"   Existing: {len(existing)} codes")
        print(f"   Official: {len(official)} codes")

        # 合并
        merged = merge_codes(existing, official, system)
        print(f"   Merged:   {len(merged)} codes")

        # 写入
        write_csv(csv_path, merged, fieldnames)

        total_existing += len(existing)
        total_official += len(official)
        total_merged += len(merged)

    print(f"\n{'=' * 60}")
    print(f"合并完成!")
    print(f"   原有数据: {total_existing} codes")
    print(f"   官方数据: {total_official} codes")
    print(f"   合并后:   {total_merged} codes")
    print(f"\n下一步: python scripts/seed_db.py -f")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
