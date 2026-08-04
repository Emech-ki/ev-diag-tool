"""
AI 客户端测试
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.config import (
    OLLAMA_BASE_URL, OLLAMA_MODEL_NAME, AI_PROVIDER,
    AI_TEMPERATURE, AI_MAX_TOKENS
)


class TestLLMClientConfig(unittest.TestCase):
    """LLMClient 配置测试"""

    def test_config_loading(self):
        """测试配置加载"""
        self.assertIsInstance(OLLAMA_BASE_URL, str)
        self.assertIn("http", OLLAMA_BASE_URL)
        self.assertIsInstance(OLLAMA_MODEL_NAME, str)
        self.assertGreater(len(OLLAMA_MODEL_NAME), 0)

    def test_ai_provider_config(self):
        """测试 AI Provider 配置"""
        self.assertIn(AI_PROVIDER, ("ollama", "openai"))

    def test_ai_generation_params(self):
        """测试 AI 生成参数配置"""
        self.assertIsInstance(AI_TEMPERATURE, float)
        self.assertGreaterEqual(AI_TEMPERATURE, 0)
        self.assertLessEqual(AI_TEMPERATURE, 2)
        self.assertIsInstance(AI_MAX_TOKENS, int)
        self.assertGreater(AI_MAX_TOKENS, 0)

    def test_llm_client_init(self):
        """测试 LLM 客户端初始化"""
        from src.ai.llm_client import LLMClient

        LLMClient._instance = None
        client = LLMClient()
        self.assertIsNotNone(client.provider)
        self.assertEqual(client.provider.provider_name, AI_PROVIDER)

    def test_set_model(self):
        """测试模型切换"""
        from src.ai.llm_client import LLMClient

        LLMClient._instance = None
        client = LLMClient()
        original_model = client.model_name

        client.set_model("new:model")
        self.assertEqual(client.model_name, "new:model")

        client.set_model(original_model)

    def test_switch_provider(self):
        """测试 Provider 切换"""
        from src.ai.llm_client import LLMClient

        LLMClient._instance = None
        client = LLMClient()

        # 切换到 openai
        client.switch_provider("openai")
        self.assertEqual(client.provider.provider_name, "openai")

        # 切换回 ollama
        client.switch_provider("ollama")
        self.assertEqual(client.provider.provider_name, "ollama")

    def test_create_provider_factory(self):
        """测试 Provider 工厂函数"""
        from unittest.mock import patch
        from src.ai.llm_client import create_provider

        ollama = create_provider("ollama")
        self.assertEqual(ollama.provider_name, "ollama")

        openai = create_provider("openai")
        self.assertEqual(openai.provider_name, "openai")

        # 默认返回 ollama（mock 模块级变量确保测试隔离）
        with patch("src.ai.llm_client.AI_PROVIDER", "ollama"):
            default = create_provider()
            self.assertEqual(default.provider_name, "ollama")


class TestPromptTemplates(unittest.TestCase):
    """提示词模板测试"""

    def test_prompt_with_knowledge(self):
        """测试带知识库信息的 prompt"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        prompt = templates.build_diagnostic_prompt(
            code="P0300",
            knowledge={
                "description": "随机/多缸失火",
                "detail": "ECU检测到多个气缸失火",
                "severity": "high",
                "common_causes": ["火花塞故障", "点火线圈故障"],
                "diagnostic_steps": ["读取冻结帧", "检查火花塞"]
            },
            vehicle_info="比亚迪秦PLUS EV",
            additional_info="冷车启动抖动"
        )
        self.assertIn("P0300", prompt)
        self.assertIn("比亚迪秦PLUS EV", prompt)
        self.assertIn("冷车启动抖动", prompt)
        self.assertIn("火花塞故障", prompt)

    def test_prompt_without_knowledge(self):
        """测试无知识库信息的 prompt"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        prompt = templates.build_diagnostic_prompt(
            code="P9999",
            knowledge=None,
            vehicle_info=""
        )
        self.assertIn("P9999", prompt)

    def test_prompt_cot_reasoning(self):
        """测试 CoT 推理引导"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        prompt = templates.build_diagnostic_prompt(
            code="P0300",
            knowledge={"description": "测试", "detail": "", "severity": "medium",
                       "common_causes": [], "diagnostic_steps": []}
        )
        # 应包含 CoT 推理引导
        self.assertIn("Chain of Thought", prompt)
        self.assertIn("逐步推理", prompt)
        self.assertIn("置信度百分比", prompt)

    def test_prompt_severity_critical(self):
        """测试高危故障码的 prompt 增强安全提醒"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        prompt = templates.build_diagnostic_prompt(
            code="P0A0E",
            knowledge={"description": "绝缘故障", "detail": "", "severity": "critical",
                       "common_causes": [], "diagnostic_steps": []}
        )
        self.assertIn("安全警告", prompt)
        self.assertIn("高压维修开关", prompt)
        self.assertIn("绝缘手套", prompt)

    def test_prompt_severity_low(self):
        """测试低危故障码的 prompt 无额外安全警告"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        prompt = templates.build_diagnostic_prompt(
            code="P0300",
            knowledge={"description": "测试", "detail": "", "severity": "low",
                       "common_causes": [], "diagnostic_steps": []}
        )
        # 不应有高危安全警告
        self.assertNotIn("安全警告（高危故障）", prompt)

    def test_prompt_few_shot(self):
        """测试 few-shot 示例"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        prompt = templates.build_diagnostic_prompt(
            code="P0300",
            knowledge={"description": "测试", "detail": "", "severity": "medium",
                       "common_causes": [], "diagnostic_steps": []}
        )
        self.assertIn("参考示例", prompt)
        self.assertIn("P0300", prompt)

    def test_agent_system_prompt(self):
        """测试 Agent 系统提示词"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        prompt = templates.get_agent_system_prompt()
        self.assertIn("新能源汽车", prompt)
        self.assertIn("高压系统", prompt)
        self.assertIn("绝缘手套", prompt)
        self.assertIn("逐步推理", prompt)


