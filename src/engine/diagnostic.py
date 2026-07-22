"""
诊断引擎 - 核心诊断逻辑
协调知识库查询和 AI 建议，生成完整的诊断结果
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

from src.engine.knowledge_base import KnowledgeBase
from src.ai.llm_client import LLMClient


@dataclass
class DiagnosticResult:
    """诊断结果数据类"""
    code: str                              # 故障码
    knowledge: Optional[Dict[str, Any]]    # 知识库查询结果
    ai_suggestion: Optional[str]           # AI 诊断建议
    ai_available: bool                     # AI 是否可用
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def has_knowledge(self) -> bool:
        """知识库中是否有该故障码"""
        return self.knowledge is not None

    def has_ai(self) -> bool:
        """是否有 AI 建议"""
        return self.ai_suggestion is not None and self.ai_available


class DiagnosticEngine:
    """
    诊断引擎
    协调知识库 + AI，生成诊断结果
    """

    def __init__(self, knowledge_base: Optional[KnowledgeBase] = None, llm: Optional[LLMClient] = None):
        super().__init__()
        self.kb = knowledge_base or KnowledgeBase()
        self.llm = llm or LLMClient()

    def diagnose(self, code: str, vehicle_info: str = "", additional_info: str = "") -> DiagnosticResult:
        """
        执行诊断

        Args:
            code: 故障码
            vehicle_info: 车型信息（可选）
            additional_info: 附加描述信息（可选）

        Returns:
            DiagnosticResult 对象
        """
        code = code.strip().upper()

        # 1. 查询知识库
        knowledge = self.kb.lookup(code)

        # 2. 获取 AI 建议（异步处理，这里先尝试获取）
        ai_suggestion = None
        ai_available = self.llm.is_available()

        if ai_available:
            try:
                ai_suggestion = self.llm.get_diagnostic_suggestion(
                    code=code,
                    knowledge=knowledge,
                    vehicle_info=vehicle_info,
                    additional_info=additional_info
                )
            except Exception as e:
                ai_suggestion = f"⚠️ AI 诊断服务暂时不可用: {str(e)}"
                ai_available = False

        return DiagnosticResult(
            code=code,
            knowledge=knowledge,
            ai_suggestion=ai_suggestion,
            ai_available=ai_available
        )

    def search_codes(self, keyword: str) -> List[Dict[str, Any]]:
        """搜索故障码"""
        return self.kb.search(keyword)

    def get_auto_complete(self, partial: str) -> List[str]:
        """获取自动补全建议"""
        return self.kb.get_suggestions(partial)

    def check_database_status(self) -> Dict[str, Any]:
        """检查数据库状态"""
        return self.kb.db.get_database_info()
