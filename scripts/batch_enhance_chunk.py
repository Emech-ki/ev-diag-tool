"""
AI 批量生成故障码详细诊断信息（分片版）

用法:
    python scripts/batch_enhance_chunk.py --chunk-id 0 --total-chunks 4

功能:
    将待处理故障码按 chunk 分片，每片独立运行、独立进度文件。
    4 片并行可将总时间从 ~15h 缩短到 ~4h。
"""

import json
import os
import re
import sqlite3
import sys
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "obd_codes.db"

# 加载 .env
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")


def get_ai_config(provider_override=None):
    """获取 AI 配置"""
    provider = (provider_override or os.getenv("AI_PROVIDER", "ollama")).lower().strip()

    if provider == "ollama":
        return {
            "provider": "ollama",
            "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            "model": os.getenv("OLLAMA_MODEL_NAME", "qwen2.5:7b"),
            "timeout": int(os.getenv("AI_REQUEST_TIMEOUT", "120")),
        }
    else:
        for i in range(1, 20):
            name = os.getenv(f"OPENAI_ENDPOINT_{i}_NAME", "").strip()
            if name:
                return {
                    "provider": "openai",
                    "base_url": os.getenv(f"OPENAI_ENDPOINT_{i}_URL", "").rstrip("/"),
                    "api_key": os.getenv(f"OPENAI_ENDPOINT_{i}_KEY", ""),
                    "model": os.getenv(f"OPENAI_ENDPOINT_{i}_MODEL", "gpt-4o-mini"),
                    "timeout": int(os.getenv("AI_REQUEST_TIMEOUT", "120")),
                }
        api_key = os.getenv("OPENAI_API_KEY", "")
        if api_key:
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
            return {
                "provider": "openai",
                "base_url": base_url,
                "api_key": api_key,
                "model": os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
                "timeout": int(os.getenv("AI_REQUEST_TIMEOUT", "120")),
            }

    return None


def call_llm(config, messages, temperature=0.3, max_tokens=2048):
    """调用 LLM API"""
    if config["provider"] == "ollama":
        return call_ollama(config, messages, temperature, max_tokens)
    else:
        return call_openai_compat(config, messages, temperature, max_tokens)


