"""
AI 批量生成故障码详细诊断信息

用法:
    python scripts/batch_enhance_codes.py [--batch-size 5] [--max-codes 100] [--provider ollama]

功能:
    从数据库读取缺少详细信息的故障码，用 AI 生成后写回数据库。
    支持断点续传（进度保存到 data/enhancement_progress.json）。
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
PROGRESS_FILE = PROJECT_ROOT / "data" / "enhancement_progress.json"

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
        # 尝试从多端点配置获取
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
        # 单端点
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
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
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
    """构建单码生成的 prompt"""
    return f"请为以下故障码生成诊断信息：\n\n- {code_info['code']}: {code_info['description']} (系统: {code_info['system']})"


def parse_ai_response(response_text):
    """解析 AI 返回的 JSON"""
    # 尝试提取 JSON 块
    json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
    if json_match:
        text = json_match.group(1)
    else:
        # 尝试直接解析
        text = response_text.strip()
        # 如果以 [ 或 { 开头，尝试直接解析
        if text.startswith("{") or text.startswith("["):
            pass
        else:
            # 尝试找到第一个 { 和最后一个 }
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                text = text[start:end+1]

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # 检查是否是单个码的结果
            if "detail" in data:
                return [data]
            # 可能是 { "P0001": {...}, "P0002": {...} } 格式
            results = []
            for k, v in data.items():
                if isinstance(v, dict) and "detail" in v:
                    v["code"] = k
                    results.append(v)
            return results
    except json.JSONDecodeError:
        pass

    return []


def load_progress():
    """加载进度文件（兼容旧格式）"""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 兼容旧格式：processed_codes -> completed
        completed = set(data.get("completed", []))
        processed = data.get("processed_codes", [])
        completed.update(processed)
        data["completed"] = list(completed)
        return data
    return {"completed": [], "failed": []}


def save_progress(progress):
    """保存进度文件"""
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def get_codes_needing_enhancement(conn, limit=None, progress=None):
    """获取需要增强的故障码"""
    cursor = conn.cursor()
    completed = set(progress.get("completed", [])) if progress else set()

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
    rows = cursor.fetchall()

    codes = []
    for row in rows:
        if row[0] not in completed:
            codes.append({
                "code": row[0],
                "description": row[1],
                "system": row[2],
                "code_type": row[3],
            })

    if limit:
        codes = codes[:limit]

    return codes


def update_code(conn, code, data):
    """更新数据库中的故障码"""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE obd_codes
        SET detail = ?,
            severity = ?,
            common_causes = ?,
            diagnostic_steps = ?,
            symptoms = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE code = ?
    """, (
        data.get("detail", ""),
        data.get("severity", "medium"),
        json.dumps(data.get("common_causes", []), ensure_ascii=False),
        json.dumps(data.get("diagnostic_steps", []), ensure_ascii=False),
        json.dumps(data.get("symptoms", []), ensure_ascii=False),
        code,
    ))


def validate_enhancement(data):
    """验证生成的数据质量"""
    issues = []
    if not data.get("detail") or len(data["detail"]) < 30:
        issues.append("detail too short")
    if data.get("severity") not in ("low", "medium", "high", "critical"):
        issues.append("invalid severity")
    causes = data.get("common_causes", [])
    if len(causes) < 3:
        issues.append("too few causes")
    steps = data.get("diagnostic_steps", [])
    if len(steps) < 3:
        issues.append("too few steps")
    symptoms = data.get("symptoms", [])
    if len(symptoms) < 2:
        issues.append("too few symptoms")
    return issues


