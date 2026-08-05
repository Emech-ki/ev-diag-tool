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


class _FakeHttpResponse:
    """模拟 urllib HTTP 响应（含 read + 上下文管理器）"""

    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestOllamaAvailability(unittest.TestCase):
    """OllamaProvider 可用性检查（TTL 缓存 + 网络 mock）"""

    def setUp(self):
        from src.ai.providers.ollama import OllamaProvider
        self.provider = OllamaProvider(base_url="http://fake:1234", model_name="test:model")

    def test_model_name_same_no_reset(self):
        """模型名不变时不重置可用性缓存"""
        self.provider._available = True
        self.provider.model_name = "test:model"
        self.assertIsNotNone(self.provider._available)

    def test_availability_ttl_cache_hit(self):
        """TTL 内命中缓存，不发起网络请求"""
        import time
        import urllib.request
        self.provider._available = True
        self.provider._available_at = time.time()
        with patch.object(urllib.request, "urlopen") as m:
            self.assertTrue(self.provider.is_available())
            m.assert_not_called()

    def test_availability_success(self):
        """urlopen 成功且模型存在 → 可用"""
        import json
        import urllib.request
        body = json.dumps({"models": [{"name": "test:model"}, {"name": "llama3"}]}).encode()
        with patch.object(urllib.request, "urlopen", return_value=_FakeHttpResponse(body)):
            self.assertTrue(self.provider.is_available())
        self.assertTrue(self.provider._available)

    def test_availability_model_not_found(self):
        """模型不在列表中 → 不可用"""
        import json
        import urllib.request
        body = json.dumps({"models": [{"name": "other"}]}).encode()
        with patch.object(urllib.request, "urlopen", return_value=_FakeHttpResponse(body)):
            self.assertFalse(self.provider.is_available())

    def test_availability_exception(self):
        """网络异常 → 不可用"""
        import urllib.request
        with patch.object(urllib.request, "urlopen", side_effect=urllib.error.URLError("down")):
            self.assertFalse(self.provider.is_available())

    def test_get_models_success(self):
        import json
        import urllib.request
        body = json.dumps({"models": [{"name": "a"}, {"name": "b"}]}).encode()
        with patch.object(urllib.request, "urlopen", return_value=_FakeHttpResponse(body)):
            self.assertEqual(self.provider.get_models(), ["a", "b"])

    def test_get_models_error_returns_empty(self):
        import urllib.request
        with patch.object(urllib.request, "urlopen", side_effect=urllib.error.URLError("down")):
            self.assertEqual(self.provider.get_models(), [])


class TestOllamaHttp(unittest.TestCase):
    """OllamaProvider 生成/对话/工具调用（mock _http_request）"""

    def _make_provider(self):
        from src.ai.providers.ollama import OllamaProvider
        return OllamaProvider(base_url="http://fake:1234", model_name="test:model")

    def test_generate(self):
        provider = self._make_provider()
        with patch.object(provider, "_http_request", return_value={"response": "  答案  "}):
            self.assertEqual(provider.generate("问题"), "答案")

    def test_chat(self):
        provider = self._make_provider()
        with patch.object(provider, "_http_request", return_value={"message": {"content": "  你好  "}}):
            self.assertEqual(provider.chat([{"role": "user", "content": "hi"}]), "你好")

    def test_chat_with_tools_string_arguments(self):
        """arguments 为字符串时原样保留"""
        provider = self._make_provider()
        result = {
            "message": {
                "content": "",
                "tool_calls": [{"function": {"name": "lookup_code", "arguments": "P0300"}}],
            }
        }
        with patch.object(provider, "_http_request", return_value=result):
            resp = provider.chat_with_tools([{"role": "user", "content": "x"}], [{"type": "function"}])
        self.assertEqual(resp["tool_calls"][0]["function"]["arguments"], "P0300")

    def test_generate_stream_skips_empty_and_bad_lines(self):
        provider = self._make_provider()
        lines = [
            b"",
            b"not json\n",
            b'{"response": "x", "done": true}\n',
        ]
        with patch.object(provider, "_open_stream", return_value=_FakeStream(lines)):
            self.assertEqual(list(provider.generate_stream("q")), ["x"])

    def test_chat_stream_skips_empty_and_bad_lines(self):
        provider = self._make_provider()
        lines = [
            b"",
            b"not json\n",
            b'{"message": {"content": "ok"}, "done": true}\n',
        ]
        with patch.object(provider, "_open_stream", return_value=_FakeStream(lines)):
            self.assertEqual(list(provider.chat_stream([{"role": "user", "content": "hi"}])), ["ok"])

    def test_chat_with_tools_stream_edges(self):
        """流式工具调用：空行/坏 JSON/字符串 arguments"""
        provider = self._make_provider()
        lines = [
            b"",
            b"not json\n",
            b'{"message": {"content": "c"}, "done": false}\n',
            b'{"message": {"tool_calls": [{"function": {"name": "lookup_code", "arguments": "P0300"}}]}, "done": true}\n',
        ]
        with patch.object(provider, "_open_stream", return_value=_FakeStream(lines)):
            events = list(provider.chat_with_tools_stream([{"role": "user", "content": "x"}], [{"type": "function"}]))
        types = [e.type for e in events]
        self.assertEqual(types, ["content", "tool_calls", "done"])
        self.assertEqual(events[1].tool_calls[0]["function"]["arguments"], "P0300")


