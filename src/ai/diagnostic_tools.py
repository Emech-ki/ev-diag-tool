"""
诊断工具集 (Diagnostic Tools)
注册 9 个可被 LLM 调用的诊断工具

类比单片机：这些工具就是"外设驱动"，
每个工具封装一个具体的数据库操作，LLM 通过 Tool Calling 协议调用它们。
"""

import json
import os
from pathlib import Path
from typing import Optional

from src.ai.tools import Tool, ToolParam, ToolRegistry
from src.engine.knowledge_base import KnowledgeBase

# 专家领域知识缓存
_EXPERT_CONTEXT_CACHE = None

def _load_expert_context() -> dict:
    """加载专家领域知识"""
    global _EXPERT_CONTEXT_CACHE
    if _EXPERT_CONTEXT_CACHE is None:
        ctx_path = Path(__file__).resolve().parent.parent.parent / "data" / "seed" / "expert_context.json"
        if ctx_path.exists():
            with open(ctx_path, "r", encoding="utf-8") as f:
                _EXPERT_CONTEXT_CACHE = json.load(f)
        else:
            _EXPERT_CONTEXT_CACHE = {}
    return _EXPERT_CONTEXT_CACHE


def register_diagnostic_tools(
    registry: ToolRegistry,
    kb: Optional[KnowledgeBase] = None,
) -> None:
    """
    把所有诊断工具注册到 ToolRegistry

    Args:
        registry: 工具注册表
        kb: 知识库实例（可选，不传则自动创建）
    """
    if kb is None:
        kb = KnowledgeBase()

    # ── 工具 1: lookup_code ──
    registry.register(Tool(
        name="lookup_code",
        description=(
            "查询 OBD-II 故障码的详细信息，包括描述、严重程度、"
            "常见原因、诊断步骤、相关故障码。"
            "当用户输入一个故障码时，应首先调用此工具。"
        ),
        parameters=[
            ToolParam(
                name="code",
                type="string",
                description="故障码，如 P0300、B1420、EV-BMS-001",
                required=True,
            ),
        ],
        function=lambda code: _lookup_code(kb, code),
    ))

    # ── 工具 2: search_by_symptom ──
    registry.register(Tool(
        name="search_by_symptom",
        description=(
            "根据症状关键词搜索可能的故障码。"
            "当用户描述故障现象（如'冷车启动抖动'、'充电中断'）但不知道故障码时使用。"
            "搜索范围包括故障码描述和已记录的症状。"
        ),
        parameters=[
            ToolParam(
                name="keyword",
                type="string",
                description="症状关键词，如'抖动'、'无法充电'、'异响'",
                required=True,
            ),
        ],
        function=lambda keyword: _search_by_symptom(kb, keyword),
    ))

    # ── 工具 3: get_vehicle_info ──
    registry.register(Tool(
        name="get_vehicle_info",
        description=(
            "查询指定车型的基本信息、常见故障码和已知通病。"
            "当用户提到具体车型（如'比亚迪秦PLUS'、'特斯拉Model 3'）时使用。"
        ),
        parameters=[
            ToolParam(
                name="make",
                type="string",
                description="品牌名，如'比亚迪'、'特斯拉'",
                required=True,
            ),
            ToolParam(
                name="model",
                type="string",
                description="车型名，如'秦PLUS EV'、'Model 3'",
                required=True,
            ),
        ],
        function=lambda make, model: _get_vehicle_info(kb, make, model),
    ))

    # ── 工具 4: get_related_codes ──
    registry.register(Tool(
        name="get_related_codes",
        description=(
            "获取与指定故障码相关的其他故障码。"
            "当需要了解一个故障码可能引发的关联故障时使用。"
        ),
        parameters=[
            ToolParam(
                name="code",
                type="string",
                description="故障码，如 P0300",
                required=True,
            ),
        ],
        function=lambda code: _get_related_codes(kb, code),
    ))

    # ── 工具 5: get_diagnostic_steps ──
    registry.register(Tool(
        name="get_diagnostic_steps",
        description=(
            "获取指定故障码的标准诊断步骤（来自维修手册）。"
            "当需要给出具体排查流程时使用。"
        ),
        parameters=[
            ToolParam(
                name="code",
                type="string",
                description="故障码，如 P0300",
                required=True,
            ),
        ],
        function=lambda code: _get_diagnostic_steps(kb, code),
    ))

    # ── 工具 6: get_wiring_info ──
    registry.register(Tool(
        name="get_wiring_info",
        description=(
            "获取故障码相关系统的电路和针脚信息。"
            "当技师需要检查线路、传感器连接时使用。"
            "注意：此信息基于知识库中的通用数据，具体车型请参考维修手册。"
        ),
        parameters=[
            ToolParam(
                name="code",
                type="string",
                description="故障码",
                required=True,
            ),
        ],
        function=lambda code: _get_wiring_info(kb, code),
    ))

    # ── 工具 7: record_symptom ──
    registry.register(Tool(
        name="record_symptom",
        description=(
            "记录技师观察到的故障现象，便于后续分析和统计。"
            "在对话过程中，每当技师描述新的症状时调用此工具。"
        ),
        parameters=[
            ToolParam(
                name="code",
                type="string",
                description="当前诊断的故障码",
                required=True,
            ),
            ToolParam(
                name="symptom",
                type="string",
                description="技师描述的现象，如'冷车启动时抖动明显'",
                required=True,
            ),
        ],
        function=lambda code, symptom: _record_symptom(kb, code, symptom),
    ))

    # ── 工具 8: get_common_fixes ──
    registry.register(Tool(
        name="get_common_fixes",
        description=(
            "获取故障码对应的常见修复方案和维修案例。"
            "当需要给出具体的维修建议时使用。"
        ),
        parameters=[
            ToolParam(
                name="code",
                type="string",
                description="故障码",
                required=True,
            ),
        ],
        function=lambda code: _get_common_fixes(kb, code),
    ))

    # ── 工具 9: search_codes_by_system ──
    registry.register(Tool(
        name="search_codes_by_system",
        description=(
            "按系统分类浏览故障码。"
            "可选系统：P(动力总成)、B(车身)、C(底盘)、U(网络通讯)、"
            "EV-BMS(电池管理)、EV-MOTOR(电机)、EV-OBC(车载充电)等。"
        ),
        parameters=[
            ToolParam(
                name="system",
                type="string",
                description="系统代码，如 P、B、C、U、EV-BMS",
                required=True,
                enum=["P", "B", "C", "U", "EV-BMS", "EV-MOTOR", "EV-OBC",
                      "EV-DCDC", "EV-THERMAL", "EV-HV", "EV-REGEN", "EV-VCU",
                      "EV-CHARGE", "EV-COMM"],
            ),
        ],
        function=lambda system: _search_codes_by_system(kb, system),
    ))

    # ── 工具 10: get_expert_context ──
    registry.register(Tool(
        name="get_expert_context",
        description=(
            "获取指定专家领域的诊断知识和注意事项。"
            "当诊断涉及 BMS（电池管理）、电机驱动、热管理等专业系统时调用。"
            "返回该领域的诊断要点、常见故障模式和安全提醒。"
        ),
        parameters=[
            ToolParam(
                name="expert",
                type="string",
                description="专家领域",
                required=True,
                enum=["battery", "motor", "vcu", "general"],
            ),
        ],
        function=lambda expert: _get_expert_context(expert),
    ))


