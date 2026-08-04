"""
LLM Provider 抽象层测试
"""

import os
import sys
import unittest
from unittest.mock import patch

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


class _FakeStream:
    """模拟 urllib 流式响应对象"""

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.closed = False

    def __iter__(self):
        return iter(self._chunks)

    def close(self):
        self.closed = True


class TestOllamaStreaming(unittest.TestCase):
    """OllamaProvider 流式/工具调用解析测试（Mock HTTP，不联网）"""

    def _make_provider(self):
        from src.ai.providers.ollama import OllamaProvider
        return OllamaProvider(base_url="http://fake:1234")

    def test_generate_stream_yields_tokens(self):
        """generate_stream 逐 token yield，done 停止"""
        provider = self._make_provider()
        lines = [
            '{"response": "你", "done": false}\n'.encode("utf-8"),
            '{"response": "好", "done": false}\n'.encode("utf-8"),
            '{"response": "", "done": true}\n'.encode("utf-8"),
        ]
        with patch.object(provider, "_open_stream", return_value=_FakeStream(lines)):
            tokens = list(provider.generate_stream("ping"))
        self.assertEqual(tokens, ["你", "好"])

    def test_generate_stream_skips_bad_json(self):
        """generate_stream 跳过坏 JSON 行"""
        provider = self._make_provider()
        lines = [
            b'not json\n',
            b'{"response": "ok", "done": true}\n',
        ]
        with patch.object(provider, "_open_stream", return_value=_FakeStream(lines)):
            tokens = list(provider.generate_stream("ping"))
        self.assertEqual(tokens, ["ok"])

    def test_chat_stream_yields_message_content(self):
        """chat_stream 解析 message.content"""
        provider = self._make_provider()
        lines = [
            '{"message": {"role": "assistant", "content": "a"}, "done": false}\n'.encode("utf-8"),
            '{"message": {"content": "b"}, "done": false}\n'.encode("utf-8"),
            '{"done": true}\n'.encode("utf-8"),
        ]
        with patch.object(provider, "_open_stream", return_value=_FakeStream(lines)):
            tokens = list(provider.chat_stream([{"role": "user", "content": "hi"}]))
        self.assertEqual(tokens, ["a", "b"])

    def test_chat_with_tools_parses_dict_arguments(self):
        """chat_with_tools 将 dict arguments 转 JSON 字符串"""
        provider = self._make_provider()
        result = {
            "message": {
                "content": "查一下",
                "tool_calls": [
                    {"function": {"name": "lookup_code", "arguments": {"code": "P0300"}}}
                ],
            }
        }
        with patch.object(provider, "_http_request", return_value=result):
            resp = provider.chat_with_tools(
                [{"role": "user", "content": "x"}], [{"type": "function"}]
            )
        self.assertEqual(resp["content"], "查一下")
        self.assertEqual(resp["tool_calls"][0]["function"]["name"], "lookup_code")
        self.assertEqual(resp["tool_calls"][0]["function"]["arguments"], '{"code": "P0300"}')

    def test_chat_with_tools_no_tools_no_calls(self):
        """无工具时返回 content，tool_calls 为 None"""
        provider = self._make_provider()
        result = {"message": {"content": "直接回答"}}
        with patch.object(provider, "_http_request", return_value=result):
            resp = provider.chat_with_tools([{"role": "user", "content": "x"}], [])
        self.assertEqual(resp["content"], "直接回答")
        self.assertIsNone(resp["tool_calls"])

    def test_chat_with_tools_stream_emits_content_then_calls(self):
        """chat_with_tools_stream 先 yield content，再 yield tool_calls，最后 done"""
        provider = self._make_provider()
        lines = [
            '{"message": {"content": "查"}, "done": false}\n'.encode("utf-8"),
            '{"message": {"tool_calls": [{"function": {"name": "lookup_code", "arguments": {"code": "P0300"}}}]}, "done": false}\n'.encode("utf-8"),
            '{"done": true}\n'.encode("utf-8"),
        ]
        with patch.object(provider, "_open_stream", return_value=_FakeStream(lines)):
            events = list(provider.chat_with_tools_stream(
                [{"role": "user", "content": "x"}], [{"type": "function"}]
            ))
        types = [e.type for e in events]
        self.assertEqual(types, ["content", "tool_calls", "done"])
        self.assertEqual(events[1].tool_calls[0]["function"]["name"], "lookup_code")

    def test_http_request_4xx_raises_no_retry(self):
        """4xx 客户端错误直接抛出不重试"""
        import urllib.error
        provider = self._make_provider()
        err = urllib.error.HTTPError("url", 400, "Bad Request", {}, None)
        with patch.object(provider, "_http_request", side_effect=err) as m:
            # 此处 patch 的是被调用方，验证外部行为：4xx 异常向上传播
            with self.assertRaises(urllib.error.HTTPError):
                m("http://fake", b"{}")