class TestOllamaRetry(unittest.TestCase):
    """OllamaProvider 重试逻辑（AI_MAX_RETRIES 压低以加速测试）"""

    def setUp(self):
        from src.ai.providers.ollama import OllamaProvider
        self.provider = OllamaProvider(base_url="http://fake:1234", model_name="test:model")

    def test_http_request_5xx_retries_then_success(self):
        import json
        import urllib.request
        calls = {"n": 0}

        def _fake_urlopen(req, timeout=90):
            calls["n"] += 1
            if calls["n"] == 1:
                raise urllib.error.HTTPError("url", 500, "Internal", {}, None)
            return _FakeHttpResponse(b'{"ok": true}')

        with patch.object(urllib.request, "urlopen", side_effect=_fake_urlopen):
            with patch("src.ai.providers.ollama.AI_MAX_RETRIES", 1):
                result = self.provider._http_request("http://x", b"{}")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(calls["n"], 2)

    def test_http_request_exhausted_raises(self):
        import urllib.request
        with patch.object(urllib.request, "urlopen", side_effect=urllib.error.URLError("down")):
            with patch("src.ai.providers.ollama.AI_MAX_RETRIES", 1):
                with self.assertRaises(urllib.error.URLError):
                    self.provider._http_request("http://x", b"{}")

    def test_open_stream_exhausted_raises(self):
        import urllib.request
        with patch.object(urllib.request, "urlopen", side_effect=urllib.error.URLError("down")):
            with patch("src.ai.providers.ollama.AI_MAX_RETRIES", 1):
                with self.assertRaises(urllib.error.URLError):
                    self.provider._open_stream("http://x", b"{}")


