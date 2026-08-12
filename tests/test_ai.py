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

    def test_tool_agent_system_prompt(self):
        """测试工具感知的 Agent 系统提示词"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        prompt = templates.get_tool_agent_system_prompt()
        self.assertIn("lookup_code", prompt)
        self.assertIn("反幻觉铁律", prompt)
        self.assertIn("工具说没有 = 没有", prompt)

    def test_expert_system_prompt(self):
        """测试专家角色系统提示词"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        battery = templates.get_expert_system_prompt("battery")
        self.assertIn("电池系统", battery)
        motor = templates.get_expert_system_prompt("motor")
        self.assertIn("电机驱动系统", motor)
        vcu = templates.get_expert_system_prompt("vcu")
        self.assertIn("电控系统", vcu)
        # 未知专家回退到通用（无角色声明）
        unknown = templates.get_expert_system_prompt("unknown")
        general = templates.get_expert_system_prompt("general")
        self.assertEqual(unknown, general)

    def test_prompt_non_list_causes_fallback(self):
        """测试 common_causes/steps 非列表时的容错分支"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        prompt = templates.build_diagnostic_prompt(
            code="P0300",
            knowledge={
                "description": "测试", "detail": "",
                "severity": "medium",
                "common_causes": "不是列表",   # 触发 else 分支
                "diagnostic_steps": "也不是列表",  # 触发 else 分支
            }
        )
        self.assertIn("信息获取失败", prompt)

    def test_prompt_no_knowledge_no_extra(self):
        """测试无知识库、无车型、无描述的最小 prompt"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        prompt = templates.build_diagnostic_prompt(code="P0A0E", knowledge=None)
        # 无知识库时不应有安全警告（非高危路径）
        self.assertIn("P0A0E", prompt)
        self.assertNotIn("安全警告（高危故障）", prompt)
        self.assertIn("安全提醒", prompt)

    # ── 多故障码 prompt 测试 ──

    def test_multi_prompt_basic(self):
        """测试多故障码 prompt 基本内容"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        prompt = templates.build_multi_diagnostic_prompt(
            codes=["P0300", "P0171"],
            results=[
                {"description": "失火", "severity": "high", "system": "P",
                 "common_causes": ["火花塞"]},
                {"description": "混合气过稀", "severity": "medium", "system": "P",
                 "common_causes": ["真空泄漏"]},
            ],
            correlation_summary="两者都与燃油供给相关",
            vehicle_info="比亚迪秦PLUS EV",
            additional_info="冷车抖动",
        )
        self.assertIn("P0300", prompt)
        self.assertIn("P0171", prompt)
        self.assertIn("两者都与燃油供给相关", prompt)
        self.assertIn("比亚迪秦PLUS EV", prompt)
        self.assertIn("冷车抖动", prompt)
        self.assertIn("关联性判断", prompt)
        self.assertIn("火花塞", prompt)
        # 有症状上下文 → 对症下药：含「已报告的症状」与候选码排序指令
        self.assertIn("已报告的症状", prompt)
        self.assertIn("对症下药", prompt)
        self.assertIn("候选码可能性排序", prompt)
        # high 级别 → 包含安全警告
        self.assertIn("安全警告", prompt)

    def test_multi_prompt_without_symptom(self):
        """无症状上下文时不出现对症下药排序段"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        prompt = templates.build_multi_diagnostic_prompt(
            codes=["P0300"],
            results=[{"description": "失火", "severity": "medium", "system": "P"}],
            correlation_summary="",
        )
        self.assertNotIn("候选码可能性排序", prompt)
        self.assertIn("故障码关联性判断", prompt)

    def test_multi_prompt_priority_codes(self):
        """高疑似候选码 → prompt 含「高疑似候选码」提示段，无症状时也可用；带 weight 时渲染置信度"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        prompt = templates.build_multi_diagnostic_prompt(
            codes=["EV-BMS-006", "EV-BMS-015", "EV-BMS-041"],
            results=[{"description": "x", "severity": "medium", "system": "BMS"}],
            correlation_summary="",
            priority_codes=["EV-BMS-006", "EV-BMS-015"],
            priority_weights={"EV-BMS-006": 95, "EV-BMS-015": 85},
        )
        self.assertIn("高疑似候选码", prompt)
        self.assertIn("EV-BMS-006", prompt)
        self.assertIn("显式置信度从高到低", prompt)
        self.assertIn("置信度 95%", prompt)
        self.assertIn("置信度 85%", prompt)

    def test_multi_prompt_priority_without_weights(self):
        """高疑似候选码未带 weight 时仅列码，不渲染置信度"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        prompt = templates.build_multi_diagnostic_prompt(
            codes=["EV-BMS-006", "EV-BMS-015"],
            results=[{"description": "x", "severity": "medium", "system": "BMS"}],
            correlation_summary="",
            priority_codes=["EV-BMS-006", "EV-BMS-015"],
        )
        self.assertIn("高疑似候选码", prompt)
        self.assertIn("EV-BMS-006", prompt)
        self.assertNotIn("置信度 95%", prompt)
        self.assertNotIn("置信度 85%", prompt)

    def test_multi_prompt_without_priority(self):
        """未指定高疑似候选码时不出现提示段"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        prompt = templates.build_multi_diagnostic_prompt(
            codes=["P0300"],
            results=[{"description": "失火", "severity": "medium", "system": "P"}],
            correlation_summary="",
        )
        self.assertNotIn("高疑似候选码", prompt)

    def test_multi_prompt_critical_severity(self):
        """测试多码中存在 critical 时取最高严重度"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        prompt = templates.build_multi_diagnostic_prompt(
            codes=["P0A00", "P0300"],
            results=[
                {"description": "电池电压异常", "severity": "critical", "system": "P",
                 "common_causes": ["电池不一致"]},
                {"description": "失火", "severity": "low", "system": "P", "common_causes": []},
            ],
            correlation_summary="",
        )
        self.assertIn("「严重」级别故障", prompt)

    def test_multi_prompt_no_knowledge(self):
        """测试多码中无知识库数据（results 为空字典）"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        prompt = templates.build_multi_diagnostic_prompt(
            codes=["P9999"],
            results=[None],
            correlation_summary="无",
        )
        self.assertIn("P9999", prompt)
        self.assertIn("无", prompt)
        # 非高危 → 普通安全提醒
        self.assertNotIn("安全警告\n", prompt)
        self.assertIn("请提醒技师注意高压安全", prompt)

    def test_multi_prompt_unknown_severity(self):
        """测试多码严重度为未知值时使用默认中等"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()
        prompt = templates.build_multi_diagnostic_prompt(
            codes=["P0000"],
            results=[{"description": "未知", "severity": "weird", "system": "P"}],
            correlation_summary="",
        )
        # 未知严重度按中等处理 → 走普通安全提醒，不含高危警告
        self.assertNotIn("「严重」级别故障", prompt)
        self.assertIn("请提醒技师注意高压安全", prompt)


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