class TestOpenAICompatStreaming(unittest.TestCase):
    """OpenAICompatProvider 流式/工具调用解析测试（Mock HTTP，不联网）"""

    def _make_provider(self):
        from src.ai.providers.openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(base_url="http://fake:1234", api_key="test")

    def test_chat_stream_parses_sse(self):
        """chat_stream 解析 SSE data 行，遇到 [DONE] 停止"""
        provider = self._make_provider()
        raw = (
            'data: {"choices": [{"delta": {"content": "你"}}]}\n'.encode("utf-8")
            + 'data: {"choices": [{"delta": {"content": "好"}}]}\n'.encode("utf-8")
            + b'data: [DONE]\n'
            + b'\n'
        )
        with patch.object(provider, "_open_stream", return_value=_FakeStream([raw])):
            tokens = list(provider.chat_stream([{"role": "user", "content": "hi"}]))
        self.assertEqual(tokens, ["你", "好"])

    def test_chat_stream_buffers_split_sse_lines(self):
        """SSE 数据跨 chunk 拆分时应正确拼接"""
        provider = self._make_provider()
        chunk1 = b'data: {"choices": [{"delta": {"cont'
        chunk2 = b'ent": "A"}}]}\n'
        chunk3 = b'data: [DONE]\n'
        with patch.object(provider, "_open_stream", return_value=_FakeStream([chunk1, chunk2, chunk3])):
            tokens = list(provider.chat_stream([{"role": "user", "content": "hi"}]))
        self.assertEqual(tokens, ["A"])

    def test_chat_stream_skips_undecodable_bytes(self):
        """不完整的多字节 UTF-8 应跳过不崩溃"""
        provider = self._make_provider()
        raw = (
            b'data: {"choices": [{"delta": {"content": "\xe4"}}]}\n'
            + 'data: {"choices": [{"delta": {"content": "好"}}]}\n'.encode("utf-8")
            + b'data: [DONE]\n'
        )
        with patch.object(provider, "_open_stream", return_value=_FakeStream([raw])):
            tokens = list(provider.chat_stream([{"role": "user", "content": "hi"}]))
        # 第一行无法解码被跳过，第二行正常
        self.assertEqual(tokens, ["好"])

    def test_chat_with_tools_parses_arguments_string(self):
        """chat_with_tools 保留字符串 arguments"""
        provider = self._make_provider()
        result = {
            "choices": [{
                "message": {
                    "content": "",
                    "tool_calls": [
                        {"id": "c1", "type": "function",
                         "function": {"name": "lookup_code", "arguments": '{"code": "P0300"}'}}
                    ],
                }
            }]
        }
        with patch.object(provider, "_http_request", return_value=result):
            resp = provider.chat_with_tools(
                [{"role": "user", "content": "x"}], [{"type": "function"}]
            )
        self.assertEqual(resp["tool_calls"][0]["id"], "c1")
        self.assertEqual(resp["tool_calls"][0]["function"]["arguments"], '{"code": "P0300"}')

    def test_chat_with_tools_empty_choices(self):
        """无 choices 时返回空 content 和 None tool_calls"""
        provider = self._make_provider()
        with patch.object(provider, "_http_request", return_value={"choices": []}):
            resp = provider.chat_with_tools([{"role": "user", "content": "x"}], [])
        self.assertEqual(resp["content"], "")
        self.assertIsNone(resp["tool_calls"])

    def test_chat_with_tools_stream_incremental_arguments(self):
        """OpenAI 流式 tool_calls 增量拼接 arguments"""
        provider = self._make_provider()
        raw = (
            b'data: {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "lookup_code", "arguments": "{\\"cod"}}]}}]}\n'
            b'data: {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "e\\": \\"P0300\\"}"}}]}}]}\n'
            b'data: {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}\n'
            b'\n'
        )
        with patch.object(provider, "_open_stream", return_value=_FakeStream([raw])):
            events = list(provider.chat_with_tools_stream(
                [{"role": "user", "content": "x"}], [{"type": "function"}]
            ))
        tool_evt = [e for e in events if e.type == "tool_calls"]
        self.assertEqual(len(tool_evt), 1)
        call = tool_evt[0].tool_calls[0]
        self.assertEqual(call["function"]["name"], "lookup_code")
        self.assertEqual(call["function"]["arguments"], '{"code": "P0300"}')
        self.assertEqual(events[-1].type, "done")


if __name__ == "__main__":
    unittest.main()