# ═══════════════════════════════════════════════════════════════
# 工具实现函数 — 每个函数对应一个工具的实际逻辑
# 输入: 来自 LLM 的参数
# 输出: JSON 字符串（LLM 能理解的格式）
# ═══════════════════════════════════════════════════════════════


def _lookup_code(kb: KnowledgeBase, code: str) -> str:
    """工具1: 查询故障码详情"""
    code = code.strip().upper()
    result = kb.lookup(code)

    if result is None:
        return json.dumps({
            "found": False,
            "code": code,
            "message": f"知识库中未找到故障码 {code}。可能是厂商自定义码或输入有误。"
        }, ensure_ascii=False)

    return json.dumps({
        "found": True,
        "code": result["code"],
        "system": result.get("system", ""),
        "description": result.get("description", ""),
        "detail": result.get("detail", ""),
        "severity": result.get("severity", "medium"),
        "common_causes": result.get("common_causes", []),
        "diagnostic_steps": result.get("diagnostic_steps", []),
        "related_codes": result.get("related_codes", []),
        "symptoms": result.get("symptoms", []),
    }, ensure_ascii=False, indent=2)


def _search_by_symptom(kb: KnowledgeBase, keyword: str) -> str:
    """工具2: 按症状搜索故障码"""
    keyword = keyword.strip()
    if not keyword:
        return json.dumps({"error": "关键词不能为空"}, ensure_ascii=False)

    # 症状关键词 → 技术术语映射
    # 用户描述的症状和数据库中的故障码描述往往用词不同
    # 例如：用户说"抖动"，数据库里是"缺火"
    _SYMPTOM_MAP = {
        "抖动": "缺火",
        "车身抖动": "缺火",
        "发动机抖动": "缺火",
        "启动抖动": "缺火",
        "怠速抖动": "缺火",
        "异响": "异响",
        "无法充电": "充电",
        "充不进电": "充电",
        "动力不足": "动力",
        "加速无力": "加速",
        "启动困难": "启动",
        "无法启动": "启动",
        "故障灯亮": "故障灯",
        "报警": "故障",
    }

    # 先尝试精确映射
    for symptom, tech_term in _SYMPTOM_MAP.items():
        if symptom in keyword:
            keyword = tech_term
            break

    results = kb.search(keyword, limit=30)

    if not results:
        return json.dumps({
            "found": False,
            "keyword": keyword,
            "message": f"未找到与'{keyword}'相关的故障码。请尝试更具体的关键词。"
        }, ensure_ascii=False)

    codes = []
    for r in results:
        codes.append({
            "code": r["code"],
            "description": r.get("description", ""),
            "system": r.get("system", ""),
            "severity": r.get("severity", "medium"),
        })

    return json.dumps({
        "found": True,
        "keyword": keyword,
        "count": len(codes),
        "results": codes,
    }, ensure_ascii=False, indent=2)


