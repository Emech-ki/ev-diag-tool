"""
诊断引擎 - 核心诊断逻辑
协调知识库查询和 AI 建议，生成完整的诊断结果
"""

import re
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


@dataclass
class MultiCodeDiagnosticResult:
    """多故障码诊断结果数据类"""
    codes: List[str]                              # 故障码列表
    results: List[DiagnosticResult]               # 每个码的诊断结果
    ai_suggestion: Optional[str]                  # AI 综合分析建议
    ai_available: bool                            # AI 是否可用
    symptom_context: str = ""                     # 技师报告的症状上下文（现象/具体表现/排查提示）
    priority_codes: List[str] = field(default_factory=list)  # 向导标注的高疑似候选码（有序，越靠前越疑似）
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def has_knowledge(self) -> bool:
        """是否有知识库结果"""
        return any(r.has_knowledge() for r in self.results)

    def has_ai(self) -> bool:
        """是否有 AI 建议"""
        return self.ai_suggestion is not None and self.ai_available


def parse_fault_codes(input_text: str) -> List[str]:
    """
    从输入文本中解析故障码

    支持的格式:
    - 逗号分隔: P0300, P0171, P0420
    - 空格分隔: P0300 P0171 P0420
    - 混合分隔: P0300, P0171 P0420
    - 换行分隔: P0300\nP0171\nP0420

    Returns:
        故障码列表（已转大写、去重、保持顺序）
    """
    if not input_text:
        return []

    # 使用正则表达式匹配故障码格式:
    #   - EV 系统码: EV-BMS-001（新能源系统，与 _split_history_codes 保持一致）
    #   - 标准码: 字母(P/B/C/U) + 4位（可能含十六进制字母，如 P0A00、B001A）
    # 注意: 标准码不能用 \d{4}，因为后 4 位常含 A-F（如 P0A0F、B001A）
    pattern = r'(?:\b[Ee][Vv]-[A-Za-z]+-\d+\b|\b[PpBbCcUu][0-9A-Fa-f]{4}\b)'
    matches = re.findall(pattern, input_text)

    # 转大写、去重、保持顺序
    seen = set()
    codes = []
    for code in matches:
        code_upper = code.upper()
        if code_upper not in seen:
            seen.add(code_upper)
            codes.append(code_upper)

    return codes


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
        执行单故障码诊断

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
                ai_suggestion = f"[警告] AI 诊断服务暂时不可用: {str(e)}"
                ai_available = False

        return DiagnosticResult(
            code=code,
            knowledge=knowledge,
            ai_suggestion=ai_suggestion,
            ai_available=ai_available
        )

    def diagnose_multiple(self, codes: List[str], vehicle_info: str = "", additional_info: str = "",
                          priority_codes: Optional[List[str]] = None) -> MultiCodeDiagnosticResult:
        """
        执行多故障码诊断

        Args:
            codes: 故障码列表
            vehicle_info: 车型信息（可选）
            additional_info: 附加描述信息（可选，含向导带入的症状上下文）
            priority_codes: 向导标注的高疑似候选码顺序（越靠前越疑似，可选）

        Returns:
            MultiCodeDiagnosticResult 对象
        """
        # 1. 批量查询知识库
        knowledge_map = self.kb.lookup_multiple(codes)

        # 2. 构建结果列表（is_available 只查一次，避免多次网络探测）
        ai_available = self.llm.is_available()
        results = []
        for code in codes:
            knowledge = knowledge_map.get(code.upper())
            results.append(DiagnosticResult(
                code=code,
                knowledge=knowledge,
                ai_suggestion=None,
                ai_available=ai_available
            ))

        # 3. 获取 AI 综合分析
        ai_suggestion = None

        if ai_available:
            try:
                # 收集所有码的知识库信息
                knowledge_list = []
                for r in results:
                    if r.knowledge:
                        knowledge_list.append({
                            "code": r.code,
                            "description": r.knowledge.get("description", ""),
                            "severity": r.knowledge.get("severity", ""),
                            "system": r.knowledge.get("system", "")
                        })

                ai_suggestion = self.llm.get_multi_code_analysis(
                    codes=codes,
                    knowledge_list=knowledge_list,
                    vehicle_info=vehicle_info,
                    additional_info=additional_info,
                    priority_codes=priority_codes,
                )
            except Exception as e:
                ai_suggestion = f"⚠️ AI 综合分析服务暂时不可用: {str(e)}"
                ai_available = False

        return MultiCodeDiagnosticResult(
            codes=codes,
            results=results,
            ai_suggestion=ai_suggestion,
            ai_available=ai_available,
            symptom_context=additional_info,
            priority_codes=list(priority_codes or [])
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
