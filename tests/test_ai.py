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
        from src.ai.llm_client import create_provider

        ollama = create_provider("ollama")
        self.assertEqual(ollama.provider_name, "ollama")

        openai = create_provider("openai")
        self.assertEqual(openai.provider_name, "openai")

        # 默认返回 ollama
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
        self.assertEqual(len(registry), 9)

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


if __name__ == "__main__":
    unittest.main()
