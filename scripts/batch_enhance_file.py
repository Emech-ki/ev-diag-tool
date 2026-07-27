"""
AI 批量生成故障码详细诊断信息（文件分片版）

用法:
    python scripts/batch_enhance_file.py --chunk-file data/remaining_chunk_0.json

功能:
    从 JSON 文件读取待处理故障码，调用 AI 生成详细诊断信息并写回数据库。
    独立进度文件，支持断点续传。
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

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")


def get_ai_config(provider_override=None):
    provider = (provider_override or os.getenv("AI_PROVIDER", "ollama")).lower().strip()
    if provider == "ollama":
        return {"provider": "ollama", "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                "model": os.getenv("OLLAMA_MODEL_NAME", "qwen2.5:7b"), "timeout": int(os.getenv("AI_REQUEST_TIMEOUT", "120"))}
    else:
        for i in range(1, 20):
            name = os.getenv(f"OPENAI_ENDPOINT_{i}_NAME", "").strip()
            if name:
                return {"provider": "openai", "base_url": os.getenv(f"OPENAI_ENDPOINT_{i}_URL", "").rstrip("/"),
                        "api_key": os.getenv(f"OPENAI_ENDPOINT_{i}_KEY", ""),
                        "model": os.getenv(f"OPENAI_ENDPOINT_{i}_MODEL", "gpt-4o-mini"),
                        "timeout": int(os.getenv("AI_REQUEST_TIMEOUT", "120"))}
        api_key = os.getenv("OPENAI_API_KEY", "")
        if api_key:
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
            return {"provider": "openai", "base_url": base_url, "api_key": api_key,
                    "model": os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
                    "timeout": int(os.getenv("AI_REQUEST_TIMEOUT", "120"))}
    return None


def call_llm(config, messages, temperature=0.3, max_tokens=2048):
    if config["provider"] == "ollama":
        return call_ollama(config, messages, temperature, max_tokens)
    else:
        return call_openai_compat(config, messages, temperature, max_tokens)


def call_ollama(config, messages, temperature, max_tokens):
    url = f"{config['base_url']}/api/chat"
    payload = {"model": config["model"], "messages": messages, "stream": False,
               "options": {"temperature": temperature, "num_predict": max_tokens}}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    resp = urllib.request.urlopen(req, timeout=config["timeout"])
    return json.loads(resp.read().decode("utf-8"))["message"]["content"]


def call_openai_compat(config, messages, temperature, max_tokens):
    base = config["base_url"]
    if not base.endswith("/v1") and not base.endswith("/v2"):
        from urllib.parse import urlparse
        if urlparse(base).path in ("", "/"):
            base = base + "/v1"
    url = f"{base}/chat/completions"
    payload = {"model": config["model"], "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {config['api_key']}"}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    resp = urllib.request.urlopen(req, timeout=config["timeout"])
    return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]


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
    json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
    text = json_match.group(1) if json_match else response_text.strip()
    if not (text.startswith("{") or text.startswith("[")):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end+1]
    try:
        data = json.loads(text)
        if isinstance(data, list): return data
        if isinstance(data, dict):
            if "detail" in data: return [data]
            return [v.update({"code": k}) or v for k, v in data.items() if isinstance(v, dict) and "detail" in v]
    except json.JSONDecodeError: pass
    return []


def update_code(code, data):
    for attempt in range(5):
        conn = sqlite3.connect(str(DB_PATH), timeout=30, isolation_level=None)
        conn.execute("PRAGMA busy_timeout=10000")
        try:
            conn.execute("""UPDATE obd_codes SET detail=?, severity=?, common_causes=?,
                diagnostic_steps=?, symptoms=?, updated_at=CURRENT_TIMESTAMP WHERE code=?""",
                (data.get("detail",""), data.get("severity","medium"),
                 json.dumps(data.get("common_causes",[]), ensure_ascii=False),
                 json.dumps(data.get("diagnostic_steps",[]), ensure_ascii=False),
                 json.dumps(data.get("symptoms",[]), ensure_ascii=False), code))
            return
        except sqlite3.OperationalError as e:
            conn.close()
            if "locked" in str(e) and attempt < 4: time.sleep(1+attempt); continue
            raise
        finally: conn.close()


def process_one(code_info, config):
    code = code_info["code"]
    messages = [{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":build_prompt(code_info)}]
    try:
        t0 = time.time()
        response = call_llm(config, messages, temperature=0.3, max_tokens=2048)
        elapsed = time.time() - t0
        results = parse_ai_response(response)
        if results:
            update_code(code, results[0])
            return (code, True, elapsed, None)
        return (code, False, elapsed, "无法解析响应")
    except Exception as e:
        return (code, False, 0, str(e))


def main():
    parser = argparse.ArgumentParser(description="AI 批量增强（文件分片版）")
    parser.add_argument("--chunk-file", type=str, required=True, help="待处理 codes JSON 文件")
    parser.add_argument("--provider", type=str, default=None)
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()

    chunk_path = Path(args.chunk_file)
    if not chunk_path.exists():
        print(f"[ERROR] 文件不存在: {chunk_path}"); sys.exit(1)

    with open(chunk_path, "r", encoding="utf-8") as f:
        all_codes = json.load(f)

    # Load progress
    progress_file = chunk_path.with_suffix(".progress.json")
    if progress_file.exists():
        with open(progress_file, "r", encoding="utf-8") as f:
            progress = json.load(f)
    else:
        progress = {"completed": [], "failed": []}

    completed_set = set(progress.get("completed", []))
    remaining = [c for c in all_codes if c["code"] not in completed_set]

    print(f"=" * 60)
    print(f"文件分片增强: {chunk_path.name}")
    print(f"总码数: {len(all_codes)}, 已完成: {len(completed_set)}, 剩余: {len(remaining)}")
    print(f"=" * 60)

    config = get_ai_config(args.provider)
    if not config:
        print("[ERROR] 未配置 AI 服务"); sys.exit(1)

    print(f"Provider: {config['provider']}, Model: {config['model']}")

    CONCURRENCY = args.concurrency
    total = len(remaining)
    success = fail = 0

    from concurrent.futures import ThreadPoolExecutor, as_completed
    for batch_start in range(0, total, CONCURRENCY):
        batch = remaining[batch_start:batch_start+CONCURRENCY]
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
            futures = {executor.submit(process_one, c, config): c for c in batch}
            for future in as_completed(futures):
                code, ok, elapsed, err = future.result()
                if ok:
                    success += 1
                    progress.setdefault("completed",[]).append(code)
                    print(f"  [OK] {code} ({elapsed:.1f}s)")
                else:
                    fail += 1
                    progress.setdefault("failed",[]).append(code)
                    print(f"  [FAIL] {code}: {err}")

        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

        done = batch_start + len(batch)
        print(f"  进度: {done}/{total} ({done*100/total:.1f}%)")

    print(f"\n完成！成功: {success}, 失败: {fail}, 总计: {total}")


if __name__ == "__main__":
    main()
