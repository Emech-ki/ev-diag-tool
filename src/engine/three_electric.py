"""
三电诊断 — 领域定义与概览统计

三电 = 电池(Battery) + 电机(Motor) + 电控(VCU)。
提供三大系统的系统码映射、向导数据加载与覆盖概览统计。

约束：
    - 纯逻辑模块，不依赖 PyQt
    - 向导数据 data/seed/three_electric_guide.json 带模块级缓存（风格对齐 _load_expert_context）
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List

from src.engine.knowledge_base import KnowledgeBase

# 三电 → 覆盖的 EV 系统码
THREE_ELECTRIC = {
    "battery": {
        "name": "电池系统",
        "icon": "🔋",
        "systems": ("EV-BMS", "EV-HV", "EV-OBC", "EV-DCDC", "EV-THERMAL"),
    },
    "motor": {
        "name": "电机系统",
        "icon": "⚙️",
        "systems": ("EV-MOTOR", "EV-REGEN"),
    },
    "vcu": {
        "name": "电控系统",
        "icon": "🖥️",
        "systems": ("EV-VCU",),
    },
}

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
    except Exception:
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
