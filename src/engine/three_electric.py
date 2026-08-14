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

# 概览"常见故障"排序与配额（v3.6.1 可调常量）
# 融合频次 = 0.7×真实频次 + 0.3×合成频次（0-100 加权）
FREQ_REAL_WEIGHT = 0.7
FREQ_SEED_WEIGHT = 0.3
OVERVIEW_QUOTA = {"battery": 5, "motor": 3, "vcu": 2}  # 常见故障每子系统席位上限
OVERVIEW_PER_SYSTEM = 1  # 每个系统前缀（EV-BMS/EV-HV/...）至多占位数，保证跨系统均衡
OVERVIEW_TOP_N = 10  # 概览常见故障总数上限

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


def get_option_codes(option: dict) -> List[str]:
    """
    提取向导选项的候选故障码（按 weight 降序，保持原顺序稳定）

    candidate_codes 支持两种形态（v3.6.0 起统一为对象式）：
        - [{"code": "EV-BMS-001", "weight": 95}, ...]
        - ["EV-BMS-001", ...]  （旧式，weight 按数组序号回退）
    """
    raw = option.get("candidate_codes", []) or []
    parsed = []
    for i, item in enumerate(raw):
        if isinstance(item, dict):
            code = str(item.get("code", "")).strip()
            parsed.append((code, int(item.get("weight", 0) or 0), i))
        else:
            code = str(item).strip()
            parsed.append((code, max(0, 90 - i * 10), i))
    parsed.sort(key=lambda t: (-t[1], t[2]))
    return [t[0] for t in parsed if t[0]]


def get_option_weights(option: dict) -> Dict[str, int]:
    """提取向导选项的候选码显式置信度映射 {code: weight}（0-100）"""
    weights: Dict[str, int] = {}
    raw = option.get("candidate_codes", []) or []
    for i, item in enumerate(raw):
        if isinstance(item, dict):
            code = str(item.get("code", "")).strip()
            weights[code] = int(item.get("weight", 0) or 0)
        else:
            code = str(item).strip()
            weights[code] = max(0, 90 - i * 10)
    return weights


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
        # 逐个系统前缀查询，融合频次排序 + 系统额度/子系统配额取前 10
        sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        quota = dict(OVERVIEW_QUOTA)
        used_prefix = {}
        picked = []
        for sys_name in info["systems"]:
            rows = kb.get_codes_by_system_prefix(sys_name, limit=50)
            sub = get_subsystem_for_system(sys_name)
            picked.extend((r, sub, sys_name) for r in rows)
        # 严重度主键 + 融合频次(-)次键；同分按码序稳定
        picked.sort(key=lambda t: (
            sev_order.get(t[0].get("severity", "low"), 9),
            -(FREQ_REAL_WEIGHT * int(t[0].get("real_frequency", 0) or 0)
              + FREQ_SEED_WEIGHT * int(t[0].get("frequency", 0) or 0)),
            t[0].get("code", ""),
        ))
        # 双约束选取：子系统总配额（battery≤5...）+ 每系统前缀额度（默认 1 席）保证均衡
        for row, sub, prefix in picked:
            if sub is None:
                continue
            if quota.get(sub, 0) <= 0:
                continue
            if used_prefix.get(prefix, 0) >= OVERVIEW_PER_SYSTEM:
                continue
            common.append(row)
            quota[sub] -= 1
            used_prefix[prefix] = used_prefix.get(prefix, 0) + 1
            if len(common) >= OVERVIEW_TOP_N:
                break
        common = common[:OVERVIEW_TOP_N]
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
