"""
LLM API 客户端（代理层）
根据配置选择 Ollama 或 OpenAI 兼容 Provider，支持多端点切换
"""

import threading
from typing import Optional, Dict, Any, List, Iterator

from src.config import (
    AI_PROVIDER, OLLAMA_BASE_URL, OLLAMA_MODEL_NAME,
    OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL_NAME,
    AI_TEMPERATURE, AI_MAX_TOKENS, get_remote_endpoints
)
from src.ai.providers import LLMProvider, StreamEvent, OllamaProvider, OpenAICompatProvider
from src.ai.prompt_templates import PromptTemplates


def create_provider(provider_name: str = None, **kwargs) -> LLMProvider:
    """
    工厂函数：根据名称创建对应的 LLM Provider

    Args:
        provider_name: "ollama" 或 "openai"，默认从 config 读取
        **kwargs: 传递给 provider 构造函数的额外参数

    Returns:
        LLMProvider 实例
    """
    name = (provider_name or AI_PROVIDER).lower().strip()

    if name == "openai":
        return OpenAICompatProvider(
            api_key=kwargs.get("api_key"),
            base_url=kwargs.get("base_url"),
            model_name=kwargs.get("model_name"),
        )
    else:
        # 默认 Ollama
        return OllamaProvider(
            model_name=kwargs.get("model_name"),
            base_url=kwargs.get("base_url"),
        )


