"""
LLMClient 代理层测试
用 mock provider 覆盖全部 wrapper 方法，不发起真实网络请求
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.ai.llm_client import LLMClient, create_provider
from src.ai.providers import StreamEvent


class _FakeProvider:
    """最小化 provider 假实现（用于属性分支测试）"""
    provider_name = "ollama"
    model_name = "fake:model"

    def is_available(self):
        return True

    def get_models(self):
        return ["fake:model"]

    def reset_availability(self):
        return None

    def generate(self, prompt, temperature=0.7, max_tokens=1024):
        return "fake 回复"


def _new_client(provider=None):
    """重置单例并用指定 provider 创建客户端"""
    LLMClient._instance = None
    return LLMClient(provider=provider)


class TestLLMClientWrapper(unittest.TestCase):
    """LLMClient wrapper 方法测试"""

    def setUp(self):
        LLMClient._instance = None
        self.provider = MagicMock()
        self.provider.provider_name = "ollama"
        self.provider.is_available.return_value = True
        self.client = _new_client(self.provider)

    def tearDown(self):
        LLMClient._instance = None

    # ── 诊断建议 ──

    def test_get_diagnostic_suggestion_ok(self):
        self.provider.generate.return_value = "建议内容"
        result = self.client.get_diagnostic_suggestion("P0300", {"description": "失火"})
        self.assertEqual(result, "建议内容")
        self.provider.generate.assert_called_once()

    def test_get_diagnostic_suggestion_not_available(self):
        self.provider.is_available.return_value = False
        result = self.client.get_diagnostic_suggestion("P0300")
        self.assertIn("未启动", result)

    def test_get_diagnostic_suggestion_error(self):
        self.provider.generate.side_effect = RuntimeError("boom")
        result = self.client.get_diagnostic_suggestion("P0300")
        self.assertIn("生成失败", result)
        self.assertIn("boom", result)

    def test_get_multi_code_analysis_ok(self):
        self.provider.generate.return_value = "综合分析"
        result = self.client.get_multi_code_analysis(["P0300"], [{"description": "失火"}])
        self.assertEqual(result, "综合分析")

    def test_get_multi_code_analysis_not_available(self):
        self.provider.is_available.return_value = False
        result = self.client.get_multi_code_analysis(["P0300"], [])
        self.assertIn("未启动", result)

    def test_get_multi_code_analysis_error(self):
        self.provider.generate.side_effect = RuntimeError("boom")
        result = self.client.get_multi_code_analysis(["P0300"], [])
        self.assertIn("生成失败", result)

    # ── 流式诊断建议 ──

    def test_get_diagnostic_suggestion_stream_ok(self):
        self.provider.generate_stream.return_value = iter(["a", "b"])
        chunks = list(self.client.get_diagnostic_suggestion_stream("P0300"))
        self.assertEqual(chunks, ["a", "b"])

    def test_get_diagnostic_suggestion_stream_not_available(self):
        self.provider.is_available.return_value = False
        chunks = list(self.client.get_diagnostic_suggestion_stream("P0300"))
        self.assertEqual(len(chunks), 1)
        self.assertIn("未启动", chunks[0])

    def test_get_diagnostic_suggestion_stream_error(self):
        self.provider.generate_stream.side_effect = RuntimeError("boom")
        chunks = list(self.client.get_diagnostic_suggestion_stream("P0300"))
        self.assertEqual(len(chunks), 1)
        self.assertIn("生成失败", chunks[0])

    # ── 对话 ──

    def test_chat_ok_with_system_inserted(self):
        self.provider.chat.return_value = "回复"
        result = self.client.chat("你好")
        self.assertEqual(result, "回复")
        messages = self.provider.chat.call_args[0][0]
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[-1]["content"], "你好")

    def test_chat_ok_keeps_existing_system(self):
        self.provider.chat.return_value = "回复"
        context = [{"role": "system", "content": "已有系统"}, {"role": "user", "content": "旧消息"}]
        self.client.chat("新消息", context=context)
        messages = self.provider.chat.call_args[0][0]
        # 已有 system → 不重复插入
        system_count = sum(1 for m in messages if m["role"] == "system")
        self.assertEqual(system_count, 1)
        self.assertEqual(messages[-1]["content"], "新消息")

    def test_chat_not_available(self):
        self.provider.is_available.return_value = False
        result = self.client.chat("你好")
        self.assertIn("未启动", result)

    def test_chat_error(self):
        self.provider.chat.side_effect = RuntimeError("boom")
        result = self.client.chat("你好")
        self.assertIn("生成失败", result)

    def test_chat_stream_ok(self):
        self.provider.chat_stream.return_value = iter(["x", "y"])
        chunks = list(self.client.chat_stream("你好"))
        self.assertEqual(chunks, ["x", "y"])

    def test_chat_stream_not_available(self):
        self.provider.is_available.return_value = False
        chunks = list(self.client.chat_stream("你好"))
        self.assertIn("未启动", chunks[0])

    def test_chat_stream_error(self):
        self.provider.chat_stream.side_effect = RuntimeError("boom")
        chunks = list(self.client.chat_stream("你好"))
        self.assertIn("生成失败", chunks[0])

    # ── 工具调用 ──

    def test_chat_with_tools_ok(self):
        self.provider.chat_with_tools.return_value = {"content": "结果", "tool_calls": None}
        result = self.client.chat_with_tools([{"role": "user", "content": "hi"}], [])
        self.assertEqual(result["content"], "结果")

    def test_chat_with_tools_not_available(self):
        self.provider.is_available.return_value = False
        result = self.client.chat_with_tools([], [])
        self.assertIn("未启动", result["content"])

    def test_chat_with_tools_error(self):
        self.provider.chat_with_tools.side_effect = RuntimeError("boom")
        result = self.client.chat_with_tools([], [])
        self.assertIn("调用失败", result["content"])

    def test_chat_with_tools_default_params(self):
        """temperature/max_tokens 未传时使用配置默认值"""
        self.provider.chat_with_tools.return_value = {"content": "ok", "tool_calls": None}
        self.client.chat_with_tools([], [])
        args = self.provider.chat_with_tools.call_args[0]
        self.assertGreaterEqual(len(args), 4)

    def test_chat_with_tools_stream_ok(self):
        events = [StreamEvent("content", content="a"), StreamEvent("done")]
        self.provider.chat_with_tools_stream.return_value = iter(events)
        got = list(self.client.chat_with_tools_stream([], []))
        self.assertEqual([e.type for e in got], ["content", "done"])

    def test_chat_with_tools_stream_not_available(self):
        self.provider.is_available.return_value = False
        got = list(self.client.chat_with_tools_stream([], []))
        self.assertEqual([e.type for e in got], ["content", "done"])
        self.assertIn("未启动", got[0].content)

    def test_chat_with_tools_stream_error(self):
        self.provider.chat_with_tools_stream.side_effect = RuntimeError("boom")
        got = list(self.client.chat_with_tools_stream([], []))
        self.assertEqual([e.type for e in got], ["content", "done"])
        self.assertIn("调用失败", got[0].content)

    # ── 状态查询 ──

    def test_is_available(self):
        self.provider.is_available.return_value = False
        self.assertFalse(self.client.is_available())

    def test_get_available_models(self):
        self.provider.get_models.return_value = ["m1", "m2"]
        self.assertEqual(self.client.get_available_models(), ["m1", "m2"])

    def test_reset_availability(self):
        self.client.reset_availability()
        self.provider.reset_availability.assert_called_once()

    def test_set_model(self):
        self.client.set_model("new:model")
        self.assertEqual(self.provider.model_name, "new:model")

    def test_model_name_property(self):
        self.provider.model_name = "current:model"
        self.assertEqual(self.client.model_name, "current:model")
        self.client.model_name = "changed:model"
        self.assertEqual(self.provider.model_name, "changed:model")

    def test_is_local(self):
        self.provider.provider_name = "ollama"
        self.assertTrue(self.client.is_local)
        self.provider.provider_name = "openai"
        self.assertFalse(self.client.is_local)

    def test_current_endpoint_name_ollama(self):
        self.provider.provider_name = "ollama"
        self.assertEqual(self.client.current_endpoint_name, "本地模型")

    def test_current_endpoint_name_remote(self):
        self.provider.provider_name = "openai"
        self.provider._endpoint_name = "DeepSeek"
        self.assertEqual(self.client.current_endpoint_name, "DeepSeek")

    def test_current_endpoint_name_remote_no_name(self):
        # 没有 _endpoint_name 属性的 provider → 返回默认"调用模型"
        self.client.set_provider(_FakeProvider())
        self.client._provider.provider_name = "openai"
        self.assertEqual(self.client.current_endpoint_name, "调用模型")

    # ── 切换 ──

    def test_set_provider(self):
        other = MagicMock()
        self.client.set_provider(other)
        self.assertIs(self.client.provider, other)

    def test_switch_to_local(self):
        self.client.switch_to_local()
        self.assertEqual(self.client.provider.provider_name, "ollama")

    def test_switch_provider(self):
        self.client.switch_provider("openai")
        self.assertEqual(self.client.provider.provider_name, "openai")
        self.client.switch_provider("ollama")
        self.assertEqual(self.client.provider.provider_name, "ollama")

    def test_switch_provider_with_name(self):
        self.client.switch_provider("openai", name="DeepSeek")
        self.assertEqual(self.client.provider._endpoint_name, "DeepSeek")

    def test_switch_to_remote_found(self):
        fake_eps = [{"name": "DeepSeek", "base_url": "http://x", "api_key": "k", "model_name": "m"}]
        with patch("src.ai.llm_client.get_remote_endpoints", return_value=fake_eps):
            ok = self.client.switch_to_remote("DeepSeek")
        self.assertTrue(ok)
        self.assertEqual(self.client.provider.provider_name, "openai")

    def test_switch_to_remote_not_found(self):
        with patch("src.ai.llm_client.get_remote_endpoints", return_value=[]):
            ok = self.client.switch_to_remote("不存在")
        self.assertFalse(ok)

    def test_get_remote_endpoints_passthrough(self):
        with patch("src.ai.llm_client.get_remote_endpoints", return_value=[{"name": "A"}]):
            self.assertEqual(self.client.get_remote_endpoints(), [{"name": "A"}])

    def test_factory_unknown_falls_back_to_ollama(self):
        p = create_provider("unknown")
        self.assertEqual(p.provider_name, "ollama")

    def test_create_llm_client_helper(self):
        from src.ai.llm_client import create_llm_client
        LLMClient._instance = None
        client = create_llm_client("ollama")
        self.assertEqual(client.provider.provider_name, "ollama")


if __name__ == "__main__":
    unittest.main()
