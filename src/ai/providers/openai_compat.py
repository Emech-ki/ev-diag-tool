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

from src.ai.providers import LLMProvider, StreamEvent
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

    def chat_with_tools_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: List[dict],
        temperature: float = None,
        max_tokens: int = None,
    ) -> Iterator[StreamEvent]:
        """
        带工具调用的流式对话（OpenAI 兼容 API）

        OpenAI 流式格式中，tool_calls 以增量片段出现：
          delta.tool_calls[0].function.name   → 第一个 tool_call 的名称
          delta.tool_calls[0].function.arguments → 逐片段拼接参数 JSON

        实现逻辑：
        1. 发送 stream=True + tools 请求
        2. 逐 SSE 行解析
        3. delta 有 content → yield content token
        4. delta 有 tool_calls → 按 index 缓冲 name + arguments
        5. 流结束时，yield 缓冲好的完整 tool_calls
        """
        temperature = temperature if temperature is not None else AI_TEMPERATURE
        max_tokens = max_tokens if max_tokens is not None else AI_MAX_TOKENS

        url = f"{self._base_url}/chat/completions"
        body = {
            "model": self._model_name,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = tools

        data = json.dumps(body).encode("utf-8")
        response = self._open_stream(url, data)

        # 按 index 缓冲 tool_calls
        # tc_buffer[index] = {"id": "...", "name": "...", "arguments": "..."}
        tc_buffer: Dict[int, Dict[str, str]] = {}
        tool_calls_detected = False
        stream_ended = False

        try:
            raw_buffer = b""
            for raw_chunk in response:
                raw_buffer += raw_chunk
                while b"\n" in raw_buffer:
                    line_bytes, raw_buffer = raw_buffer.split(b"\n", 1)
                    try:
                        line = line_bytes.decode("utf-8").strip()
                    except UnicodeDecodeError:
                        continue
                    if not line:
                        continue
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        stream_ended = True
                        break
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    finish_reason = choices[0].get("finish_reason")

                    # 处理 content token（仅在未检测到 tool_calls 且流未结束时）
                    if not tool_calls_detected and not stream_ended:
                        content = delta.get("content", "")
                        if content:
                            yield StreamEvent("content", content=content)

                    # 处理增量 tool_calls
                    raw_tc_list = delta.get("tool_calls")
                    if raw_tc_list:
                        for tc_delta in raw_tc_list:
                            idx = tc_delta.get("index", 0)
                            if idx not in tc_buffer:
                                tc_buffer[idx] = {"id": "", "name": "", "arguments": ""}
                            if tc_delta.get("id"):
                                tc_buffer[idx]["id"] = tc_delta["id"]
                            func_delta = tc_delta.get("function", {})
                            if func_delta.get("name"):
                                tc_buffer[idx]["name"] = func_delta["name"]
                            if func_delta.get("arguments"):
                                tc_buffer[idx]["arguments"] += func_delta["arguments"]

                    # finish_reason="tool_calls" 表示工具调用完成
                    if finish_reason == "tool_calls":
                        tool_calls_detected = True
                        break

                if tool_calls_detected or stream_ended:
                    break

        finally:
            response.close()

        # 如果缓冲区有 tool_calls，yield 完整的 tool_calls 事件
        if tc_buffer:
            parsed_calls = []
            for idx in sorted(tc_buffer.keys()):
                tc = tc_buffer[idx]
                parsed_calls.append({
                    "id": tc["id"] or f"call_{idx}",
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    },
                })
            yield StreamEvent("tool_calls", tool_calls=parsed_calls)

        yield StreamEvent("done")

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