class TestAgentStream(unittest.TestCase):
    """Agent run_stream 流式路径测试"""

    @staticmethod
    def _make_stream_llm(side_effects, is_local=False):
        llm = MagicMock()
        llm.is_local = is_local
        llm.chat_with_tools_stream.side_effect = side_effects
        llm.chat.return_value = "流式降级回答"
        return llm

    def test_run_stream_direct_answer(self):
        """无 tool_calls → 直接流式回答"""
        from src.ai.agent import DiagnosticAgent
        from src.ai.providers import StreamEvent

        llm = self._make_stream_llm([iter([
            StreamEvent("content", content="直接"),
            StreamEvent("content", content="回答"),
            StreamEvent("done"),
        ])])
        agent = DiagnosticAgent(kb=None, llm=llm)

        events = list(agent.run_stream("你好"))
        contents = [e.content for e in events if e.type == "content"]
        self.assertEqual(contents, ["直接", "回答"])
        self.assertEqual(events[-1].type, "done")
        self.assertEqual([h["role"] for h in agent._history], ["user", "assistant"])

    def test_run_stream_react_loop(self):
        """流式 ReAct：第一轮带 tool_calls，第二轮最终回答"""
        from src.ai.agent import DiagnosticAgent
        from src.ai.providers import StreamEvent

        tool_call = [{
            "id": "c1", "type": "function",
            "function": {"name": "lookup_code", "arguments": '{"code": "P0300"}'},
        }]
        llm = self._make_stream_llm([
            iter([StreamEvent("content", content="查一下"), StreamEvent("tool_calls", tool_calls=tool_call), StreamEvent("done")]),
            iter([StreamEvent("content", content="P0300 是失火"), StreamEvent("done")]),
        ])
        agent = DiagnosticAgent(kb=None, llm=llm)

        calls = []
        events = list(agent.run_stream(
            "查 P0300",
            on_tool_call=lambda n, a: calls.append((n, a)),
        ))
        contents = [e.content for e in events if e.type == "content"]
        self.assertEqual(contents, ["查一下", "P0300 是失火"])
        self.assertEqual(calls, [("lookup_code", {"code": "P0300"})])
        self.assertEqual(events[-1].type, "done")

    def test_run_stream_exception_before_content_falls_back(self):
        """流式调用抛异常且未 yield 内容 → 降级到普通 chat"""
        from src.ai.agent import DiagnosticAgent
        from src.ai.providers import StreamEvent

        llm = MagicMock()
        llm.is_local = False
        llm.chat_with_tools_stream.side_effect = RuntimeError("stream down")
        llm.chat.return_value = "降级回答"
        agent = DiagnosticAgent(kb=None, llm=llm)

        events = list(agent.run_stream("查 P0300"))
        self.assertEqual([e.content for e in events if e.type == "content"], ["降级回答"])
        self.assertEqual(events[-1].type, "done")

    def test_run_stream_exception_after_content(self):
        """流式调用在 yield 部分内容后中断 → 报错结束，不重复回复"""
        from src.ai.agent import DiagnosticAgent
        from src.ai.providers import StreamEvent

        def _partial_then_fail():
            yield StreamEvent("content", content="部分内容")
            raise RuntimeError("连接中断")

        llm = MagicMock()
        llm.is_local = False
        llm.chat_with_tools_stream.return_value = _partial_then_fail()
        agent = DiagnosticAgent(kb=None, llm=llm)

        events = list(agent.run_stream("查 P0300"))
        contents = [e.content for e in events if e.type == "content"]
        self.assertIn("部分内容", contents[0])
        self.assertTrue(any("流式中断" in e.content for e in events if e.type == "content"))
        self.assertEqual(events[-1].type, "done")

    def test_run_stream_fallback_chat_fails(self):
        """流式失败且降级 chat 也失败 → 返回 AI 调用失败占位"""
        from src.ai.agent import DiagnosticAgent
        from src.ai.providers import StreamEvent

        llm = MagicMock()
        llm.is_local = False
        llm.chat_with_tools_stream.side_effect = RuntimeError("stream down")
        llm.chat.side_effect = RuntimeError("chat down too")
        agent = DiagnosticAgent(kb=None, llm=llm)

        events = list(agent.run_stream("查 P0300"))
        contents = [e.content for e in events if e.type == "content"]
        self.assertIn("AI 调用失败", contents[0])
        self.assertEqual(events[-1].type, "done")

    def test_run_stream_react_dedup_breaks_to_summary(self):
        """流式 ReAct：重复工具调用 → break 后普通 chat 总结"""
        from src.ai.agent import DiagnosticAgent
        from src.ai.providers import StreamEvent

        tool_call = [{
            "id": "c1", "type": "function",
            "function": {"name": "lookup_code", "arguments": '{"code": "P0300"}'},
        }]
        llm = MagicMock()
        llm.is_local = False
        llm.chat_with_tools_stream.side_effect = [
            iter([StreamEvent("content", content="查"), StreamEvent("tool_calls", tool_calls=tool_call), StreamEvent("done")]),
            iter([StreamEvent("content", content="再查"), StreamEvent("tool_calls", tool_calls=tool_call), StreamEvent("done")]),
        ]
        llm.chat.return_value = "总结答案"
        agent = DiagnosticAgent(kb=None, llm=llm)

        events = list(agent.run_stream("查 P0300"))
        contents = [e.content for e in events if e.type == "content"]
        self.assertIn("总结答案", contents)
        self.assertEqual(events[-1].type, "done")

    def test_run_with_prefetch_callbacks(self):
        """降级模式预查询触发全部 on_tool_call/on_tool_result 回调"""
        import tempfile
        from src.ai.agent import DiagnosticAgent
        from tests.db_fixtures import setup_test_db, make_test_kb

        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test.db")
        setup_test_db(db_path)
        kb = make_test_kb(db_path)
        try:
            llm = MagicMock()
            llm.is_local = False
            llm.chat_with_tools.return_value = {"content": "", "tool_calls": None}
            llm.chat.return_value = "回答"
            agent = DiagnosticAgent(kb=kb, llm=llm)

            calls = []
            results = []
            agent.run(
                "比亚迪秦PLUS EV 的 P0300 抖动问题",
                on_tool_call=lambda n, a: calls.append(n),
                on_tool_result=lambda n, r: results.append(n),
            )
            self.assertIn("lookup_code", calls)
            self.assertIn("get_vehicle_info", calls)
            self.assertIn("search_by_symptom", calls)
            self.assertEqual(len(calls), len(results))
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)
            os.rmdir(temp_dir)

    def test_chat_stream_compat(self):
        """chat_stream 兼容接口：只 yield content"""
        from src.ai.agent import DiagnosticAgent
        from src.ai.providers import StreamEvent

        llm = self._make_stream_llm([iter([
            StreamEvent("content", content="你好"),
            StreamEvent("done"),
        ])])
        agent = DiagnosticAgent(kb=None, llm=llm)
        self.assertEqual(list(agent.chat_stream("你好")), ["你好"])

    def test_build_tool_assistant_msg_no_tool_calls(self):
        """无 tool_calls 时返回基础 assistant 消息"""
        from src.ai.agent import DiagnosticAgent
        agent = DiagnosticAgent(kb=None, llm=MagicMock())
        msg = agent._build_tool_assistant_msg("文本", [])
        self.assertEqual(msg, {"role": "assistant", "content": "文本"})

    def test_build_tool_assistant_msg_is_local_error(self):
        """is_local 读取异常时按 OpenAI 处理（携带 tool_calls）"""
        from src.ai.agent import DiagnosticAgent

        class _LLMNoIsLocal:
            @property
            def is_local(self):
                raise AttributeError("no is_local")

        agent = DiagnosticAgent(kb=None, llm=_LLMNoIsLocal())
        msg = agent._build_tool_assistant_msg("文本", [{"id": "c1", "function": {"name": "lookup_code", "arguments": "{}"}}])
        self.assertIn("tool_calls", msg)

    def test_execute_tool_calls_json_decode_error(self):
        """工具参数 JSON 解析失败 → 降级为空 dict，不崩溃"""
        from src.ai.agent import DiagnosticAgent
        llm = MagicMock()
        agent = DiagnosticAgent(kb=None, llm=llm)
        tool_call = {"id": "c1", "function": {"name": "lookup_code", "arguments": "not-json"}}
        called = []
        messages = []
        any_new = agent._execute_tool_calls([tool_call], messages, set(), on_tool_call=lambda n, a: called.append((n, a)))
        self.assertTrue(any_new)
        self.assertEqual(called, [("lookup_code", {})])
        # 工具结果以 tool role 追加到消息
        self.assertEqual(messages[-1]["role"], "tool")

    def test_react_loop_next_round_fails_then_summary(self):
        """下一轮 chat_with_tools 失败 → break 后用普通 chat 总结"""
        from src.ai.agent import DiagnosticAgent

        tool_call = {
            "id": "c1", "type": "function",
            "function": {"name": "lookup_code", "arguments": '{"code": "P0300"}'},
        }
        llm = MagicMock()
        llm.is_local = False
        llm.chat_with_tools.side_effect = [
            {"content": "查", "tool_calls": [tool_call]},
            RuntimeError("network down"),
        ]
        llm.chat.return_value = "总结回答"
        agent = DiagnosticAgent(kb=None, llm=llm)
        self.assertEqual(agent.run("查 P0300"), "总结回答")

    def test_react_loop_summary_generation_fails(self):
        """总结 chat 也失败 → 返回占位错误消息"""
        from src.ai.agent import DiagnosticAgent

        tool_call = {
            "id": "c1", "type": "function",
            "function": {"name": "lookup_code", "arguments": '{"code": "P0300"}'},
        }
        llm = MagicMock()
        llm.is_local = False
        llm.chat_with_tools.return_value = {"content": "查", "tool_calls": [tool_call]}
        llm.chat.side_effect = RuntimeError("boom")
        agent = DiagnosticAgent(kb=None, llm=llm)
        result = agent.run("查 P0300")
        self.assertIn("诊断轮次过多", result)

    def test_run_with_prefetch_no_data(self):
        """降级模式：无预查询数据时提示知识库未收录"""
        from src.ai.agent import DiagnosticAgent

        llm = MagicMock()
        llm.is_local = False
        llm.chat_with_tools.return_value = {"content": "", "tool_calls": None}
        llm.chat.return_value = "回答"
        agent = DiagnosticAgent(kb=None, llm=llm)

        agent.run("你好")
        message = llm.chat.call_args[1]["message"]
        self.assertIn("知识库中未找到直接相关的数据", message)
        self.assertIn("不要编造故障码含义", message)

    def test_run_with_prefetch_session_context(self):
        """降级模式：带会话上下文（故障码+车型）"""
        import tempfile
        from src.ai.agent import DiagnosticAgent
        from tests.db_fixtures import setup_test_db, make_test_kb

        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test.db")
        setup_test_db(db_path)
        kb = make_test_kb(db_path)
        try:
            llm = MagicMock()
            llm.is_local = False
            llm.chat_with_tools.return_value = {"content": "", "tool_calls": None}
            llm.chat.return_value = "回答"
            agent = DiagnosticAgent(kb=kb, llm=llm)
            agent.start_diagnosis("P0300", "比亚迪秦PLUS EV")

            agent.run("下一步怎么办")
            message = llm.chat.call_args[1]["message"]
            self.assertIn("故障码: P0300", message)
            self.assertIn("车型: 比亚迪秦PLUS EV", message)
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)
            os.rmdir(temp_dir)

    def test_run_with_prefetch_vehicle(self):
        """降级模式：识别车型关键词并预查询车型信息"""
        import tempfile
        from src.ai.agent import DiagnosticAgent
        from tests.db_fixtures import setup_test_db, make_test_kb

        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test.db")
        setup_test_db(db_path)
        kb = make_test_kb(db_path)
        try:
            llm = MagicMock()
            llm.is_local = False
            llm.chat_with_tools.return_value = {"content": "", "tool_calls": None}
            llm.chat.return_value = "回答"
            agent = DiagnosticAgent(kb=kb, llm=llm)

            agent.run("比亚迪秦PLUS EV 有哪些通病")
            message = llm.chat.call_args[1]["message"]
            self.assertIn("车型信息", message)
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)
            os.rmdir(temp_dir)

    def test_run_with_prefetch_symptom(self):
        """降级模式：识别症状关键词并搜索"""
        from src.ai.agent import DiagnosticAgent

        llm = MagicMock()
        llm.is_local = False
        llm.chat_with_tools.return_value = {"content": "", "tool_calls": None}
        llm.chat.return_value = "回答"
        agent = DiagnosticAgent(kb=None, llm=llm)

        agent.run("车辆怠速抖动")
        message = llm.chat.call_args[1]["message"]
        self.assertIn("症状搜索", message)

    def test_extract_model(self):
        """车型名提取"""
        from src.ai.agent import DiagnosticAgent
        agent = DiagnosticAgent(kb=None, llm=MagicMock())
        self.assertEqual(agent._extract_model("比亚迪秦PLUS EV", "比亚迪"), "秦")
        self.assertEqual(agent._extract_model("特斯拉Model 3 动力问题", "特斯拉"), "Model 3")
        self.assertEqual(agent._extract_model("比亚迪某某未知车型", "比亚迪"), "")

    def test_chat_compat(self):
        """chat 兼容接口调用 run"""
        from src.ai.agent import DiagnosticAgent
        llm = MagicMock()
        llm.is_local = False
        llm.chat_with_tools.return_value = {"content": "直接回答", "tool_calls": None}
        agent = DiagnosticAgent(kb=None, llm=llm)
        self.assertEqual(agent.chat("P0300 是什么"), "直接回答")

    def test_create_agent_helper(self):
        """create_agent 便捷函数"""
        from src.ai.agent import create_agent
        agent = create_agent(llm=MagicMock())
        self.assertIsNotNone(agent.tools)
        self.assertGreaterEqual(len(agent.tools), 9)


