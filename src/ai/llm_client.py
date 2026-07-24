"""
LLM API 客户端
负责与 Ollama 本地大模型通信，生成诊断建议
"""

import json
import time
import threading
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List
from src.config import OLLAMA_BASE_URL, OLLAMA_MODEL_NAME
from src.ai.prompt_templates import PromptTemplates

TEMPERATURE = 0.7
MAX_TOKENS = 1024
CHECK_TIMEOUT = 3
REQUEST_TIMEOUT = 90
MAX_RETRIES = 3


class LLMClient:
    """
    LLM 客户端（Ollama）
    调用本地部署的大模型生成诊断建议
    """

    _instance = None
    _init_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = None, base_url: str = None):
        if self._initialized:
            return

        self.model_name = model_name or OLLAMA_MODEL_NAME
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        self._available = None
        self._avail_lock = threading.Lock()
        self.templates = PromptTemplates()
        self._initialized = True

    def _check_availability(self) -> bool:
        """检查 Ollama 服务是否可用"""
        if self._available is not None:
            return self._available

        with self._avail_lock:
            if self._available is not None:
                return self._available

            try:
                url = f"{self.base_url}/api/tags"
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=CHECK_TIMEOUT) as response:
                    data = json.loads(response.read().decode())
                    models = [m["name"] for m in data.get("models", [])]

                    model_available = any(self.model_name in m for m in models)
                    if not model_available:
                        print(f"  ⚠️ 模型 '{self.model_name}' 未在 Ollama 中找到")
                        print(f"  💡 可用模型: {models[:5]}")
                        print(f"  💡 请运行: ollama pull {self.model_name}")

                    self._available = model_available
                    return model_available

            except Exception as e:
                print(f"  ⚠️ Ollama 服务不可用: {e}")
                print(f"  💡 请确保 Ollama 已启动: ollama serve")
                self._available = False
                return False

    def is_available(self) -> bool:
        """Ollama 服务是否可用"""
        return self._check_availability()

    def get_available_models(self) -> List[str]:
        """获取 Ollama 已安装的模型列表"""
        try:
            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=CHECK_TIMEOUT) as response:
                data = json.loads(response.read().decode())
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def set_model(self, model_name: str):
        """切换模型"""
        self.model_name = model_name
        self._available = None  # 重置可用性缓存

    def get_diagnostic_suggestion(
        self,
        code: str,
        knowledge: Optional[Dict[str, Any]] = None,
        vehicle_info: str = "",
        additional_info: str = ""
    ) -> str:
        """
        获取 AI 诊断建议

        Args:
            code: 故障码
            knowledge: 知识库查询结果（可为 None）
            vehicle_info: 车型信息
            additional_info: 附加描述

        Returns:
            AI 生成的诊断建议文本
        """
        if not self._check_availability():
            return "⚠️ Ollama 服务未启动，请检查后重试"

        # 构建提示词
        prompt = self.templates.build_diagnostic_prompt(
            code=code,
            knowledge=knowledge,
            vehicle_info=vehicle_info,
            additional_info=additional_info
        )

        # 调用 Ollama
        try:
            response = self._call_ollama(prompt)
            return response
        except Exception as e:
            return f"⚠️ AI 诊断生成失败: {str(e)}"

    def chat(self, message: str, context: Optional[List[Dict[str, str]]] = None) -> str:
        """
        与 AI Agent 对话

        Args:
            message: 用户消息
            context: 对话上下文历史

        Returns:
            AI 回复
        """
        if not self._check_availability():
            return "⚠️ Ollama 服务未启动"

        # 构建对话消息
        messages = list(context) if context else []
        messages.append({"role": "user", "content": message})

        # 添加系统提示
        system_prompt = self.templates.get_agent_system_prompt()
        messages.insert(0, {"role": "system", "content": system_prompt})

        try:
            return self._call_ollama_chat(messages)
        except Exception as e:
            return f"⚠️ AI 回复生成失败: {str(e)}"

    def chat_stream(self, message: str, context: Optional[List[Dict[str, str]]] = None):
        """
        与 AI Agent 对话（流式响应）

        Args:
            message: 用户消息
            context: 对话上下文历史

        Yields:
            每个 token 文本
        """
        if not self._check_availability():
            yield "⚠️ Ollama 服务未启动"
            return

        messages = list(context) if context else []
        messages.append({"role": "user", "content": message})

        system_prompt = self.templates.get_agent_system_prompt()
        messages.insert(0, {"role": "system", "content": system_prompt})

        try:
            yield from self._call_ollama_chat_stream(messages)
        except Exception as e:
            yield f"⚠️ AI 回复生成失败: {str(e)}"

    @staticmethod
    def _http_request(url: str, data: bytes, headers: dict, timeout: int = REQUEST_TIMEOUT, max_retries: int = MAX_RETRIES) -> dict:
        """带重试的 HTTP POST 请求"""
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    return json.loads(response.read().decode())
            except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, TimeoutError) as e:
                last_error = e
                if attempt < max_retries:
                    wait = 2 ** attempt
                    print(f"  ⚠️ Ollama 请求失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}，{wait}秒后重试")
                    time.sleep(wait)
        raise last_error

    def _call_ollama(self, prompt: str) -> str:
        """调用 Ollama API (非流式)"""
        url = f"{self.base_url}/api/generate"
        data = json.dumps({
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 1024
            }
        }).encode("utf-8")

        result = self._http_request(
            url, data,
            headers={"Content-Type": "application/json"},
        )
        return result.get("response", "").strip()

    def _call_ollama_chat(self, messages: List[Dict[str, str]]) -> str:
        """调用 Ollama Chat API"""
        url = f"{self.base_url}/api/chat"
        data = json.dumps({
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": TEMPERATURE,
                "num_predict": MAX_TOKENS
            }
        }).encode("utf-8")

        result = self._http_request(
            url, data,
            headers={"Content-Type": "application/json"},
        )
        return result.get("message", {}).get("content", "").strip()

    def _call_ollama_chat_stream(self, messages: List[Dict[str, str]]):
        """调用 Ollama Chat API（流式）"""
        url = f"{self.base_url}/api/chat"
        data = json.dumps({
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": TEMPERATURE,
                "num_predict": MAX_TOKENS
            }
        }).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
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


# 便捷函数
def create_llm_client(model_name: str = "qwen2.5:7b") -> LLMClient:
    """创建 LLM 客户端实例"""
    return LLMClient(model_name=model_name)