def main():
    parser = argparse.ArgumentParser(description="AI 批量生成故障码详细诊断信息")
    parser.add_argument("--max-codes", type=int, default=0, help="最多处理的故障码数量 (0=全部)")
    parser.add_argument("--provider", type=str, default=None, help="AI provider (ollama/openai)")
    parser.add_argument("--dry-run", action="store_true", help="只显示计划，不实际调用 AI")
    args = parser.parse_args()

    print("=" * 60)
    print("EV-Diag-Tool | AI 批量故障码增强")
    print("=" * 60)

    # 检查数据库
    if not DB_PATH.exists():
        print(f"\n[ERROR] 数据库不存在: {DB_PATH}")
        print("  请先运行: python scripts/seed_db.py")
        sys.exit(1)

    # 获取 AI 配置
    config = get_ai_config(args.provider)
    if not config:
        print("\n[ERROR] 未配置 AI 服务")
        print("  请在 .env 中配置 AI_PROVIDER 和对应的 API 信息")
        print("  示例: AI_PROVIDER=ollama 或 AI_PROVIDER=openai + OPENAI_API_KEY")
        sys.exit(1)

    print(f"\nAI Provider: {config['provider']}")
    print(f"Model: {config['model']}")
    print(f"Base URL: {config['base_url']}")

    # 连接数据库（autocommit 模式，每条 UPDATE 立即释放锁，避免 database is locked）
    conn = sqlite3.connect(str(DB_PATH), timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")

    # 加载进度
    progress = load_progress()
    print(f"已完成: {len(progress.get('completed', []))} 条")
    print(f"已失败: {len(progress.get('failed', []))} 条")

    # 获取需要增强的码
    limit = args.max_codes if args.max_codes > 0 else None
    codes = get_codes_needing_enhancement(conn, limit=limit, progress=progress)
    print(f"\n待处理: {len(codes)} 条")

    if not codes:
        print("\n所有故障码已有详细信息，无需增强。")
        conn.close()
        return

    if args.dry_run:
        print("\n[DRY RUN] 将处理以下故障码：")
        for i, c in enumerate(codes[:20]):
            print(f"  {c['code']}: {c['description'][:40]}")
        if len(codes) > 20:
            print(f"  ... 还有 {len(codes) - 20} 条")
        conn.close()
        return

    # 逐条处理（比批量更可靠，AI 不会丢码）
    total = len(codes)
    success_count = 0
    error_count = 0

    print(f"\n开始处理，共 {total} 条")
    print("-" * 60)

    for i, code_info in enumerate(codes):
        code = code_info["code"]
        print(f"\n[{i+1}/{total}] {code}: {code_info['description'][:40]}")

        # 构建 prompt
        user_msg = build_prompt(code_info)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        # 调用 AI
        try:
            t0 = time.time()
            response = call_llm(config, messages, temperature=0.3, max_tokens=2048)
            elapsed = time.time() - t0
            print(f"  AI 响应: {elapsed:.1f}s", end="")

            # 解析响应
            results = parse_ai_response(response)
            data = results[0] if results else None

            if data:
                issues = validate_enhancement(data)
                if issues:
                    print(f" [WARN: {', '.join(issues)}]", end="")
                update_code(conn, code, data)
                progress.setdefault("completed", []).append(code)
                success_count += 1
                print(f" -> OK")
            else:
                print(f" -> [FAIL] 无法解析响应")
                progress.setdefault("failed", []).append(code)
                error_count += 1

            # 每 10 条提交一次
            if (i + 1) % 10 == 0:
                conn.commit()
                save_progress(progress)

        except urllib.error.HTTPError as e:
            print(f"  [ERROR] HTTP {e.code}: {e.reason}")
            progress.setdefault("failed", []).append(code)
            error_count += 1
            if e.code == 429:
                print("  请求过于频繁，等待 30 秒后重试...")
                time.sleep(30)
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")
            progress.setdefault("failed", []).append(code)
            error_count += 1

        # 请求间隔（避免过载）
        if i < total - 1:
            time.sleep(0.5)

    # 最终提交
    conn.commit()
    save_progress(progress)
    conn.close()

    print("\n" + "=" * 60)
    print("批量增强完成！")
    print(f"  成功: {success_count}")
    print(f"  失败: {error_count}")
    print(f"  总计: {total}")
    print(f"  进度文件: {PROGRESS_FILE}")
    print(f"\n下一步:")
    print(f"  1. 运行测试: python -m pytest tests/")
    print(f"  2. 重新运行本脚本处理失败的码: python scripts/batch_enhance_codes.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
