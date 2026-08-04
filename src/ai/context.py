"""
诊断上下文数据类
封装多次传递的参数，减少 Data Clumps
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any


@dataclass
class DiagnosticContext:
    """诊断上下文，封装诊断过程中多次传递的参数"""
    codes: List[str] = field(default_factory=list)
    results: List[Any] = field(default_factory=list)
    correlation: Optional[Any] = None
    vehicle_info: str = ""
    additional_info: str = ""

    def add_code(self, code: str, result: Any = None) -> None:
        """添加故障码和对应结果"""
        self.codes.append(code)
        self.results.append(result)

    def get_code_result_pairs(self) -> List[tuple]:
        """获取故障码和结果的配对列表"""
        return list(zip(self.codes, self.results))

    @property
    def code_count(self) -> int:
        """获取故障码数量"""
        return len(self.codes)

    @property
    def has_correlation(self) -> bool:
        """是否有故障码关联性分析"""
        return self.correlation is not None and getattr(self.correlation, 'is_correlated', False)
