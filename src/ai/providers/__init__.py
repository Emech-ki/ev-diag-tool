"""
LLM Provider 抽象层
定义统一的 LLM 调用接口，支持多种后端（Ollama、OpenAI 兼容 API）
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, List, Dict, Optional, Any


@dataclass
class StreamEvent:
    """
    流式事件 — 用于流式 Tool Calling 的统一事件类型

    类比硬件中断:
      type="content"    → 数据就绪中断（收到一个 token）
      type="tool_calls" → 外设请求中断（LLM 想调用工具）
      type="done"       → 传输完成中断（本轮结束）
    """
    type: str                               # "content" | "tool_calls" | "done"
    content: str = ""                       # 文本 token（type="content" 时）
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)  # 工具调用列表


class LLMProvider(ABC):
    """LLM Provider 抽象基类"""

    @abstractmethod
    def is_available(self) -> bool:
        """检查 provider 是否可用"""
        ...

    @abstractmethod
    def get_models(self) -> List[str]:
        """获取可用模型列表"""
        ...

    @abstractmethod
    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 1024) -> str:
        """单次生成（非流式）"""
        ...

    @abstractmethod
    def generate_stream(self, prompt: str, temperature: float = 0.7, max_tokens: int = 1024) -> Iterator[str]:
        """流式生成"""
        ...

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 1024) -> str:
        """多轮对话（非流式）"""
        ...

    @abstractmethod
    def chat_stream(self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 1024) -> Iterator[str]:
        """多轮对话（流式）"""
        ...

    @abstractmethod
    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """
        带工具调用的对话（Tool Calling）

        Args:
            messages: 对话历史，格式同 chat()
            tools: OpenAI function calling 格式的工具定义列表
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            dict: {
                "content": str | None,       # LLM 的文本回复（可能为 None）
                "tool_calls": list | None    # 工具调用请求列表（可能为 None）
            }
            当 tool_calls 为空/None 时，表示 LLM 给出最终回答
        """
        ...

    def chat_with_tools_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Iterator[StreamEvent]:
        """
        带工具调用的流式对话（默认实现：回退到非流式）

        子类可覆盖此方法提供真正的流式实现。
        默认实现调用非流式 chat_with_tools 然后包装为 StreamEvent。

        Yields:
            StreamEvent: content → tool_calls → done
        """
        result = self.chat_with_tools(messages, tools, temperature, max_tokens)
        content = result.get("content")
        tool_calls = result.get("tool_calls")
        if content:
            yield StreamEvent("content", content=content)
        if tool_calls:
            yield StreamEvent("tool_calls", tool_calls=tool_calls)
        yield StreamEvent("done")

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider 名称标识"""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """当前模型名称"""
        ...

    @model_name.setter
    @abstractmethod
    def model_name(self, name: str) -> None:
        """切换模型"""
        ...


from src.ai.providers.ollama import OllamaProvider
from src.ai.providers.openai_compat import OpenAICompatProvider

__all__ = ["LLMProvider", "StreamEvent", "OllamaProvider", "OpenAICompatProvider"]