class TestAgent(unittest.TestCase):
    """DiagnosticAgent 测试"""

    def test_agent_init(self):
        """测试 Agent 初始化"""
        from src.ai.agent import DiagnosticAgent

        agent = DiagnosticAgent(kb=None, llm=None)
        self.assertIsNone(agent.session_code)
        self.assertIsNone(agent.session_vehicle)
        self.assertEqual(len(agent._history), 0)

    def test_agent_start_diagnosis(self):
        """测试开始诊断"""
        from src.ai.agent import DiagnosticAgent

        agent = DiagnosticAgent(kb=None, llm=None)
        result = agent.start_diagnosis("P0300")
        self.assertEqual(result["code"], "P0300")
        self.assertEqual(agent.session_code, "P0300")

    def test_agent_reset_session(self):
        """测试重置会话"""
        from src.ai.agent import DiagnosticAgent

        agent = DiagnosticAgent(kb=None, llm=None)
        agent.start_diagnosis("P0300")
        agent.reset_session()
        self.assertIsNone(agent.session_code)
        self.assertIsNone(agent.session_vehicle)

    def test_agent_get_session_summary(self):
        """测试获取会话摘要"""
        from src.ai.agent import DiagnosticAgent

        agent = DiagnosticAgent(kb=None, llm=None)
        summary = agent.get_session_summary()
        self.assertEqual(summary["status"], "no_active_session")

        agent.start_diagnosis("P0300")
        summary = agent.get_session_summary()
        self.assertEqual(summary["code"], "P0300")

    def test_agent_has_tools(self):
        """测试 Agent 初始化后有工具注册"""
        from src.ai.agent import DiagnosticAgent

        agent = DiagnosticAgent(kb=None, llm=None)
        tools = agent.tools.list_tools()
        self.assertIn("lookup_code", tools)
        self.assertIn("search_by_symptom", tools)
        self.assertIn("get_vehicle_info", tools)
        self.assertGreaterEqual(len(tools), 9)


