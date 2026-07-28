"""
合并各分片的进度文件到主进度文件

用法:
    python scripts/merge_enhancement_progress.py
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROGRESS_FILE = PROJECT_ROOT / "data" / "enhancement_progress.json"


def main():
    data_dir = PROJECT_ROOT / "data"

    # 找到所有分片进度文件
    chunk_files = sorted(data_dir.glob("enhancement_progress_*.json"))
    if not chunk_files:
        print("[WARN] 未找到分片进度文件 (enhancement_progress_*.json)")
        return

    print(f"找到 {len(chunk_files)} 个分片进度文件：")

    all_completed = set()
    all_failed = set()

    for f in chunk_files:
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        completed = set(data.get("completed", []))
        failed = set(data.get("failed", []))
        print(f"  {f.name}: completed={len(completed)}, failed={len(failed)}")
        all_completed.update(completed)
        all_failed.update(failed)

    # 加载主进度文件（保留之前的数据）
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as fh:
            main_data = json.load(fh)
        old_completed = set(main_data.get("completed", []))
        old_failed = set(main_data.get("failed", []))
        print(f"\n主进度文件已有: completed={len(old_completed)}, failed={len(old_failed)}")
        all_completed.update(old_completed)
        all_failed.update(old_failed)

    # 从 failed 中移除已成功完成的
    all_failed -= all_completed

    merged = {
        "completed": sorted(all_completed),
        "failed": sorted(all_failed),
    }

    with open(PROGRESS_FILE, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=2)

    print(f"\n合并完成！")
    print(f"  总 completed: {len(all_completed)}")
    print(f"  总 failed: {len(all_failed)}")
    print(f"  已写入: {PROGRESS_FILE}")

    # 检查数据库覆盖率
    import sqlite3
    db_path = data_dir / "obd_codes.db"
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM obd_codes")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM obd_codes WHERE detail IS NOT NULL AND detail != ''")
        done = cur.fetchone()[0]
        conn.close()
        print(f"\n数据库覆盖率: {done}/{total} ({done/total*100:.1f}%)")


if __name__ == "__main__":
    main()
