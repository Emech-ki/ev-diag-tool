"""
OpenAI 兼容 API Provider
支持 OpenAI、DeepSeek、vLLM、LM Studio 等任何 OpenAI 兼容接口
"""

import json
import time
import threading
import urllib.request
import urllib.error
from typing import Iterator, List, Dict, Optional, Any

from src.ai.providers import LLMProvider
from src.config import (
    OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL_NAME,
    AI_TEMPERATURE, AI_MAX_TOKENS,
    AI_REQUEST_TIMEOUT, AI_MAX_RETRIES
)

CHECK_TIMEOUT = 5


class OpenAICompatProvider(LLMProvider):
    """OpenAI 兼容 API Provider"""

    def __init__(self, api_key: str = None, base_url: str = None, model_name: str = None):
        self._api_key = api_key or OPENAI_API_KEY
        base = (base_url or OPENAI_BASE_URL).rstrip("/")
        # 自动补全 /v1 后缀（用户可能只填了 https://api.deepseek.com）
        if not base.endswith("/v1"):
            base = base + "/v1"
        self._base_url = base
        self._model_name = model_name or OPENAI_MODEL_NAME
        self._available = None
        self._avail_lock = threading.Lock()

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model_name

    @model_name.setter
    def model_name(self, name: str) -> None:
        self._model_name = name
        self.reset_availability()

    def _check_availability(self) -> bool:
        """检查 OpenAI 兼容 API 是否可用"""
        if self._available is not None:
            return self._available

        with self._avail_lock:
            if self._available is not None:
                return self._available

            if not self._api_key:
                print("  ⚠️ OpenAI API Key 未配置")
                self._available = False
                return False

            try:
                url = f"{self._base_url}/models"
                req = urllib.request.Request(url, method="GET")
                req.add_header("Authorization", f"Bearer {self._api_key}")
                with urllib.request.urlopen(req, timeout=CHECK_TIMEOUT) as response:
                    data = json.loads(response.read().decode())
                    models = [m.get("id", "") for m in data.get("data", [])]

                    model_available = any(self._model_name.lower() in m.lower() for m in models)
                    if not model_available and models:
                        print(f"  ⚠️ 模型 '{self._model_name}' 可能不在可用列表中")
                        print(f"  💡 可用模型: {models[:5]}")

                    # 即使模型不在列表中也标记为可用（某些 API 不返回完整列表）
                    self._available = True
                    return True

            except Exception as e:
                print(f"  ⚠️ OpenAI 兼容 API 不可用: {e}")
                self._available = False
                return False

    def is_available(self) -> bool:
        return self._check_availability()

    def get_models(self) -> List[str]:
        if not self._api_key:
            return []
        try:
            url = f"{self._base_url}/models"
            req = urllib.request.Request(url, method="GET")
            req.add_header("Authorization", f"Bearer {self._api_key}")
            with urllib.request.urlopen(req, timeout=CHECK_TIMEOUT) as response:
                data = json.loads(response.read().decode())
                return [m.get("id", "") for m in data.get("data", [])]
        except Exception:
            return []

    def reset_availability(self):
        self._available = None

    def generate(self, prompt: str, temperature: float = None, max_tokens: int = None) -> str:
        """单次生成 — 使用 chat completions API"""
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, temperature, max_tokens)

    def generate_stream(self, prompt: str, temperature: float = None, max_tokens: int = None) -> Iterator[str]:
        """流式生成 — 使用 chat completions API"""
        messages = [{"role": "user", "content": prompt}]
        yield from self.chat_stream(messages, temperature, max_tokens)

    def chat(self, messages: List[Dict[str, str]], temperature: float = None, max_tokens: int = None) -> str:
        temperature = temperature if temperature is not None else AI_TEMPERATURE
        max_tokens = max_tokens if max_tokens is not None else AI_MAX_TOKENS

        url = f"{self._base_url}/chat/completions"
        data = json.dumps({
            "model": self._model_name,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
            "max_tokens": max_tokens
        }).encode("utf-8")

        result = self._http_request(url, data)
        choices = result.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "").strip()
        return ""

    def chat_stream(self, messages: List[Dict[str, str]], temperature: float = None, max_tokens: int = None) -> Iterator[str]:
        temperature = temperature if temperature is not None else AI_TEMPERATURE
        max_tokens = max_tokens if max_tokens is not None else AI_MAX_TOKENS

        url = f"{self._base_url}/chat/completions"
        data = json.dumps({
            "model": self._model_name,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens
        }).encode("utf-8")

        response = self._open_stream(url, data)
        try:
            raw_buffer = b""
            for raw_chunk in response:
                raw_buffer += raw_chunk
                while b"\n" in raw_buffer:
                    line_bytes, raw_buffer = raw_buffer.split(b"\n", 1)
                    try:
                        line = line_bytes.decode("utf-8").strip()
                    except UnicodeDecodeError:
                        continue  # 跳过不完整的多字节字符
                    if not line:
                        continue
                    # SSE 格式: "data: {...}" 或 "data: [DONE]"
                    if line.startswith("data: "):
                        payload = line[6:]
                        if payload == "[DONE]":
                            break
                        try:
                            chunk = json.loads(payload)
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
        finally:
            response.close()

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[dict],
        temperature: float = None,
        max_tokens: int = None,
    ) -> Dict[str, Any]:
        """
        带工具调用的对话（OpenAI Function Calling）

        请求体新增 "tools" 字段，LLM 可能返回：
        - 普通文本回复: choices[0].message.content 有值，tool_calls 为空
        - 工具调用请求: choices[0].message.tool_calls 有值

        Args:
            messages: 对话历史
            tools: OpenAI function calling 格式的工具定义
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            {"content": "...", "tool_calls": [...]} 或 {"content": "..."}
        """
        temperature = temperature if temperature is not None else AI_TEMPERATURE
        max_tokens = max_tokens if max_tokens is not None else AI_MAX_TOKENS

        url = f"{self._base_url}/chat/completions"
        body = {
            "model": self._model_name,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # 只有传入了工具才加 tools 字段
        if tools:
            body["tools"] = tools

        data = json.dumps(body).encode("utf-8")
        result = self._http_request(url, data)

        choices = result.get("choices", [])
        if not choices:
            return {"content": "", "tool_calls": None}

        message = choices[0].get("message", {})
        content = message.get("content") or ""
        raw_tool_calls = message.get("tool_calls")

        # 解析 tool_calls
        tool_calls = None
        if raw_tool_calls:
            tool_calls = []
            for tc in raw_tool_calls:
                tool_calls.append({
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                })

        return {
            "content": content if content else None,
            "tool_calls": tool_calls,
        }

    def _http_request(self, url: str, data: bytes) -> dict:
        """带重试的 HTTP POST 请求（4xx 客户端错误不重试）"""
        last_error = None
        for attempt in range(max(AI_MAX_RETRIES, 0) + 1):
            try:
                req = urllib.request.Request(url, data=data, method="POST")
                req.add_header("Content-Type", "application/json")
                req.add_header("Authorization", f"Bearer {self._api_key}")
                with urllib.request.urlopen(req, timeout=AI_REQUEST_TIMEOUT) as response:
                    return json.loads(response.read().decode())
            except urllib.error.HTTPError as e:
                if 400 <= e.code < 500:
                    raise
                last_error = e
                if attempt < AI_MAX_RETRIES:
                    wait = 2 ** attempt
                    print(f"  ⚠️ OpenAI API 请求失败 (尝试 {attempt + 1}/{AI_MAX_RETRIES + 1}): {e}，{wait}秒后重试")
                    time.sleep(wait)
            except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
                last_error = e
                if attempt < AI_MAX_RETRIES:
                    wait = 2 ** attempt
                    print(f"  ⚠️ OpenAI API 请求失败 (尝试 {attempt + 1}/{AI_MAX_RETRIES + 1}): {e}，{wait}秒后重试")
                    time.sleep(wait)
        raise last_error

    def _open_stream(self, url: str, data: bytes):
        """打开流式连接（仅连接阶段重试）"""
        last_error = None
        for attempt in range(max(AI_MAX_RETRIES, 0) + 1):
            try:
                req = urllib.request.Request(url, data=data, method="POST")
                req.add_header("Content-Type", "application/json")
                req.add_header("Authorization", f"Bearer {self._api_key}")
                return urllib.request.urlopen(req, timeout=AI_REQUEST_TIMEOUT)
            except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, TimeoutError) as e:
                last_error = e
                if attempt < AI_MAX_RETRIES:
                    wait = 2 ** attempt
                    print(f"  ⚠️ OpenAI API 流式连接失败 (尝试 {attempt + 1}/{AI_MAX_RETRIES + 1}): {e}，{wait}秒后重试")
                    time.sleep(wait)
                else:
                    raise last_error