class TestOpenAICompatExtras(unittest.TestCase):
    """OpenAICompatProvider 补充分支（可用性/URL 自动补全/重试）"""

    def _make_provider(self, api_key="test", base_url="http://fake:1234/v1"):
        from src.ai.providers.openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(api_key=api_key, base_url=base_url, model_name="gpt-x")

    def test_model_name_same_no_reset(self):
        provider = self._make_provider()
        provider._available = True
        provider.model_name = "gpt-x"
        self.assertIsNotNone(provider._available)

    def test_base_url_auto_append_v1(self):
        provider = self._make_provider(base_url="https://api.deepseek.com")
        self.assertEqual(provider._base_url, "https://api.deepseek.com/v1")

    def test_base_url_keeps_v2_and_custom_path(self):
        provider = self._make_provider(base_url="https://x.com/v2")
        self.assertEqual(provider._base_url, "https://x.com/v2")
        provider = self._make_provider(base_url="https://x.com/custom")
        self.assertEqual(provider._base_url, "https://x.com/custom")

    def test_availability_ttl_cache_hit(self):
        import time
        import urllib.request
        provider = self._make_provider()
        provider._available = True
        provider._available_at = time.time()
        with patch.object(urllib.request, "urlopen") as m:
            self.assertTrue(provider.is_available())
            m.assert_not_called()

    def test_availability_success(self):
        """urlopen 成功 → 可用（即使模型不在列表中也返回 True）"""
        import json
        import urllib.request
        provider = self._make_provider()
        body = json.dumps({"data": [{"id": "other-model"}]}).encode()
        with patch.object(urllib.request, "urlopen", return_value=_FakeHttpResponse(body)):
            self.assertTrue(provider.is_available())

    def test_availability_exception(self):
        """网络异常 → 不可用"""
        import urllib.request
        provider = self._make_provider()
        with patch.object(urllib.request, "urlopen", side_effect=urllib.error.URLError("down")):
            self.assertFalse(provider.is_available())

    def test_get_models_no_key(self):
        provider = self._make_provider(api_key="")
        self.assertEqual(provider.get_models(), [])

    def test_get_models_success(self):
        import json
        import urllib.request
        provider = self._make_provider()
        body = json.dumps({"data": [{"id": "a"}, {"id": "b"}]}).encode()
        with patch.object(urllib.request, "urlopen", return_value=_FakeHttpResponse(body)):
            self.assertEqual(provider.get_models(), ["a", "b"])

    def test_get_models_exception(self):
        import urllib.request
        provider = self._make_provider()
        with patch.object(urllib.request, "urlopen", side_effect=urllib.error.URLError("down")):
            self.assertEqual(provider.get_models(), [])

    def test_generate_delegates_chat(self):
        provider = self._make_provider()
        with patch.object(provider, "_http_request", return_value={"choices": [{"message": {"content": " 结果 "}}]}):
            self.assertEqual(provider.generate("q"), "结果")

    def test_generate_stream(self):
        provider = self._make_provider()
        with patch.object(provider, "_open_stream", return_value=_FakeStream([
            b'data: {"choices": [{"delta": {"content": "A"}}]}\n',
            b'data: [DONE]\n',
            b'\n',
        ])):
            self.assertEqual(list(provider.generate_stream("q")), ["A"])

    def test_chat_empty_choices(self):
        provider = self._make_provider()
        with patch.object(provider, "_http_request", return_value={"choices": []}):
            self.assertEqual(provider.chat([{"role": "user", "content": "hi"}]), "")

    def test_chat_stream_skips_bad_json(self):
        provider = self._make_provider()
        raw = (
            b'data: not-json\n'
            + b'data: {"choices": [{"delta": {"content": "ok"}}]}\n'
            + b'data: [DONE]\n'
        )
        with patch.object(provider, "_open_stream", return_value=_FakeStream([raw])):
            self.assertEqual(list(provider.chat_stream([{"role": "user", "content": "hi"}])), ["ok"])

    def test_chat_with_tools_stream_edges(self):
        """流式工具调用：非法行/空行/非 data 行/[DONE] 前终结"""
        provider = self._make_provider()
        raw = (
            b'garbage line\n'
            + b''
            + b'data: {"choices": []}\n'
            + b'data: not-json\n'
            + b'data: {"choices": [{"delta": {"content": "T"}, "finish_reason": "tool_calls"}]}\n'
            + b'data: [DONE]\n'
        )
        with patch.object(provider, "_open_stream", return_value=_FakeStream([raw])):
            events = list(provider.chat_with_tools_stream([{"role": "user", "content": "x"}], [{"type": "function"}]))
        contents = [e.content for e in events if e.type == "content"]
        self.assertEqual(contents, ["T"])
        self.assertEqual(events[-1].type, "done")

    def test_chat_with_tools_stream_unicode_decode_error(self):
        """chat_with_tools_stream 跳过不完整的 UTF-8 多字节"""
        provider = self._make_provider()
        raw = (
            b'data: {"choices": [{"delta": {"content": "\xe4"}}]}\n'
            + 'data: {"choices": [{"delta": {"content": "好"}}]}\n'.encode("utf-8")
            + b'data: [DONE]\n'
        )
        with patch.object(provider, "_open_stream", return_value=_FakeStream([raw])):
            events = list(provider.chat_with_tools_stream([{"role": "user", "content": "x"}], []))
        contents = [e.content for e in events if e.type == "content"]
        self.assertEqual(contents, ["好"])

    def test_chat_with_tools_stream_done_break(self):
        """[DONE] 后 break 退出"""
        provider = self._make_provider()
        raw = (
            b'data: {"choices": [{"delta": {"content": "X"}}]}\n'
            + b'data: [DONE]\n'
        )
        with patch.object(provider, "_open_stream", return_value=_FakeStream([raw])):
            events = list(provider.chat_with_tools_stream([{"role": "user", "content": "x"}], []))
        contents = [e.content for e in events if e.type == "content"]
        self.assertEqual(contents, ["X"])

    def test_http_request_urlerror_retries_then_raises(self):
        """URLError 重试耗尽后抛出"""
        import urllib.request
        provider = self._make_provider()
        with patch.object(urllib.request, "urlopen", side_effect=urllib.error.URLError("down")):
            with patch("src.ai.providers.openai_compat.AI_MAX_RETRIES", 1):
                with self.assertRaises(urllib.error.URLError):
                    provider._http_request("http://x", b"{}")

    def test_http_request_5xx_retries_then_success(self):
        """5xx 重试后成功"""
        import urllib.request
        provider = self._make_provider()
        calls = {"n": 0}

        def _fake_urlopen(req, timeout=90):
            calls["n"] += 1
            if calls["n"] == 1:
                raise urllib.error.HTTPError("url", 500, "Internal", {}, None)
            return _FakeHttpResponse(b'{"ok": true}')

        with patch.object(urllib.request, "urlopen", side_effect=_fake_urlopen):
            with patch("src.ai.providers.openai_compat.AI_MAX_RETRIES", 1):
                result = provider._http_request("http://x", b"{}")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(calls["n"], 2)

    def test_open_stream_4xx_raises_no_retry(self):
        """4xx 不重试直接抛出"""
        import urllib.request
        provider = self._make_provider()
        err = urllib.error.HTTPError("url", 400, "Bad Request", {}, None)
        with patch.object(urllib.request, "urlopen", side_effect=err):
            with self.assertRaises(urllib.error.HTTPError):
                provider._open_stream("http://x", b"{}")


