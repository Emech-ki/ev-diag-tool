"""
AI Agent 模块 (方案C)
实现基于 MCP/A2A 架构的诊断 Agent
支持对话式交互，引导技师逐步排查
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

from src.engine.knowledge_base import KnowledgeBase
from src.ai.llm_client import LLMClient


@dataclass
class ConversationTurn:
    """对话轮次"""
    role: str       # "user" 或 "assistant"
    content: str    # 消息内容
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))


@dataclass
class DiagnosticSession:
    """诊断会话"""
    code: str                       # 正在诊断的故障码
    vehicle_info: str = ""          # 车型信息
    context: Dict[str, Any] = field(default_factory=dict)  # 诊断上下文
    history: List[ConversationTurn] = field(default_factory=list)  # 对话历史


CONTEXT_WINDOW_SIZE = 10


class DiagnosticAgent:
    """
    诊断 AI Agent
    通过对话引导技师完成排查
    """

    def __init__(self, kb: Optional[KnowledgeBase] = None, llm: Optional[LLMClient] = None):
        super().__init__()
        self.kb = kb or KnowledgeBase()
        self.llm = llm or LLMClient()
        self.session: Optional[DiagnosticSession] = None

    def start_diagnosis(self, code: str, vehicle_info: str = "") -> Dict[str, Any]:
        """
        开始新的诊断会话

        Args:
            code: 故障码
            vehicle_info: 车型信息

        Returns:
            包含知识库信息和 AI 初始建议的字典
        """
        code = code.strip().upper()

        knowledge = self.kb.lookup(code)

        self.session = DiagnosticSession(
            code=code,
            vehicle_info=vehicle_info,
            context={"knowledge": knowledge}
        )

        result = {
            "code": code,
            "knowledge": knowledge,
            "message": self._build_initial_message(knowledge),
            "session_started": True
        }

        self.session.history.append(ConversationTurn(
            role="assistant",
            content=result["message"]
        ))

        return result

    def chat(self, message: str) -> str:
        """
        与 Agent 对话

        Args:
            message: 技师的消息

        Returns:
            Agent 的回复
        """
        if not self.session:
            return "请先输入故障码开始诊断。"

        # 记录用户消息
        self.session.history.append(ConversationTurn(role="user", content=message))

        # 构建 AI 回复
        try:
            # 将对话历史转换为 LLM 所需格式
            context = [
                {"role": turn.role, "content": turn.content}
                for turn in self.session.history[-10:]  # 最近10轮
            ]

            # 添加当前诊断上下文
            context_info = f"\n[当前诊断上下文]\n故障码: {self.session.code}\n"
            if self.session.vehicle_info:
                context_info += f"车型: {self.session.vehicle_info}\n"

            # 调用 LLM
            response = self.llm.chat(
                message=f"{context_info}\n\n技师提问: {message}",
                context=context
            )

            # 记录回复
            self.session.history.append(ConversationTurn(role="assistant", content=response))
            return response

        except Exception as e:
            error_msg = f"抱歉，AI 回复时遇到问题: {str(e)}。请重试。"
            self.session.history.append(ConversationTurn(role="assistant", content=error_msg))
            return error_msg

    def chat_stream(self, message: str):
        """
        与 Agent 对话（流式响应）

        Args:
            message: 技师的消息

        Yields:
            每个 token 文本
        """
        if not self.session:
            yield "请先输入故障码开始诊断。"
            return

        self.session.history.append(ConversationTurn(role="user", content=message))

        try:
            context = [
                {"role": turn.role, "content": turn.content}
                for turn in self.session.history[-10:]
            ]

            context_info = f"\n[当前诊断上下文]\n故障码: {self.session.code}\n"
            if self.session.vehicle_info:
                context_info += f"车型: {self.session.vehicle_info}\n"

            full_response = []
            for token in self.llm.chat_stream(
                message=f"{context_info}\n\n技师提问: {message}",
                context=context
            ):
                full_response.append(token)
                yield token

            self.session.history.append(ConversationTurn(role="assistant", content="".join(full_response)))

        except Exception as e:
            error_msg = f"抱歉，AI 回复时遇到问题: {str(e)}。请重试。"
            self.session.history.append(ConversationTurn(role="assistant", content=error_msg))
            yield error_msg

    def reset_session(self):
        """重置当前诊断会话"""
        self.session = None

    def get_session_summary(self) -> Dict[str, Any]:
        """获取当前会话摘要"""
        if not self.session:
            return {"status": "no_active_session"}

        return {
            "code": self.session.code,
            "vehicle_info": self.session.vehicle_info,
            "turns": len(self.session.history),
            "knowledge_found": self.session.context.get("knowledge") is not None
        }

    def _build_initial_message(self, knowledge: Optional[Dict[str, Any]]) -> str:
        """构建诊断开始时的初始消息"""
        if not knowledge:
            return (
                f"⚠️ 在知识库中未找到故障码 {self.session.code} 的信息。\n\n"
                f"但我仍然可以帮你分析。请告诉我以下信息：\n"
                f"1. 车辆出现了什么症状？\n"
                f"2. 故障灯是常亮还是闪烁？\n"
                f"3. 车辆行驶里程是多少？"
            )

        # 构建结构化回复
        msg = f"✅ 已查到故障码 {self.session.code} 的信息。\n\n"
        msg += f"**{knowledge.get('description', '')}**\n\n"

        # 严重程度
        severity = knowledge.get('severity', 'medium')
        severity_icons = {"low": "ℹ️", "medium": "⚠️", "high": "🔴", "critical": "🚨"}
        msg += f"{severity_icons.get(severity, '⚠️')} 严重程度: {severity.upper()}\n\n"

        # 常见原因概览
        causes = knowledge.get('common_causes', [])
        if causes:
            msg += "**可能的原因（按常见程度排序）：**\n"
            for i, cause in enumerate(causes[:5], 1):
                msg += f"{i}. {cause}\n"
            if len(causes) > 5:
                msg += f"   ...以及 {len(causes)-5} 个其他可能原因\n"

        # 开始引导
        msg += (
            "\n---\n"
            "🎯 **开始排查前，我想先了解几个情况：**\n\n"
            "1. 这个故障码是**第一次出现**还是**反复出现**？\n"
            "2. 车辆最近有没有做过维修或保养？\n"
            "3. 除了故障码，你观察到了什么症状？\n\n"
            "请告诉我，我帮你制定排查计划。"
        )

        return msg


# 便捷函数
def create_agent(kb: Optional[KnowledgeBase] = None, llm: Optional[LLMClient] = None) -> DiagnosticAgent:
    """创建诊断 Agent"""
    return DiagnosticAgent(kb=kb, llm=llm)