def _get_vehicle_info(kb: KnowledgeBase, make: str, model: str) -> str:
    """工具3: 查询车型信息"""
    make = make.strip()
    model = model.strip()

    info = kb.get_vehicle_info(make, model)
    if info is None:
        # 尝试只查品牌
        models = kb.get_models_by_make(make)
        if models:
            model_list = [m["model"] for m in models]
            return json.dumps({
                "found": False,
                "message": f"未找到'{make} {model}'。{make}在库中的车型: {', '.join(model_list)}",
                "available_models": model_list,
            }, ensure_ascii=False)
        return json.dumps({
            "found": False,
            "message": f"未找到品牌'{make}'的信息。"
        }, ensure_ascii=False)

    return json.dumps({
        "found": True,
        "make": info.get("make", ""),
        "model": info.get("model", ""),
        "year_range": f"{info.get('year_start', '?')}-{info.get('year_end', '在产')}",
        "powertrain": info.get("powertrain", ""),
        "battery_type": info.get("battery_type", ""),
        "motor_type": info.get("motor_type", ""),
        "common_codes": info.get("common_codes", []),
        "known_issues": info.get("known_issues", []),
        "notes": info.get("notes", ""),
    }, ensure_ascii=False, indent=2)


def _get_related_codes(kb: KnowledgeBase, code: str) -> str:
    """工具4: 获取相关故障码"""
    code = code.strip().upper()
    result = kb.lookup(code)

    if result is None:
        return json.dumps({
            "error": f"故障码 {code} 不存在于知识库中"
        }, ensure_ascii=False)

    related = result.get("related_codes", [])
    if not related:
        return json.dumps({
            "code": code,
            "related_codes": [],
            "message": f"{code} 没有已知的关联故障码。"
        }, ensure_ascii=False)

    # 查询每个关联码的基本信息
    related_details = []
    for rc in related[:10]:  # 最多返回 10 个
        rc_info = kb.lookup(rc.strip())
        if rc_info:
            related_details.append({
                "code": rc_info["code"],
                "description": rc_info.get("description", ""),
                "severity": rc_info.get("severity", "medium"),
            })
        else:
            related_details.append({"code": rc, "description": "未收录", "severity": "unknown"})

    return json.dumps({
        "code": code,
        "related_count": len(related_details),
        "related_codes": related_details,
    }, ensure_ascii=False, indent=2)


