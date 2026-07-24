"""
AI 客户端测试
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.config import OLLAMA_BASE_URL, OLLAMA_MODEL_NAME


class TestLLMClientConfig(unittest.TestCase):
    """LLMClient 配置测试"""

    def test_config_loading(self):
        """测试配置加载"""
        from src.config import OLLAMA_BASE_URL, OLLAMA_MODEL_NAME
        self.assertIsInstance(OLLAMA_BASE_URL, str)
        self.assertIn("http", OLLAMA_BASE_URL)
        self.assertIsInstance(OLLAMA_MODEL_NAME, str)
        self.assertGreater(len(OLLAMA_MODEL_NAME), 0)

    def test_llm_client_init(self):
        """测试 LLM 客户端初始化"""
        from src.ai.llm_client import LLMClient

        LLMClient._instance = None
        client = LLMClient()
        self.assertEqual(client.model_name, OLLAMA_MODEL_NAME)
        self.assertEqual(client.base_url, OLLAMA_BASE_URL)

    def test_llm_client_custom_params(self):
        """测试自定义参数"""
        from src.ai.llm_client import LLMClient

        LLMClient._instance = None
        client = LLMClient(model_name="custom:model", base_url="http://custom:1234")
        self.assertEqual(client.model_name, "custom:model")
        self.assertEqual(client.base_url, "http://custom:1234")

    def test_set_model(self):
        """测试模型切换"""
        from src.ai.llm_client import LLMClient

        LLMClient._instance = None
        client = LLMClient()
        original_model = client.model_name

        client.set_model("new:model")
        self.assertEqual(client.model_name, "new:model")

        client.set_model(original_model)

    def test_prompt_templates(self):
        """测试提示词模板"""
        from src.ai.prompt_templates import PromptTemplates

        templates = PromptTemplates()

        prompt = templates.build_diagnostic_prompt(
            code="P0300",
            knowledge={"description": "测试", "detail": "详情", "severity": "high",
                       "common_causes": ["原因1"], "diagnostic_steps": ["步骤1"]},
            vehicle_info="测试车型",
            additional_info="附加信息"
        )
        self.assertIn("P0300", prompt)
        self.assertIn("测试车型", prompt)

        system_prompt = templates.get_agent_system_prompt()
        self.assertIn("新能源汽车", system_prompt)


class TestAgent(unittest.TestCase):
    """DiagnosticAgent 测试"""

    def test_agent_init(self):
        """测试 Agent 初始化"""
        from src.ai.agent import DiagnosticAgent

        agent = DiagnosticAgent(kb=None, llm=None)
        self.assertIsNone(agent.session)

    def test_agent_start_diagnosis(self):
        """测试开始诊断"""
        from src.ai.agent import DiagnosticAgent

        agent = DiagnosticAgent(kb=None, llm=None)
        result = agent.start_diagnosis("P0300")
        self.assertEqual(result["code"], "P0300")
        self.assertIsNotNone(agent.session)

    def test_agent_reset_session(self):
        """测试重置会话"""
        from src.ai.agent import DiagnosticAgent

        agent = DiagnosticAgent(kb=None, llm=None)
        agent.start_diagnosis("P0300")
        agent.reset_session()
        self.assertIsNone(agent.session)

    def test_agent_get_session_summary(self):
        """测试获取会话摘要"""
        from src.ai.agent import DiagnosticAgent

        agent = DiagnosticAgent(kb=None, llm=None)
        summary = agent.get_session_summary()
        self.assertEqual(summary["status"], "no_active_session")

        agent.start_diagnosis("P0300")
        summary = agent.get_session_summary()
        self.assertEqual(summary["code"], "P0300")


if __name__ == "__main__":
    unittest.main()
