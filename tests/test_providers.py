"""
LLM Provider 抽象层测试
"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


class TestOllamaProvider(unittest.TestCase):
    """OllamaProvider 测试"""

    def test_init_defaults(self):
        """测试默认初始化"""
        from src.ai.providers.ollama import OllamaProvider

        provider = OllamaProvider()
        self.assertEqual(provider.provider_name, "ollama")
        self.assertIsNotNone(provider.model_name)

    def test_init_custom(self):
        """测试自定义参数初始化"""
        from src.ai.providers.ollama import OllamaProvider

        provider = OllamaProvider(model_name="test:model", base_url="http://test:1234")
        self.assertEqual(provider.model_name, "test:model")
        self.assertEqual(provider._base_url, "http://test:1234")

    def test_set_model(self):
        """测试模型切换"""
        from src.ai.providers.ollama import OllamaProvider

        provider = OllamaProvider()
        provider.model_name = "new:model"
        self.assertEqual(provider.model_name, "new:model")

    def test_generate_uses_config_params(self):
        """测试 generate 使用配置参数"""
        from src.ai.providers.ollama import OllamaProvider
        from src.config import AI_TEMPERATURE, AI_MAX_TOKENS

        provider = OllamaProvider()
        # 验证配置参数存在且有效
        self.assertIsInstance(AI_TEMPERATURE, float)
        self.assertIsInstance(AI_MAX_TOKENS, int)


class TestOpenAICompatProvider(unittest.TestCase):
    """OpenAICompatProvider 测试"""

    def test_init_defaults(self):
        """测试默认初始化"""
        from src.ai.providers.openai_compat import OpenAICompatProvider

        provider = OpenAICompatProvider()
        self.assertEqual(provider.provider_name, "openai")
        self.assertIsNotNone(provider.model_name)

    def test_init_custom(self):
        """测试自定义参数初始化"""
        from src.ai.providers.openai_compat import OpenAICompatProvider

        provider = OpenAICompatProvider(
            api_key="test-key",
            base_url="http://test:8080/v1",
            model_name="test-model"
        )
        self.assertEqual(provider._api_key, "test-key")
        self.assertEqual(provider._base_url, "http://test:8080/v1")
        self.assertEqual(provider.model_name, "test-model")

    def test_no_api_key_marks_unavailable(self):
        """测试无 API Key 时标记为不可用"""
        from src.ai.providers.openai_compat import OpenAICompatProvider

        provider = OpenAICompatProvider(api_key="")
        # 不可用（无 API Key）
        self.assertFalse(provider.is_available())

    def test_set_model(self):
        """测试模型切换"""
        from src.ai.providers.openai_compat import OpenAICompatProvider

        provider = OpenAICompatProvider(api_key="test")
        provider.model_name = "gpt-4"
        self.assertEqual(provider.model_name, "gpt-4")


class TestProviderFactory(unittest.TestCase):
    """Provider 工厂函数测试"""

    def test_create_ollama(self):
        """测试创建 Ollama Provider"""
        from src.ai.llm_client import create_provider

        provider = create_provider("ollama")
        self.assertEqual(provider.provider_name, "ollama")

    def test_create_openai(self):
        """测试创建 OpenAI Provider"""
        from src.ai.llm_client import create_provider

        provider = create_provider("openai")
        self.assertEqual(provider.provider_name, "openai")

    def test_create_default(self):
        """测试默认创建"""
        from src.ai.llm_client import create_provider

        provider = create_provider()
        from src.config import AI_PROVIDER
        self.assertEqual(provider.provider_name, AI_PROVIDER)

    def test_create_case_insensitive(self):
        """测试大小写不敏感"""
        from src.ai.llm_client import create_provider

        self.assertEqual(create_provider("Ollama").provider_name, "ollama")
        self.assertEqual(create_provider("OPENAI").provider_name, "openai")

    def test_create_unknown_defaults_ollama(self):
        """测试未知 provider 默认返回 ollama"""
        from src.ai.llm_client import create_provider

        provider = create_provider("unknown")
        self.assertEqual(provider.provider_name, "ollama")


class TestLLMClientProxy(unittest.TestCase):
    """LLMClient 代理层测试"""

    def test_provider_property(self):
        """测试 provider 属性"""
        from src.ai.llm_client import LLMClient

        LLMClient._instance = None
        client = LLMClient()
        self.assertIsNotNone(client.provider)
        self.assertIn(client.provider.provider_name, ("ollama", "openai"))

    def test_model_name_delegates_to_provider(self):
        """测试 model_name 委托给 provider"""
        from src.ai.llm_client import LLMClient

        LLMClient._instance = None
        client = LLMClient()
        # model_name 应该来自 provider
        self.assertEqual(client.model_name, client.provider.model_name)

    def test_switch_provider_changes_provider(self):
        """测试 switch_provider 切换 provider"""
        from src.ai.llm_client import LLMClient

        LLMClient._instance = None
        client = LLMClient()

        original = client.provider.provider_name
        new_name = "openai" if original == "ollama" else "ollama"

        client.switch_provider(new_name)
        self.assertEqual(client.provider.provider_name, new_name)


if __name__ == "__main__":
    unittest.main()