def _get_diagnostic_steps(kb: KnowledgeBase, code: str) -> str:
    """工具5: 获取标准诊断步骤"""
    code = code.strip().upper()
    result = kb.lookup(code)

    if result is None:
        return json.dumps({
            "error": f"故障码 {code} 不存在于知识库中"
        }, ensure_ascii=False)

    steps = result.get("diagnostic_steps", [])
    if not steps:
        return json.dumps({
            "code": code,
            "diagnostic_steps": [],
            "message": f"{code} 没有标准诊断步骤记录。"
        }, ensure_ascii=False)

    return json.dumps({
        "code": code,
        "description": result.get("description", ""),
        "severity": result.get("severity", "medium"),
        "diagnostic_steps": steps,
    }, ensure_ascii=False, indent=2)


def _get_wiring_info(kb: KnowledgeBase, code: str) -> str:
    """
    工具6: 获取电路/针脚信息
    注意：当前知识库没有专门的电路信息表，
    这里基于故障码的 system 字段给出通用提示。
    后续可扩展 wiring_info 表。
    """
    code = code.strip().upper()
    result = kb.lookup(code)

    if result is None:
        return json.dumps({
            "error": f"故障码 {code} 不存在于知识库中"
        }, ensure_ascii=False)

    system = result.get("system", "")
    description = result.get("description", "")

    # 基于系统类型给出通用电路信息提示
    wiring_hints = {
        "P": "动力总成系统 — 检查 ECM/PCM 线束、传感器供电(5V参考)、接地线路",
        "B": "车身系统 — 检查 BCM 线束、CAN 总线连接、车身接地",
        "C": "底盘系统 — 检查 ABS/ESP 模块线束、轮速传感器线路",
        "U": "网络通讯 — 检查 CAN 总线终端电阻、OBD-II 诊断口针脚",
    }

    ev_wiring_hints = {
        "EV-BMS": "BMS — 检查电池管理单元线束、电压采集线、温度传感器线路",
        "EV-MOTOR": "电机控制器 — 检查三相线缆、旋变传感器、温度传感器",
        "EV-OBC": "车载充电机 — 检查 AC 输入线缆、DC 输出线缆、CP/CC 信号线",
        "EV-DCDC": "DC-DC — 检查高压输入线缆、低压输出线缆、使能信号线",
        "EV-THERMAL": "热管理 — 检查水泵线束、温度传感器、电子风扇线路",
        "EV-HV": "高压系统 — 检查高压互锁回路、预充电路、高压继电器",
        "EV-VCU": "整车控制器 — 检查 VCU 供电/接地、整车 CAN 总线、上下电硬线信号",
    }

    hint = ev_wiring_hints.get(system) or wiring_hints.get(system[0] if system else "", "通用系统")

    return json.dumps({
        "code": code,
        "system": system,
        "description": description,
        "wiring_hint": hint,
        "note": "以上为通用提示。具体针脚定义和电路图请参考车型维修手册。"
    }, ensure_ascii=False, indent=2)


def _record_symptom(kb: KnowledgeBase, code: str, symptom: str) -> str:
    """工具7: 记录技师观察到的现象"""
    code = code.strip().upper()
    symptom = symptom.strip()

    if not symptom:
        return json.dumps({"error": "症状描述不能为空"}, ensure_ascii=False)

    success = kb.record_symptoms(code, symptom)

    if success:
        # 获取已记录的所有症状
        all_symptoms = kb.get_symptoms(code)
        return json.dumps({
            "success": True,
            "code": code,
            "recorded": symptom,
            "total_symptoms": len(all_symptoms),
            "all_symptoms": all_symptoms,
        }, ensure_ascii=False, indent=2)
    else:
        return json.dumps({
            "success": False,
            "message": f"记录失败。故障码 {code} 可能不存在于知识库中。"
        }, ensure_ascii=False)