class TestToolRegistry(unittest.TestCase):
    """工具注册表测试"""

    def test_register_and_find(self):
        """测试注册和查找工具"""
        from src.ai.tools import Tool, ToolParam, ToolRegistry

        registry = ToolRegistry()
        tool = Tool(
            name="test_tool",
            description="测试工具",
            parameters=[ToolParam(name="code", type="string", description="故障码")],
            function=lambda code: f'{{"result": "{code}"}}',
        )
        registry.register(tool)

        self.assertIn("test_tool", registry)
        self.assertEqual(len(registry), 1)
        self.assertIs(registry.get("test_tool"), tool)
        self.assertIsNone(registry.get("nonexistent"))

    def test_to_openai_schema(self):
        """测试导出 OpenAI function calling 格式"""
        from src.ai.tools import Tool, ToolParam

        tool = Tool(
            name="lookup_code",
            description="查询故障码详情",
            parameters=[
                ToolParam(name="code", type="string", description="故障码如P0300", required=True),
                ToolParam(name="verbose", type="boolean", description="是否详细", required=False),
            ],
            function=lambda code, verbose=False: "{}",
        )
        schema = tool.to_openai_schema()

        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "lookup_code")
        self.assertIn("查询故障码", schema["function"]["description"])
        self.assertIn("code", schema["function"]["parameters"]["properties"])
        self.assertIn("code", schema["function"]["parameters"]["required"])
        self.assertNotIn("verbose", schema["function"]["parameters"]["required"])

    def test_execute_success(self):
        """测试工具执行成功"""
        from src.ai.tools import Tool, ToolParam, ToolRegistry
        import json

        registry = ToolRegistry()
        registry.register(Tool(
            name="echo",
            description="回显",
            parameters=[ToolParam(name="text", type="string", description="输入")],
            function=lambda text: json.dumps({"echo": text}),
        ))

        result = registry.execute("echo", {"text": "hello"})
        parsed = json.loads(result)
        self.assertEqual(parsed["echo"], "hello")

    def test_execute_unknown_tool(self):
        """测试执行未知工具"""
        from src.ai.tools import ToolRegistry
        import json

        registry = ToolRegistry()
        result = registry.execute("nonexistent", {})
        parsed = json.loads(result)
        self.assertIn("error", parsed)

    def test_execute_tool_error(self):
        """测试工具执行出错"""
        from src.ai.tools import Tool, ToolParam, ToolRegistry
        import json

        registry = ToolRegistry()
        registry.register(Tool(
            name="fail",
            description="会失败的工具",
            parameters=[],
            function=lambda: 1 / 0,  # 除零错误
        ))

        result = registry.execute("fail", {})
        parsed = json.loads(result)
        self.assertIn("error", parsed)

    def test_to_openai_format_multiple(self):
        """测试多个工具导出"""
        from src.ai.tools import Tool, ToolParam, ToolRegistry

        registry = ToolRegistry()
        for i in range(3):
            registry.register(Tool(
                name=f"tool_{i}",
                description=f"工具{i}",
                parameters=[],
                function=lambda: "{}",
            ))

        format_list = registry.to_openai_format()
        self.assertEqual(len(format_list), 3)
        for item in format_list:
            self.assertEqual(item["type"], "function")


class TestDiagnosticTools(unittest.TestCase):
    """诊断工具集测试"""

    def test_all_tools_registered(self):
        """测试所有 9 个工具都能注册"""
        from src.ai.tools import ToolRegistry
        from src.ai.diagnostic_tools import register_diagnostic_tools

        registry = ToolRegistry()
        register_diagnostic_tools(registry)

        expected = [
            "lookup_code", "search_by_symptom", "get_vehicle_info",
            "get_related_codes", "get_diagnostic_steps", "get_wiring_info",
            "record_symptom", "get_common_fixes", "search_codes_by_system",
        ]
        for name in expected:
            self.assertIn(name, registry, f"工具 {name} 未注册")
        self.assertEqual(len(registry), 10)

    def test_tool_schemas_valid(self):
        """测试所有工具的 schema 格式正确"""
        from src.ai.tools import ToolRegistry
        from src.ai.diagnostic_tools import register_diagnostic_tools
        import json

        registry = ToolRegistry()
        register_diagnostic_tools(registry)

        for tool in registry.to_openai_format():
            self.assertEqual(tool["type"], "function")
            func = tool["function"]
            self.assertIn("name", func)
            self.assertIn("description", func)
            self.assertIn("parameters", func)
            self.assertEqual(func["parameters"]["type"], "object")
            self.assertIn("properties", func["parameters"])