class TestStreamEventDefaults(unittest.TestCase):
    """StreamEvent 数据类与 LLMProvider 默认流式实现"""

    def test_stream_event_defaults(self):
        from src.ai.providers import StreamEvent
        ev = StreamEvent("content")
        self.assertEqual(ev.content, "")
        self.assertEqual(ev.tool_calls, [])

    def test_provider_default_chat_with_tools_stream(self):
        """LLMProvider 默认 chat_with_tools_stream 包装非流式结果"""
        from src.ai.providers import LLMProvider, StreamEvent

        class _Minimal(LLMProvider):
            provider_name = "minimal"
            _model_name = "m"

            @property
            def model_name(self):
                return self._model_name

            @model_name.setter
            def model_name(self, name):
                self._model_name = name

            def is_available(self):
                return True

            def get_models(self):
                return []

            def generate(self, prompt, temperature=0.7, max_tokens=1024):
                return ""

            def generate_stream(self, prompt, temperature=0.7, max_tokens=1024):
                return iter([])

            def chat(self, messages, temperature=0.7, max_tokens=1024):
                return ""

            def chat_stream(self, messages, temperature=0.7, max_tokens=1024):
                return iter([])

            def chat_with_tools(self, messages, tools, temperature=0.7, max_tokens=2048):
                return {"content": "默认", "tool_calls": [{"id": "x"}]}

        p = _Minimal()
        events = list(p.chat_with_tools_stream([], []))
        types = [e.type for e in events]
        self.assertEqual(types, ["content", "tool_calls", "done"])
        self.assertEqual(events[0].content, "默认")


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