def _get_common_fixes(kb: KnowledgeBase, code: str) -> str:
    """工具8: 获取常见修复方案"""
    code = code.strip().upper()
    result = kb.lookup(code)

    if result is None:
        return json.dumps({
            "error": f"故障码 {code} 不存在于知识库中"
        }, ensure_ascii=False)

    causes = result.get("common_causes", [])
    steps = result.get("diagnostic_steps", [])
    severity = result.get("severity", "medium")

    # 综合常见原因和诊断步骤，生成修复建议
    fixes = []
    for i, cause in enumerate(causes):
        fix = {"issue": cause}
        if i < len(steps):
            fix["check_step"] = steps[i]
        fixes.append(fix)

    return json.dumps({
        "code": code,
        "description": result.get("description", ""),
        "severity": severity,
        "common_causes": causes,
        "diagnostic_steps": steps,
        "fixes_summary": fixes,
        "note": "以上信息来自知识库。实际维修请结合车辆具体状况判断。"
    }, ensure_ascii=False, indent=2)


def _search_codes_by_system(kb: KnowledgeBase, system: str) -> str:
    """工具9: 按系统分类浏览故障码"""
    system = system.strip().upper()

    # 系统名称映射
    system_names = {
        "P": "动力总成 (Powertrain)",
        "B": "车身 (Body)",
        "C": "底盘 (Chassis)",
        "U": "网络通讯 (Network)",
        "EV-BMS": "电池管理系统",
        "EV-MOTOR": "电机控制系统",
        "EV-OBC": "车载充电机",
        "EV-DCDC": "DC-DC 变换器",
        "EV-THERMAL": "热管理系统",
        "EV-HV": "高压系统",
        "EV-REGEN": "再生制动系统",
        "EV-VCU": "整车控制器（电控）",
        "EV-CHARGE": "充电系统",
        "EV-COMM": "新能源网络通讯",
    }

    # 系统代码到数据库system字段的映射
    system_to_db = {
        "P": "Powertrain",
        "B": "Body",
        "C": "Chassis",
        "U": "Network",
    }

    # 获取对应的数据库system名称
    db_system = system_to_db.get(system, system)

    # 直接用 SQL 查询，按 code 前缀或 system 字段精确匹配
    # 这样比 kb.search() 模糊搜索更可靠
    try:
        if system.startswith("EV-"):
            # EV 系统码：按 code 前缀匹配（如 EV-BMS-001）
            results = kb.db.execute_query(
                "SELECT code, description, severity FROM obd_codes WHERE code LIKE ? LIMIT 15",
                (f"{system}-%",)
            )
        else:
            # 传统系统码：按 code 首字母匹配（如 P0300）
            results = kb.db.execute_query(
                "SELECT code, description, severity FROM obd_codes WHERE code LIKE ? LIMIT 15",
                (f"{system[0]}%",)
            )
    except Exception:
        # 降级到旧方式
        results = kb.search(db_system, limit=50)
        filtered = []
        for r in results:
            r_system = (r.get("system") or "").upper()
            r_code = (r.get("code") or "").upper()
            if r_system == db_system.upper() or r_system == system or r_code.startswith(system):
                filtered.append(r)
        results = filtered[:15]

    if not results:
        return json.dumps({
            "found": False,
            "system": system,
            "system_name": system_names.get(system, system),
            "message": f"未找到系统'{system}'的故障码。"
        }, ensure_ascii=False)

    codes = []
    for r in results:
        codes.append({
            "code": r["code"],
            "description": r.get("description", ""),
            "severity": r.get("severity", "medium"),
        })

    return json.dumps({
        "found": True,
        "system": system,
        "system_name": system_names.get(system, system),
        "count": len(codes),
        "codes": codes,
    }, ensure_ascii=False, indent=2)


def _get_expert_context(expert: str) -> str:
    """工具10: 获取专家领域知识"""
    expert = expert.strip().lower()
    ctx = _load_expert_context()

    if expert not in ctx:
        available = list(ctx.keys())
        return json.dumps({
            "error": f"未知专家领域: {expert}",
            "available": available,
        }, ensure_ascii=False)

    profile = ctx[expert]
    return json.dumps({
        "expert": expert,
        "name": profile["name"],
        "context": profile["context"],
    }, ensure_ascii=False, indent=2)