class LLMClient:
    """
    LLM 客户端（代理）
    委托给当前活跃的 LLMProvider，支持多端点管理
    """

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, provider: LLMProvider = None):
        if self._initialized:
            return
        self._provider = provider or create_provider()
        self._provider_lock = threading.Lock()
        self.templates = PromptTemplates()
        self._initialized = True

    @property
    def provider(self) -> LLMProvider:
        """当前活跃的 provider（线程安全读取）"""
        with self._provider_lock:
            return self._provider

    @property
    def model_name(self) -> str:
        with self._provider_lock:
            return self._provider.model_name

    @model_name.setter
    def model_name(self, name: str) -> None:
        with self._provider_lock:
            self._provider.model_name = name

    @property
    def is_local(self) -> bool:
        """当前是否使用本地模型"""
        with self._provider_lock:
            return self._provider.provider_name == "ollama"

    @property
    def current_endpoint_name(self) -> str:
        """当前端点显示名称"""
        with self._provider_lock:
            if self._provider.provider_name == "ollama":
                return "本地模型"
            return getattr(self._provider, "_endpoint_name", "调用模型")

    def get_remote_endpoints(self) -> List[Dict[str, Any]]:
        """获取已配置的远程端点列表"""
        return get_remote_endpoints()

    def set_provider(self, provider: LLMProvider):
        """切换 provider（线程安全）"""
        with self._provider_lock:
            self._provider = provider

    def switch_provider(self, provider_name: str, **kwargs):
        """按名称切换 provider（线程安全）"""
        new_provider = create_provider(provider_name, **kwargs)
        if "name" in kwargs:
            new_provider._endpoint_name = kwargs["name"]
        with self._provider_lock:
            self._provider = new_provider

    def switch_to_local(self):
        """切换到本地 Ollama（线程安全）"""
        with self._provider_lock:
            self._provider = OllamaProvider(
                model_name=OLLAMA_MODEL_NAME,
                base_url=OLLAMA_BASE_URL,
            )

    def switch_to_remote(self, endpoint_name: str) -> bool:
        """
        切换到指定名称的远程端点（线程安全）

        Args:
            endpoint_name: 端点名称（如 "DeepSeek"）

        Returns:
            是否切换成功
        """
        endpoints = get_remote_endpoints()
        for ep in endpoints:
            if ep["name"].lower() == endpoint_name.lower():
                provider = OpenAICompatProvider(
                    api_key=ep["api_key"],
                    base_url=ep["base_url"],
                    model_name=ep["model_name"],
                )
                provider._endpoint_name = ep["name"]
                with self._provider_lock:
                    self._provider = provider
                return True
        return False

    def is_available(self) -> bool:
        with self._provider_lock:
            return self._provider.is_available()

    def get_available_models(self) -> List[str]:
        with self._provider_lock:
            return self._provider.get_models()

    def reset_availability(self):
        with self._provider_lock:
            self._provider.reset_availability()

    def set_model(self, model_name: str):
        with self._provider_lock:
            self._provider.model_name = model_name

    def get_diagnostic_suggestion(
        self,
        code: str,
        knowledge: Optional[Dict[str, Any]] = None,
        vehicle_info: str = "",
        additional_info: str = ""
    ) -> str:
        """获取 AI 诊断建议"""
        with self._provider_lock:
            provider = self._provider
        if not provider.is_available():
            return "[警告] AI 服务未启动，请检查后重试"

        prompt = self.templates.build_diagnostic_prompt(
            code=code,
            knowledge=knowledge,
            vehicle_info=vehicle_info,
            additional_info=additional_info
        )

        try:
            return provider.generate(prompt, AI_TEMPERATURE, AI_MAX_TOKENS)
        except Exception as e:
            return f"[警告] AI 诊断生成失败: {str(e)}"

    def get_diagnostic_suggestion_stream(
        self,
        code: str,
        knowledge: Optional[Dict[str, Any]] = None,
        vehicle_info: str = "",
        additional_info: str = ""
    ) -> Iterator[str]:
        """获取 AI 诊断建议（流式）"""
        with self._provider_lock:
            provider = self._provider
        if not provider.is_available():
            yield "[警告] AI 服务未启动，请检查后重试"
            return

        prompt = self.templates.build_diagnostic_prompt(
            code=code,
            knowledge=knowledge,
            vehicle_info=vehicle_info,
            additional_info=additional_info
        )

        try:
            yield from provider.generate_stream(prompt, AI_TEMPERATURE, AI_MAX_TOKENS)
        except Exception as e:
            yield f"[警告] AI 诊断生成失败: {str(e)}"

    def chat(self, message: str, context: Optional[List[Dict[str, str]]] = None) -> str:
        """与 AI Agent 对话"""
        with self._provider_lock:
            provider = self._provider
        if not provider.is_available():
            return "[警告] AI 服务未启动"

        messages = list(context) if context else []
        messages.append({"role": "user", "content": message})

        # 仅在没有系统提示词时插入
        if not messages or messages[0].get("role") != "system":
            system_prompt = self.templates.get_agent_system_prompt()
            messages.insert(0, {"role": "system", "content": system_prompt})

        try:
            return provider.chat(messages, AI_TEMPERATURE, AI_MAX_TOKENS)
        except Exception as e:
            return f"[警告] AI 回复生成失败: {str(e)}"

    def chat_stream(self, message: str, context: Optional[List[Dict[str, str]]] = None) -> Iterator[str]:
        """与 AI Agent 对话（流式响应）"""
        with self._provider_lock:
            provider = self._provider
        if not provider.is_available():
            yield "[警告] AI 服务未启动"
            return

        messages = list(context) if context else []
        messages.append({"role": "user", "content": message})

        # 仅在没有系统提示词时插入
        if not messages or messages[0].get("role") != "system":
            system_prompt = self.templates.get_agent_system_prompt()
            messages.insert(0, {"role": "system", "content": system_prompt})

        try:
            yield from provider.chat_stream(messages, AI_TEMPERATURE, AI_MAX_TOKENS)
        except Exception as e:
            yield f"[警告] AI 回复生成失败: {str(e)}"

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[dict],
        temperature: float = None,
        max_tokens: int = None,
    ) -> Dict[str, Any]:
        """
        带工具调用的对话（代理到当前 provider）

        Args:
            messages: 对话历史
            tools: OpenAI function calling 格式的工具定义
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            {"content": "...", "tool_calls": [...]} 或 {"content": "..."}
        """
        with self._provider_lock:
            provider = self._provider
        if not provider.is_available():
            return {"content": "[警告] AI 服务未启动", "tool_calls": None}

        try:
            return provider.chat_with_tools(
                messages, tools,
                temperature if temperature is not None else AI_TEMPERATURE,
                max_tokens if max_tokens is not None else AI_MAX_TOKENS,
            )
        except Exception as e:
            return {"content": f"[警告] AI 调用失败: {str(e)}", "tool_calls": None}

    def chat_with_tools_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: List[dict],
        temperature: float = None,
        max_tokens: int = None,
    ) -> Iterator[StreamEvent]:
        """
        带工具调用的流式对话（代理到当前 provider）

        Yields:
            StreamEvent: content → tool_calls → done
        """
        with self._provider_lock:
            provider = self._provider
        if not provider.is_available():
            yield StreamEvent("content", content="[警告] AI 服务未启动")
            yield StreamEvent("done")
            return

        try:
            yield from provider.chat_with_tools_stream(
                messages, tools,
                temperature if temperature is not None else AI_TEMPERATURE,
                max_tokens if max_tokens is not None else AI_MAX_TOKENS,
            )
        except Exception as e:
            yield StreamEvent("content", content=f"[警告] AI 调用失败: {str(e)}")
            yield StreamEvent("done")

    def get_multi_code_suggestion(
        self,
        codes: List[str],
        results: List[Any],
        correlation: Any,
        vehicle_info: str = "",
        additional_info: str = "",
    ) -> str:
        """获取多故障码综合 AI 建议"""
        with self._provider_lock:
            provider = self._provider
        if not provider.is_available():
            return "[警告] AI 服务未启动"

        # 将 DiagnosticResult 转为 dict
        kb_dicts = []
        for r in results:
            if r and hasattr(r, 'knowledge') and r.knowledge:
                kb_dicts.append(r.knowledge)
            elif r and isinstance(r, dict):
                kb_dicts.append(r)
            else:
                kb_dicts.append(None)

        prompt = self.templates.build_multi_diagnostic_prompt(
            codes=codes,
            results=kb_dicts,
            correlation_summary=correlation.analysis_summary,
            vehicle_info=vehicle_info,
            additional_info=additional_info,
        )

        try:
            return provider.generate(prompt, AI_TEMPERATURE, AI_MAX_TOKENS)
        except Exception as e:
            return f"[警告] 综合 AI 诊断失败: {str(e)}"

    def get_multi_code_suggestion_stream(
        self,
        codes: List[str],
        results: List[Any],
        correlation: Any,
        vehicle_info: str = "",
        additional_info: str = "",
    ) -> Iterator[str]:
        """获取多故障码综合 AI 建议（流式）"""
        with self._provider_lock:
            provider = self._provider
        if not provider.is_available():
            yield "[警告] AI 服务未启动"
            return

        kb_dicts = []
        for r in results:
            if r and hasattr(r, 'knowledge') and r.knowledge:
                kb_dicts.append(r.knowledge)
            elif r and isinstance(r, dict):
                kb_dicts.append(r)
            else:
                kb_dicts.append(None)

        prompt = self.templates.build_multi_diagnostic_prompt(
            codes=codes,
            results=kb_dicts,
            correlation_summary=correlation.analysis_summary,
            vehicle_info=vehicle_info,
            additional_info=additional_info,
        )

        try:
            yield from provider.generate_stream(prompt, AI_TEMPERATURE, AI_MAX_TOKENS)
        except Exception as e:
            yield f"[警告] 综合 AI 诊断失败: {str(e)}"


# 便捷函数
def create_llm_client(provider_name: str = None, **kwargs) -> LLMClient:
    """创建 LLM 客户端实例"""
    provider = create_provider(provider_name, **kwargs)
    return LLMClient(provider=provider)
