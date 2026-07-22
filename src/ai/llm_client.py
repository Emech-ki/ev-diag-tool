"""
LLM API 客户端
负责与 Ollama 本地大模型通信，生成诊断建议
"""

import json
from typing import Optional, Dict, Any, List
from src.ai.prompt_templates import PromptTemplates


class LLMClient:
    """
    LLM 客户端（Ollama）
    调用本地部署的大模型生成诊断建议
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = "qwen2.5:7b", base_url: str = "http://localhost:11434"):
        if self._initialized:
            return

        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self._available = None
        self.templates = PromptTemplates()
        self._initialized = True

    def _check_availability(self) -> bool:
        """检查 Ollama 服务是否可用"""
        if self._available is not None:
            return self._available

        try:
            import urllib.request
            import json

            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as response:
                data = json.loads(response.read().decode())
                models = [m["name"] for m in data.get("models", [])]

                # 检查指定模型是否已拉取
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

    def _call_ollama(self, prompt: str) -> str:
        """
        调用 Ollama API (非流式)

        Args:
            prompt: 输入提示词

        Returns:
            模型回复文本
        """
        import urllib.request

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

        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            return result.get("response", "").strip()

    def _call_ollama_chat(self, messages: List[Dict[str, str]]) -> str:
        """
        调用 Ollama Chat API

        Args:
            messages: 消息列表 [{"role": "system/user/assistant", "content": "..."}]

        Returns:
            模型回复文本
        """
        import urllib.request

        url = f"{self.base_url}/api/chat"
        data = json.dumps({
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 1024
            }
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            return result.get("message", {}).get("content", "").strip()


# 便捷函数
def create_llm_client(model_name: str = "qwen2.5:7b") -> LLMClient:
    """创建 LLM 客户端实例"""
    return LLMClient(model_name=model_name)
