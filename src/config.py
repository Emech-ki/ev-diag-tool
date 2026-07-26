"""
EV-Diag-Tool 配置管理
从 .env 文件加载配置，提供统一的配置接口
支持多 OpenAI 兼容 API 端点
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 加载 .env 文件
load_dotenv(PROJECT_ROOT / ".env")

# ── AI Provider 配置 ──
# 可选: ollama / openai
AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama")

# Ollama 配置
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME", "qwen2.5:7b")

# 单端点 OpenAI 兼容 API 配置（向后兼容）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")

# AI 生成参数
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.7"))
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "1024"))
AI_REQUEST_TIMEOUT = int(os.getenv("AI_REQUEST_TIMEOUT", "90"))
AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "3"))

# ── 数据库配置 ──
# 数据库路径（留空则使用默认路径 data/obd_codes.db）
DB_PATH = os.getenv("DB_PATH", "")

# ── 日志配置 ──
# 日志级别: DEBUG / INFO / WARNING / ERROR
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


def get_remote_endpoints() -> list:
    """
    解析 .env 中配置的多个 OpenAI 兼容 API 端点。

    支持两种格式：
    1. 索引格式（多端点）:
       OPENAI_ENDPOINT_1_NAME=DeepSeek
       OPENAI_ENDPOINT_1_URL=https://api.deepseek.com/v1
       OPENAI_ENDPOINT_1_KEY=sk-xxx
       OPENAI_ENDPOINT_1_MODEL=deepseek-chat

    2. 单端点格式（向后兼容）:
       OPENAI_API_KEY=sk-xxx
       OPENAI_BASE_URL=https://api.openai.com/v1
       OPENAI_MODEL_NAME=gpt-4o-mini

    Returns:
        list[dict]，每项含 name, base_url, api_key, model_name
    """
    endpoints = []

    # 扫描索引格式端点 (OPENAI_ENDPOINT_1_NAME, _2_NAME, ...)
    for i in range(1, 20):  # 最多支持 20 个端点
        name = os.getenv(f"OPENAI_ENDPOINT_{i}_NAME", "").strip()
        if not name:
            continue
        url = os.getenv(f"OPENAI_ENDPOINT_{i}_URL", "").strip()
        key = os.getenv(f"OPENAI_ENDPOINT_{i}_KEY", "").strip()
        model = os.getenv(f"OPENAI_ENDPOINT_{i}_MODEL", "").strip()
        if url and key:
            endpoints.append({
                "name": name,
                "base_url": url,
                "api_key": key,
                "model_name": model or "gpt-4o-mini",
            })

    # 向后兼容：如果没索引端点但有单端点配置，自动转为单端点
    if not endpoints and OPENAI_API_KEY:
        endpoints.append({
            "name": "OpenAI",
            "base_url": OPENAI_BASE_URL,
            "api_key": OPENAI_API_KEY,
            "model_name": OPENAI_MODEL_NAME,
        })

    return endpoints


def get_next_endpoint_index() -> int:
    """
    扫描 .env 中已有的 OPENAI_ENDPOINT_*_NAME 条目，返回下一个可用索引。
    """
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return 1

    import re
    max_idx = 0
    pattern = re.compile(r"^OPENAI_ENDPOINT_(\d+)_NAME\s*=", re.MULTILINE)
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            m = pattern.match(line.strip())
            if m:
                max_idx = max(max_idx, int(m.group(1)))
    return max_idx + 1


def append_endpoint_to_env(name: str, url: str, key: str, model: str) -> int:
    """
    将一个新的 OpenAI 兼容端点追加到 .env 文件。

    Returns:
        写入的索引号
    """
    idx = get_next_endpoint_index()
    env_path = PROJECT_ROOT / ".env"

    # 如果 .env 不存在，先创建一个基础模板
    if not env_path.exists():
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("# EV-Diag-Tool 环境变量配置\n\n")

    # 确保文件末尾有换行
    with open(env_path, "a", encoding="utf-8") as f:
        f.write(f"\nOPENAI_ENDPOINT_{idx}_NAME={name}\n")
        f.write(f"OPENAI_ENDPOINT_{idx}_URL={url}\n")
        f.write(f"OPENAI_ENDPOINT_{idx}_KEY={key}\n")
        f.write(f"OPENAI_ENDPOINT_{idx}_MODEL={model}\n")

    # 重新加载 .env 到环境变量（override=True 确保覆盖）
    load_dotenv(env_path, override=True)

    return idx


def remove_endpoint_from_env(endpoint_name: str) -> bool:
    """
    从 .env 文件中删除指定名称的远程端点。

    Args:
        endpoint_name: 端点显示名称（如 "DeepSeek"）

    Returns:
        是否删除成功
    """
    import re

    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return False

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 找到该端点对应的索引
    target_idx = None
    for line in lines:
        m = re.match(r"^OPENAI_ENDPOINT_(\d+)_NAME\s*=\s*(.+)", line.strip())
        if m and m.group(2).strip() == endpoint_name:
            target_idx = int(m.group(1))
            break

    if target_idx is None:
        return False

    # 过滤掉该索引对应的 4 行
    prefix = f"OPENAI_ENDPOINT_{target_idx}_"
    filtered = [
        line for line in lines
        if not re.match(rf"^{prefix}(NAME|URL|KEY|MODEL)\s*=", line)
    ]

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(filtered)

    # 从 os.environ 中也移除
    for suffix in ("NAME", "URL", "KEY", "MODEL"):
        os.environ.pop(f"OPENAI_ENDPOINT_{target_idx}_{suffix}", None)

    # 重新加载 .env
    load_dotenv(env_path, override=True)

    return True


def update_endpoint_in_env(endpoint_name: str, new_url: str, new_key: str, new_model: str) -> bool:
    """
    更新 .env 文件中指定端点的 URL、KEY、MODEL（NAME 不可修改）。

    Args:
        endpoint_name: 端点显示名称（如 "DeepSeek"）
        new_url: 新的 API 地址
        new_key: 新的 API Key
        new_model: 新的模型名称

    Returns:
        是否更新成功
    """
    import re

    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return False

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 找到该端点对应的索引
    target_idx = None
    for line in lines:
        m = re.match(r"^OPENAI_ENDPOINT_(\d+)_NAME\s*=\s*(.+)", line.strip())
        if m and m.group(2).strip() == endpoint_name:
            target_idx = int(m.group(1))
            break

    if target_idx is None:
        return False

    # 替换 URL、KEY、MODEL 三行
    prefix = f"OPENAI_ENDPOINT_{target_idx}_"
    replacements = {
        f"{prefix}URL": new_url,
        f"{prefix}KEY": new_key,
        f"{prefix}MODEL": new_model,
    }

    new_lines = []
    for line in lines:
        matched = False
        for key, value in replacements.items():
            if re.match(rf"^{key}\s*=", line.strip()):
                new_lines.append(f"{key}={value}\n")
                matched = True
                break
        if not matched:
            new_lines.append(line)

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    # 更新 os.environ
    os.environ[f"OPENAI_ENDPOINT_{target_idx}_URL"] = new_url
    os.environ[f"OPENAI_ENDPOINT_{target_idx}_KEY"] = new_key
    os.environ[f"OPENAI_ENDPOINT_{target_idx}_MODEL"] = new_model

    # 重新加载 .env
    load_dotenv(env_path, override=True)

    return True