class TestAgentExpertRouting(unittest.TestCase):
    """专家路由测试（使用临时数据库）"""

    def setUp(self):
        import tempfile
        from src.ai.agent import DiagnosticAgent
        from tests.db_fixtures import setup_test_db, make_test_kb
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        setup_test_db(self.db_path)
        self.kb = make_test_kb(self.db_path)
        self.agent = DiagnosticAgent(kb=self.kb, llm=MagicMock())

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_route_ev_bms(self):
        self.assertEqual(self.agent._select_expert("EV-BMS-001", ""), "battery")

    def test_route_ev_motor(self):
        self.assertEqual(self.agent._select_expert("EV-MOTOR-001", ""), "motor")

    def test_route_ev_thermal(self):
        self.assertEqual(self.agent._select_expert("EV-THERMAL-001", ""), "battery")

    def test_route_ev_vcu(self):
        self.assertEqual(self.agent._select_expert("EV-VCU-001", ""), "vcu")

    def test_route_p0a_default_bms(self):
        self.assertEqual(self.agent._select_expert("P0A00", ""), "battery")

    def test_route_p0a_motor_desc(self):
        """P0Axx 码描述含电机关键词 → 电机专家"""
        self.assertEqual(self.agent._select_expert("P0A1F", ""), "motor")

    def test_route_traditional_general(self):
        self.assertEqual(self.agent._select_expert("P0300", ""), "general")
        self.assertEqual(self.agent._select_expert("B1100", ""), "general")

    def test_route_keywords_bms(self):
        self.assertEqual(self.agent._select_expert(None, "电池绝缘问题"), "battery")

    def test_route_keywords_motor(self):
        self.assertEqual(self.agent._select_expert(None, "电机扭矩异常"), "motor")

    def test_route_keywords_vcu(self):
        self.assertEqual(self.agent._select_expert(None, "整车无法上电"), "vcu")

    def test_route_default_general(self):
        self.assertEqual(self.agent._select_expert(None, "随便聊聊"), "general")

    def test_route_kb_error_falls_back(self):
        from unittest.mock import patch
        with patch.object(self.kb, "lookup", side_effect=RuntimeError("db error")):
            self.assertEqual(self.agent._select_expert("P0300", ""), "general")


if __name__ == "__main__":
    unittest.main()