def call_ollama(config, messages, temperature, max_tokens):
    """调用 Ollama API"""
    url = f"{config['base_url']}/api/chat"
    payload = {
        "model": config["model"],
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    resp = urllib.request.urlopen(req, timeout=config["timeout"])
    result = json.loads(resp.read().decode("utf-8"))
    return result["message"]["content"]


def call_openai_compat(config, messages, temperature, max_tokens):
    """调用 OpenAI 兼容 API"""
    base = config["base_url"]
    if not base.endswith("/v1") and not base.endswith("/v2"):
        from urllib.parse import urlparse
        parsed = urlparse(base)
        if parsed.path in ("", "/"):
            base = base + "/v1"

    url = f"{base}/chat/completions"
    payload = {
        "model": config["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['api_key']}",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    resp = urllib.request.urlopen(req, timeout=config["timeout"])
    result = json.loads(resp.read().decode("utf-8"))
    return result["choices"][0]["message"]["content"]


SYSTEM_PROMPT = """你是一位资深的新能源汽车维修技师和 OBD-II 诊断专家。

你的任务是为给定的 OBD-II 故障码生成详细的中文诊断信息。

输出格式必须是严格的 JSON，不要包含任何其他文本：

```json
{
  "detail": "详细说明（100-200字，包含系统原理和故障含义）",
  "severity": "low/medium/high/critical 之一",
  "common_causes": ["原因1", "原因2", "原因3", "原因4", "原因5"],
  "diagnostic_steps": ["第一步：具体操作", "第二步：具体操作", "第三步：具体操作", "第四步：具体操作", "第五步：具体操作"],
  "symptoms": ["症状1", "症状2", "症状3"]
}
```

要求：
1. detail 要说明该系统的正常工作原理和故障发生时的异常
2. severity 按照对行车安全和车辆性能的影响程度判断
3. common_causes 列出 5-6 个最常见的原因，从最常见到较少见排列
4. diagnostic_steps 列出 5-7 步具体可操作的诊断流程，每步要包含具体操作和判断标准
5. symptoms 列出 3-4 个驾驶员可直接观察到的现象
6. 使用专业中文术语：开路、短路、电压过低、范围/性能等
7. 如果是新能源相关码（P0Axx/P0Bxx/P0Cxx），注意高压安全提醒
8. 所有内容用中文"""


def build_prompt(code_info):
    return f"请为以下故障码生成诊断信息：\n\n- {code_info['code']}: {code_info['description']} (系统: {code_info['system']})"


def parse_ai_response(response_text):
    """解析 AI 返回的 JSON"""
    json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
    if json_match:
        text = json_match.group(1)
    else:
        text = response_text.strip()
        if not (text.startswith("{") or text.startswith("[")):
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                text = text[start:end+1]

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            if "detail" in data:
                return [data]
            results = []
            for k, v in data.items():
                if isinstance(v, dict) and "detail" in v:
                    v["code"] = k
                    results.append(v)
            return results
    except json.JSONDecodeError:
        pass
    return []


def load_progress(chunk_id):
    """加载分片进度文件"""
    path = PROJECT_ROOT / "data" / f"enhancement_progress_{chunk_id}.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        completed = set(data.get("completed", []))
        data["completed"] = list(completed)
        return data
    return {"completed": [], "failed": []}


def save_progress(progress, chunk_id):
    """保存分片进度文件"""
    path = PROJECT_ROOT / "data" / f"enhancement_progress_{chunk_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def get_all_codes_needing_enhancement(conn):
    """获取所有需要增强的故障码（按优先级排序）"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT code, description, system, code_type
        FROM obd_codes
        WHERE detail IS NULL OR detail = ''
        ORDER BY
            CASE
                WHEN code LIKE 'P0A%' OR code LIKE 'P0B%' OR code LIKE 'P0C%' THEN 0
                WHEN code LIKE 'P0%' THEN 1
                WHEN code LIKE 'P1%' THEN 2
                WHEN code LIKE 'B%' THEN 3
                WHEN code LIKE 'C%' THEN 4
                WHEN code LIKE 'U%' THEN 5
                ELSE 6
            END,
            code
    """)
    return [
        {"code": r[0], "description": r[1], "system": r[2], "code_type": r[3]}
        for r in cursor.fetchall()
    ]


def get_chunk_codes(all_codes, chunk_id, total_chunks, completed_set):
    """从全部 codes 中取出本 chunk 的份额，跳过已完成的"""
    # 先过滤掉已完成的
    remaining = [c for c in all_codes if c["code"] not in completed_set]
    # 均匀分片
    chunk_size = len(remaining) // total_chunks
    start = chunk_id * chunk_size
    end = start + chunk_size if chunk_id < total_chunks - 1 else len(remaining)
    return remaining[start:end]


def update_code(code, data):
    """更新数据库中的故障码"""
    import time as _time
    for attempt in range(5):
        conn = sqlite3.connect(str(DB_PATH), timeout=30, isolation_level=None)
        conn.execute("PRAGMA busy_timeout=10000")
        try:
            conn.execute("""
                UPDATE obd_codes
                SET detail = ?, severity = ?, common_causes = ?,
                    diagnostic_steps = ?, symptoms = ?, updated_at = CURRENT_TIMESTAMP
                WHERE code = ?
            """, (
                data.get("detail", ""),
                data.get("severity", "medium"),
                json.dumps(data.get("common_causes", []), ensure_ascii=False),
                json.dumps(data.get("diagnostic_steps", []), ensure_ascii=False),
                json.dumps(data.get("symptoms", []), ensure_ascii=False),
                code,
            ))
            return
        except sqlite3.OperationalError as e:
            conn.close()
            if "locked" in str(e) and attempt < 4:
                _time.sleep(1 + attempt)
                continue
            raise
        finally:
            conn.close()


def process_one(code_info, config):
    """处理单个故障码"""
    code = code_info["code"]
    user_msg = build_prompt(code_info)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    try:
        t0 = time.time()
        response = call_llm(config, messages, temperature=0.3, max_tokens=2048)
        elapsed = time.time() - t0
        results = parse_ai_response(response)
        data = results[0] if results else None
        if data:
            update_code(code, data)
            return (code, True, elapsed, None)
        else:
            return (code, False, elapsed, "无法解析响应")
    except Exception as e:
        return (code, False, 0, str(e))


def main():
    parser = argparse.ArgumentParser(description="AI 批量生成故障码详细诊断信息（分片版）")
    parser.add_argument("--chunk-id", type=int, required=True, help="当前分片 ID (0-based)")
    parser.add_argument("--total-chunks", type=int, default=4, help="总分片数 (默认 4)")
    parser.add_argument("--provider", type=str, default=None, help="AI provider (ollama/openai)")
    parser.add_argument("--concurrency", type=int, default=5, help="并发数 (默认 5)")
    args = parser.parse_args()

    chunk_id = args.chunk_id
    total_chunks = args.total_chunks

    if chunk_id < 0 or chunk_id >= total_chunks:
        print(f"[ERROR] chunk-id 必须在 0-{total_chunks-1} 之间")
        sys.exit(1)

    print("=" * 60)
    print(f"EV-Diag-Tool | 批量增强 — 分片 {chunk_id}/{total_chunks}")
    print("=" * 60)

    if not DB_PATH.exists():
        print(f"\n[ERROR] 数据库不存在: {DB_PATH}")
        sys.exit(1)

    config = get_ai_config(args.provider)
    if not config:
        print("\n[ERROR] 未配置 AI 服务")
        sys.exit(1)

    print(f"\nAI Provider: {config['provider']}")
    print(f"Model: {config['model']}")
    print(f"Base URL: {config['base_url']}")

    conn = sqlite3.connect(str(DB_PATH), timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")

    # 加载本分片进度
    progress = load_progress(chunk_id)
    completed_set = set(progress.get("completed", []))
    print(f"本分片已完成: {len(completed_set)} 条")

    # 获取所有待处理 codes，然后分片
    all_codes = get_all_codes_needing_enhancement(conn)
    my_codes = get_chunk_codes(all_codes, chunk_id, total_chunks, completed_set)
    print(f"本分片待处理: {len(my_codes)} 条")
    conn.close()

    if not my_codes:
        print("\n本分片无待处理故障码。")
        return

    CONCURRENCY = args.concurrency
    total = len(my_codes)
    success_count = 0
    error_count = 0

    print(f"\n开始处理，并发数 {CONCURRENCY}")
    print("-" * 60)

    for batch_start in range(0, total, CONCURRENCY):
        batch_end = min(batch_start + CONCURRENCY, total)
        batch = my_codes[batch_start:batch_end]

        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
            futures = {executor.submit(process_one, c, config): c for c in batch}
            for future in as_completed(futures):
                code, ok, elapsed, err = future.result()
                if ok:
                    success_count += 1
                    progress.setdefault("completed", []).append(code)
                    print(f"  [OK] {code} ({elapsed:.1f}s)")
                else:
                    error_count += 1
                    progress.setdefault("failed", []).append(code)
                    print(f"  [FAIL] {code}: {err}")

        save_progress(progress, chunk_id)
        done = batch_end
        remaining = total - done
        eta_hours = remaining * 20 / CONCURRENCY / 3600
        print(f"  进度: {done}/{total} ({done*100/total:.1f}%) | 预计剩余: {eta_hours:.1f}h")

    save_progress(progress, chunk_id)

    print("\n" + "=" * 60)
    print(f"分片 {chunk_id} 完成！")
    print(f"  成功: {success_count}")
    print(f"  失败: {error_count}")
    print(f"  总计: {total}")
    print(f"  进度文件: data/enhancement_progress_{chunk_id}.json")
    print("=" * 60)


if __name__ == "__main__":
    main()