class TestAgentReAct(unittest.TestCase):
    """DiagnosticAgent.run() 主循环测试（Mock LLM，不发起真实网络请求）"""

    @staticmethod
    def _make_mock_llm(responses, is_local=False):
        """构造一个按顺序返回 chat_with_tools 响应的 Mock LLM"""
        llm = MagicMock()
        llm.is_local = is_local
        llm.chat_with_tools.side_effect = responses
        llm.chat.return_value = "mock 总结回答"
        return llm

    def test_direct_answer_no_tools(self):
        """LLM 直接给出文本回答 → run() 返回该回答"""
        from src.ai.agent import DiagnosticAgent

        llm = self._make_mock_llm([{"content": "直接回答", "tool_calls": None}])
        agent = DiagnosticAgent(kb=None, llm=llm)
        result = agent.run("P0300 是什么")
        self.assertEqual(result, "直接回答")
        self.assertEqual(len(agent._history), 2)

    def test_react_loop_tool_then_answer(self):
        """ReAct：第一轮调用工具，第二轮给出最终回答"""
        from src.ai.agent import DiagnosticAgent

        first = {
            "content": "让我查询",
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "lookup_code", "arguments": '{"code": "P0300"}'},
            }],
        }
        second = {"content": "P0300 是失火", "tool_calls": None}
        llm = self._make_mock_llm([first, second])
        agent = DiagnosticAgent(kb=None, llm=llm)

        calls = []
        results = []
        result = agent.run(
            "查 P0300",
            on_tool_call=lambda n, a: calls.append((n, a)),
            on_tool_result=lambda n, r: results.append((n, r)),
        )

        self.assertEqual(result, "P0300 是失火")
        self.assertEqual(calls, [("lookup_code", {"code": "P0300"})])
        self.assertEqual(len(results), 1)
        # 历史应包含 user + assistant
        self.assertEqual([h["role"] for h in agent._history], ["user", "assistant"])
        # chat_with_tools 应被调用两次（首轮测试 + 下一轮）
        self.assertEqual(llm.chat_with_tools.call_count, 2)

    def test_react_loop_ollama_strips_tool_calls(self):
        """Ollama（is_local=True）时，assistant 消息不应携带 tool_calls 字段"""
        from src.ai.agent import DiagnosticAgent

        first = {
            "content": "查一下",
            "tool_calls": [{
                "id": "c1", "type": "function",
                "function": {"name": "lookup_code", "arguments": '{"code": "P0300"}'},
            }],
        }
        second = {"content": "结论", "tool_calls": None}
        llm = self._make_mock_llm([first, second], is_local=True)
        agent = DiagnosticAgent(kb=None, llm=llm)

        agent.run("查 P0300")

        # 第二次调用（下一轮）的消息历史中，assistant 消息不能有 tool_calls
        args = llm.chat_with_tools.call_args_list[1]
        messages = args[0][0]
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        self.assertTrue(assistant_msgs, "应存在 assistant 消息")
        self.assertNotIn("tool_calls", assistant_msgs[-1])

    def test_react_loop_openai_keeps_tool_calls(self):
        """OpenAI（is_local=False）时，assistant 消息必须携带 tool_calls 字段"""
        from src.ai.agent import DiagnosticAgent

        first = {
            "content": "查一下",
            "tool_calls": [{
                "id": "c1", "type": "function",
                "function": {"name": "lookup_code", "arguments": '{"code": "P0300"}'},
            }],
        }
        second = {"content": "结论", "tool_calls": None}
        llm = self._make_mock_llm([first, second], is_local=False)
        agent = DiagnosticAgent(kb=None, llm=llm)

        agent.run("查 P0300")

        args = llm.chat_with_tools.call_args_list[1]
        messages = args[0][0]
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        self.assertTrue(assistant_msgs, "应存在 assistant 消息")
        self.assertIn("tool_calls", assistant_msgs[-1])

    def test_react_loop_dedup_tools(self):
        """相同工具+参数不应重复调用（去重后强制总结）"""
        from src.ai.agent import DiagnosticAgent

        tool_call = {
            "id": "c1", "type": "function",
            "function": {"name": "lookup_code", "arguments": '{"code": "P0300"}'},
        }
        first = {"content": "查一下", "tool_calls": [tool_call]}
        second = {"content": "再查一次", "tool_calls": [tool_call]}  # 重复调用
        llm = self._make_mock_llm([first, second])
        agent = DiagnosticAgent(kb=None, llm=llm)

        # 第二轮重复 → any_new_call=False → 走 chat 总结
        result = agent.run("查 P0300")
        self.assertEqual(result, "mock 总结回答")
        self.assertGreaterEqual(llm.chat.call_count, 1)

    def test_react_loop_max_rounds_summary(self):
        """循环次数用尽后走 chat 总结"""
        from src.ai.agent import DiagnosticAgent

        tool_call = {
            "id": "c1", "type": "function",
            "function": {"name": "lookup_code", "arguments": '{"code": "P0300"}'},
        }
        responses = []
        for i in range(12):  # 超过 MAX_TOOL_ROUNDS=10
            responses.append({"content": f"查询{i}", "tool_calls": [tool_call]})
        llm = self._make_mock_llm(responses)
        agent = DiagnosticAgent(kb=None, llm=llm)

        result = agent.run("查 P0300")
        self.assertEqual(result, "mock 总结回答")

    def test_tool_calling_fails_falls_back_to_prefetch(self):
        """chat_with_tools 抛异常 → 降级到 _run_with_prefetch"""
        from src.ai.agent import DiagnosticAgent

        llm = MagicMock()
        llm.is_local = False
        llm.chat_with_tools.side_effect = RuntimeError("tool calling not supported")
        llm.chat.return_value = "降级回答"
        agent = DiagnosticAgent(kb=None, llm=llm)

        result = agent.run("查 P0300 是什么问题")
        self.assertEqual(result, "降级回答")
        llm.chat.assert_called_once()


if __name__ == "__main__":
    unittest.main()
