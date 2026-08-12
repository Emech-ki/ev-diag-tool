"""
三电诊断 — 领域定义与概览统计

三电 = 电池(Battery) + 电机(Motor) + 电控(VCU)。
提供三大系统的系统码映射、向导数据加载与覆盖概览统计。

约束：
    - 纯逻辑模块，不依赖 PyQt
    - 向导数据 data/seed/three_electric_guide.json 带模块级缓存（风格对齐 _load_expert_context）
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

from src.engine.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

# 三电 → 覆盖的 EV 系统码（域映射单一真源）
# 修改此映射即同步影响：向导概览 / 专家路由(_select_expert) / 专家展示名
# expert_context.json 的 domains 由 get_expert_domains() 校验一致性
THREE_ELECTRIC = {
    "battery": {
        "name": "电池系统",
        "expert_name": "电池系统专家",
        "icon": "🔋",
        "systems": ("EV-BMS", "EV-HV", "EV-OBC", "EV-DCDC", "EV-THERMAL"),
        "keywords": ("电池", "bms", "单体", "电压", "绝缘", "充电", "soc", "soh",
                     "均衡", "接触器", "预充", "冷却", "热管理", "温度", "热失控"),
    },
    "motor": {
        "name": "电机系统",
        "expert_name": "电机驱动专家",
        "icon": "⚙️",
        "systems": ("EV-MOTOR", "EV-REGEN"),
        "keywords": ("电机", "扭矩", "旋变", "电机位置", "驱动", "三相", "逆变器",
                     "mcu", "转速", "再生", "回收"),
    },
    "vcu": {
        "name": "电控系统",
        "expert_name": "电控系统专家",
        "icon": "🖥️",
        "systems": ("EV-VCU",),
        "keywords": ("电控", "整车", "上下电", "上电", "下电", "网关", "网络", "can",
                     "钥匙", "挡位", "唤醒", "休眠", "防盗"),
    },
}

GENERAL_EXPERT_NAME = "通用诊断专家"

_GUIDE_CACHE = None
_GUIDE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "seed" / "three_electric_guide.json"


def get_subsystems() -> List[Dict[str, Any]]:
    """获取三电子系统定义列表（battery/motor/vcu 顺序）"""
    return [
        {"key": key, "name": info["name"], "icon": info["icon"]}
        for key, info in THREE_ELECTRIC.items()
    ]


def get_systems_for(subsystem: str) -> tuple:
    """返回子系统覆盖的系统码元组"""
    info = THREE_ELECTRIC.get(subsystem)
    return tuple(info["systems"]) if info else ()


def get_expert_domains() -> Dict[str, tuple]:
    """返回 子系统 → 覆盖系统码 的映射（专家路由域映射单一来源）"""
    return {key: info["systems"] for key, info in THREE_ELECTRIC.items()}


def get_subsystem_for_system(system: str) -> Optional[str]:
    """
    按系统码前缀路由到三电子系统（battery/motor/vcu），未知返回 None

    匹配规则：系统码以 mapping 中任一前缀开头即命中（如 EV-BMS-001 → battery）。
    """
    sys_upper = (system or "").upper()
    for key, systems in get_expert_domains().items():
        for prefix in systems:
            if sys_upper.startswith(prefix):
                return key
    return None


def get_expert_name(subsystem: str) -> str:
    """返回子系统对应的专家展示名（未匹配则返回通用诊断专家）"""
    info = THREE_ELECTRIC.get(subsystem)
    return info["expert_name"] if info else GENERAL_EXPERT_NAME


def get_expert_keywords(subsystem: str) -> tuple:
    """返回子系统的诊断关键词元组（未匹配返回空元组）"""
    info = THREE_ELECTRIC.get(subsystem)
    return tuple(info.get("keywords", ())) if info else ()


def match_keywords(text: str) -> Optional[str]:
    """
    按关键词把文本路由到三电子系统（battery/motor/vcu），未命中返回 None

    关键词列表是 THREE_ELECTRIC 的 keywords 单一真源；命中优先级固定为 battery → motor → vcu。
    """
    if not text:
        return None
    lowered = text.lower()
    for sub in ("battery", "motor", "vcu"):
        if any(kw in lowered for kw in get_expert_keywords(sub)):
            return sub
    return None


def load_three_electric_guide() -> dict:
    """加载三电向导数据（带模块级缓存）"""
    global _GUIDE_CACHE
    if _GUIDE_CACHE is None:
        if _GUIDE_PATH.exists():
            with open(str(_GUIDE_PATH), "r", encoding="utf-8") as f:
                _GUIDE_CACHE = json.load(f)
        else:
            _GUIDE_CACHE = {}
    return _GUIDE_CACHE


def get_guide_for(subsystem: str) -> dict:
    """获取指定子系统的向导定义"""
    guide = load_three_electric_guide()
    return guide.get(subsystem, {})


def build_overview(kb: KnowledgeBase, subsystem: str) -> Dict[str, Any]:
    """
    构建指定三电子系统的覆盖概览

    Returns:
        {
            "subsystem": "battery",
            "name": "电池系统",
            "icon": "🔋",
            "systems": [...覆盖明细: {system, total, with_detail, sev分布}],
            "total_codes": 250,
            "codes_with_detail": 250,
            "common_codes": [最常见的前 N 条码 {code, description, severity}]
        }
    """
    info = THREE_ELECTRIC.get(subsystem)
    if info is None:
        return {"subsystem": subsystem, "name": subsystem, "icon": "❓",
                "systems": [], "total_codes": 0, "codes_with_detail": 0, "common_codes": []}

    coverage = kb.get_system_detail_coverage(info["systems"]) or []
    total = sum(r["total"] for r in coverage)
    with_detail = sum(r["with_detail"] for r in coverage)

    common = []
    try:
        # 逐个系统前缀查询，过滤 + 按严重度排序取前 10
        sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        filtered = []
        for sys_name in info["systems"]:
            rows = kb.get_codes_by_system_prefix(sys_name, limit=50)
            filtered.extend(rows)
        filtered.sort(key=lambda r: sev_order.get(r.get("severity", "low"), 9))
        common = filtered[:10]
    except (KeyError, TypeError, AttributeError) as e:
        logger.debug(f"build_overview common_codes 查询失败: {e}")
        common = []

    return {
        "subsystem": subsystem,
        "name": info["name"],
        "icon": info["icon"],
        "systems": coverage,
        "total_codes": total,
        "codes_with_detail": with_detail,
        "common_codes": common,
    }
