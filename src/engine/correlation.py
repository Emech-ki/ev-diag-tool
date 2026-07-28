"""
故障码关联性分析
判断多个故障码之间是否存在关联，用于决定综合诊断还是分别诊断
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from src.engine.knowledge_base import KnowledgeBase


@dataclass
class CodeRelation:
    """两个故障码之间的关系"""
    code_a: str
    code_b: str
    relation_type: str  # "direct_related" / "same_system" / "cross_system"
    confidence: float   # 0.0 ~ 1.0
    reason: str         # 关联原因描述


@dataclass
class CorrelationResult:
    """关联性分析结果"""
    codes: List[str]                          # 输入的所有故障码
    is_correlated: bool                       # 是否整体关联
    relation_groups: List[List[str]]          # 关联分组
    relations: List[CodeRelation]             # 所有两两关系
    analysis_summary: str                     # 分析摘要

    @property
    def group_count(self) -> int:
        return len(self.relation_groups)


class CorrelationAnalyzer:
    """故障码关联性分析器"""

    def __init__(self, kb: Optional[KnowledgeBase] = None):
        self.kb = kb or KnowledgeBase()

    def analyze(self, codes: List[str]) -> CorrelationResult:
        """
        分析多个故障码的关联性
        
        关联性判断规则（按优先级）：
        1. 直接关联：A 的 related_codes 包含 B
        2. 同系统关联：A 和 B 属于同一系统（如都是 EV-BMS）
        3. 交叉关联：A 的 related_codes 的 related_codes 包含 C（传递关联）
        
        Args:
            codes: 故障码列表，如 ["P0300", "P0301", "P0171"]
            
        Returns:
            CorrelationResult 对象
        """
        codes = [c.strip().upper() for c in codes if c.strip()]
        
        if len(codes) <= 1:
            return CorrelationResult(
                codes=codes,
                is_correlated=False,
                relation_groups=[codes] if codes else [],
                relations=[],
                analysis_summary="单个故障码，无需关联分析" if codes else "无故障码",
            )
        
        # 1. 查询每个码的知识库信息
        code_infos: Dict[str, Dict[str, Any]] = {}
        for code in codes:
            info = self.kb.lookup(code)
            if info:
                code_infos[code] = info
        
        # 2. 构建关联矩阵（两两判断）
        relations: List[CodeRelation] = []
        for i, code_a in enumerate(codes):
            for code_b in codes[i+1:]:
                relation = self._analyze_pair(code_a, code_b, code_infos)
                if relation:
                    relations.append(relation)
        
        # 3. 基于关联关系做分组（Union-Find 算法）
        relation_groups = self._group_codes(codes, relations)
        
        # 4. 判断整体是否关联
        is_correlated = len(relation_groups) == 1
        
        # 5. 生成摘要
        summary = self._build_summary(codes, relation_groups, relations, code_infos)
        
        return CorrelationResult(
            codes=codes,
            is_correlated=is_correlated,
            relation_groups=relation_groups,
            relations=relations,
            analysis_summary=summary,
        )

    def _analyze_pair(
        self, 
        code_a: str, 
        code_b: str, 
        code_infos: Dict[str, Dict[str, Any]]
    ) -> Optional[CodeRelation]:
        """分析两个故障码之间的关系"""
        
        info_a = code_infos.get(code_a)
        info_b = code_infos.get(code_b)
        
        # 规则 1: 直接关联（A 的 related_codes 包含 B）
        if info_a:
            related_a = info_a.get("related_codes", [])
            if code_b in related_a:
                return CodeRelation(
                    code_a=code_a, code_b=code_b,
                    relation_type="direct_related",
                    confidence=0.95,
                    reason=f"{code_a} 的关联故障码包含 {code_b}"
                )
        
        if info_b:
            related_b = info_b.get("related_codes", [])
            if code_a in related_b:
                return CodeRelation(
                    code_a=code_a, code_b=code_b,
                    relation_type="direct_related",
                    confidence=0.95,
                    reason=f"{code_b} 的关联故障码包含 {code_a}"
                )
        
        # 规则 2: 同系统关联
        if info_a and info_b:
            sys_a = (info_a.get("system") or "").upper()
            sys_b = (info_b.get("system") or "").upper()
            if sys_a and sys_a == sys_b:
                # 对 EV 系统码做更精确的子系统判断
                # 数据库中 EV-BMS-001 和 EV-MOTOR-001 的 system 都是 "Powertrain"
                # 但它们是不同子系统，不应有高置信度关联
                ev_prefixes = ["EV-BMS", "EV-MOTOR", "EV-OBC", "EV-DCDC", "EV-THERMAL", "EV-HV"]
                prefix_a = next((p for p in ev_prefixes if code_a.startswith(p)), None)
                prefix_b = next((p for p in ev_prefixes if code_b.startswith(p)), None)

                if prefix_a and prefix_b:
                    # 两个都是 EV 码
                    if prefix_a == prefix_b:
                        # 同子系统（如都是 EV-BMS）
                        return CodeRelation(
                            code_a=code_a, code_b=code_b,
                            relation_type="same_system",
                            confidence=0.7,
                            reason=f"同属 {prefix_a} 子系统"
                        )
                    else:
                        # 不同子系统（如 EV-BMS vs EV-MOTOR）
                        # 低置信度，可能是间接关联
                        return CodeRelation(
                            code_a=code_a, code_b=code_b,
                            relation_type="cross_system",
                            confidence=0.3,
                            reason=f"不同 EV 子系统 ({prefix_a} vs {prefix_b})"
                        )
                else:
                    # 传统系统码（P/B/C/U），保持原逻辑
                    return CodeRelation(
                        code_a=code_a, code_b=code_b,
                        relation_type="same_system",
                        confidence=0.6,
                        reason=f"同属 {sys_a} 系统"
                    )
        
        # 规则 3: 传递关联（A→X→B，X 是中间码）
        if info_a and info_b:
            related_a = set(info_a.get("related_codes", []))
            related_b = set(info_b.get("related_codes", []))
            common = related_a & related_b
            if common:
                return CodeRelation(
                    code_a=code_a, code_b=code_b,
                    relation_type="cross_system",
                    confidence=0.4,
                    reason=f"共同关联码: {', '.join(list(common)[:3])}"
                )
        
        return None  # 无关联

    def _group_codes(
        self, 
        codes: List[str], 
        relations: List[CodeRelation]
    ) -> List[List[str]]:
        """基于关联关系对故障码分组（Union-Find 并查集）"""
        parent = {code: code for code in codes}
        
        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        
        def union(x, y):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[rx] = ry
        
        # 只有高置信度的关系才合并（阈值可调）
        MERGE_THRESHOLD = 0.5
        for rel in relations:
            if rel.confidence >= MERGE_THRESHOLD:
                union(rel.code_a, rel.code_b)
        
        # 提取分组
        groups: Dict[str, List[str]] = {}
        for code in codes:
            root = find(code)
            groups.setdefault(root, []).append(code)
        
        return list(groups.values())

    def _build_summary(
        self,
        codes: List[str],
        relation_groups: List[List[str]],
        relations: List[CodeRelation],
        code_infos: Dict[str, Dict[str, Any]],
    ) -> str:
        """生成关联性分析摘要"""
        if len(codes) == 1:
            return "单个故障码"
        
        if len(relation_groups) == 1:
            # 所有码都关联
            if len(relations) == 1:
                rel = relations[0]
                return f"{rel.code_a} 与 {rel.code_b} {rel.reason}，存在关联"
            else:
                return f"所有 {len(codes)} 个故障码之间存在关联，可能存在共同根因"
        else:
            # 部分关联或无关联
            group_descs = []
            for i, group in enumerate(relation_groups, 1):
                if len(group) == 1:
                    group_descs.append(f"{group[0]}（独立）")
                else:
                    group_descs.append(f"{', '.join(group)}（关联）")
            
            return f"分为 {len(relation_groups)} 组: {'; '.join(group_descs)}"
