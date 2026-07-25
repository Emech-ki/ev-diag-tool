"""
LLM Provider 抽象层
定义统一的 LLM 调用接口，支持多种后端（Ollama、OpenAI 兼容 API）
"""

from abc import ABC, abstractmethod
from typing import Iterator, List, Dict, Optional


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

__all__ = ["LLMProvider", "OllamaProvider", "OpenAICompatProvider"]
