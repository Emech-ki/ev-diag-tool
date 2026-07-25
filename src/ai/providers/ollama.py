"""
Ollama LLM Provider
通过 Ollama HTTP API 调用本地大模型
"""

import json
import time
import threading
import urllib.request
import urllib.error
from typing import Iterator, List, Dict, Optional, Any

from src.ai.providers import LLMProvider
from src.config import (
    OLLAMA_BASE_URL, OLLAMA_MODEL_NAME,
    AI_TEMPERATURE, AI_MAX_TOKENS,
    AI_REQUEST_TIMEOUT, AI_MAX_RETRIES
)

CHECK_TIMEOUT = 3


class OllamaProvider(LLMProvider):
    """Ollama 本地模型 Provider"""

    def __init__(self, model_name: str = None, base_url: str = None):
        self._model_name = model_name or OLLAMA_MODEL_NAME
        self._base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        self._available = None
        self._avail_lock = threading.Lock()

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model_name

    @model_name.setter
    def model_name(self, name: str) -> None:
        self._model_name = name
        self.reset_availability()

    def _check_availability(self) -> bool:
        """检查 Ollama 服务是否可用"""
        if self._available is not None:
            return self._available

        with self._avail_lock:
            if self._available is not None:
                return self._available

            try:
                url = f"{self._base_url}/api/tags"
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=CHECK_TIMEOUT) as response:
                    data = json.loads(response.read().decode())
                    models = [m["name"] for m in data.get("models", [])]

                    model_available = any(self._model_name.lower() in m.lower() for m in models)
                    if not model_available:
                        print(f"  ⚠️ 模型 '{self._model_name}' 未在 Ollama 中找到")
                        print(f"  💡 可用模型: {models[:5]}")
                        print(f"  💡 请运行: ollama pull {self._model_name}")

                    self._available = model_available
                    return model_available

            except Exception as e:
                print(f"  ⚠️ Ollama 服务不可用: {e}")
                print(f"  💡 请确保 Ollama 已启动: ollama serve")
                self._available = False
                return False

    def is_available(self) -> bool:
        return self._check_availability()

    def get_models(self) -> List[str]:
        try:
            url = f"{self._base_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=CHECK_TIMEOUT) as response:
                data = json.loads(response.read().decode())
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def reset_availability(self):
        self._available = None

    def generate(self, prompt: str, temperature: float = None, max_tokens: int = None) -> str:
        temperature = temperature if temperature is not None else AI_TEMPERATURE
        max_tokens = max_tokens if max_tokens is not None else AI_MAX_TOKENS

        url = f"{self._base_url}/api/generate"
        data = json.dumps({
            "model": self._model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }).encode("utf-8")

        result = self._http_request(url, data)
        return result.get("response", "").strip()

    def generate_stream(self, prompt: str, temperature: float = None, max_tokens: int = None) -> Iterator[str]:
        temperature = temperature if temperature is not None else AI_TEMPERATURE
        max_tokens = max_tokens if max_tokens is not None else AI_MAX_TOKENS

        url = f"{self._base_url}/api/generate"
        data = json.dumps({
            "model": self._model_name,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }).encode("utf-8")

        response = self._open_stream(url, data)
        try:
            for line in response:
                if not line:
                    continue
                try:
                    chunk = json.loads(line.decode("utf-8"))
                    token = chunk.get("response", "")
                    if token:
                        yield token
                    if chunk.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue
        finally:
            response.close()

    def chat(self, messages: List[Dict[str, str]], temperature: float = None, max_tokens: int = None) -> str:
        temperature = temperature if temperature is not None else AI_TEMPERATURE
        max_tokens = max_tokens if max_tokens is not None else AI_MAX_TOKENS

        url = f"{self._base_url}/api/chat"
        data = json.dumps({
            "model": self._model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }).encode("utf-8")

        result = self._http_request(url, data)
        return result.get("message", {}).get("content", "").strip()

    def chat_stream(self, messages: List[Dict[str, str]], temperature: float = None, max_tokens: int = None) -> Iterator[str]:
        temperature = temperature if temperature is not None else AI_TEMPERATURE
        max_tokens = max_tokens if max_tokens is not None else AI_MAX_TOKENS

        url = f"{self._base_url}/api/chat"
        data = json.dumps({
            "model": self._model_name,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }).encode("utf-8")

        response = self._open_stream(url, data)
        try:
            for line in response:
                if not line:
                    continue
                try:
                    chunk = json.loads(line.decode("utf-8"))
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if chunk.get("done", False):
                        break
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
        带工具调用的对话（Ollama Tool Calling）

        Ollama 从 0.4.0+ 支持 /api/chat 的 tools 参数，
        格式与 OpenAI function calling 兼容。

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

        url = f"{self._base_url}/api/chat"
        body = {
            "model": self._model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        # 只有传入了工具才加 tools 字段
        if tools:
            body["tools"] = tools

        data = json.dumps(body).encode("utf-8")
        result = self._http_request(url, data)

        message = result.get("message", {})
        content = message.get("content") or ""
        raw_tool_calls = message.get("tool_calls")

        # 解析 Ollama 的 tool_calls 格式
        # Ollama 返回: [{"function": {"name": "...", "arguments": {...}}}]
        tool_calls = None
        if raw_tool_calls:
            tool_calls = []
            for i, tc in enumerate(raw_tool_calls):
                func = tc.get("function", {})
                # Ollama 的 arguments 可能已经是 dict，需要转为 JSON 字符串
                args = func.get("arguments", {})
                if isinstance(args, dict):
                    args_str = json.dumps(args, ensure_ascii=False)
                else:
                    args_str = str(args)

                tool_calls.append({
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": func.get("name", ""),
                        "arguments": args_str,
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
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=AI_REQUEST_TIMEOUT) as response:
                    return json.loads(response.read().decode())
            except urllib.error.HTTPError as e:
                # 4xx 客户端错误（如 400 Bad Request）不重试，直接抛出
                if 400 <= e.code < 500:
                    raise
                last_error = e
                if attempt < AI_MAX_RETRIES:
                    wait = 2 ** attempt
                    print(f"  ⚠️ Ollama 请求失败 (尝试 {attempt + 1}/{AI_MAX_RETRIES + 1}): {e}，{wait}秒后重试")
                    time.sleep(wait)
            except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
                last_error = e
                if attempt < AI_MAX_RETRIES:
                    wait = 2 ** attempt
                    print(f"  ⚠️ Ollama 请求失败 (尝试 {attempt + 1}/{AI_MAX_RETRIES + 1}): {e}，{wait}秒后重试")
                    time.sleep(wait)
        raise last_error

    def _open_stream(self, url: str, data: bytes):
        """打开流式连接（仅连接阶段重试）"""
        last_error = None
        for attempt in range(max(AI_MAX_RETRIES, 0) + 1):
            try:
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
                return urllib.request.urlopen(req, timeout=AI_REQUEST_TIMEOUT)
            except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, TimeoutError) as e:
                last_error = e
                if attempt < AI_MAX_RETRIES:
                    wait = 2 ** attempt
                    print(f"  ⚠️ Ollama 流式连接失败 (尝试 {attempt + 1}/{AI_MAX_RETRIES + 1}): {e}，{wait}秒后重试")
                    time.sleep(wait)
                else:
                    raise last_error
