# -*- coding: utf-8 -*-
"""
确定性生成 EV 系统码的详细诊断信息（纯模板，无 LLM 调用）

背景：
    batch_enhance_codes.py 的 Ollama 批量增强管线在本环境卡死（0 进展）。
    本脚本用 8 个系统（BMS/MOTOR/OBC/DCDC/THERMAL/HV/REGEN/VCU）的领域模板，
    结合每条码的 description 与 severity，程序化生成
    detail / common_causes / diagnostic_steps / symptoms，
    回填数据库中 detail 为空的 EV 码。

约束：
    - 只处理 DB 中 detail 为空的 EV 码（幂等，重跑不会覆盖已有详情）
    - 不修改已有 AI 生成的 146 条详情
    - detail 中文 >= 100 字；common_causes >= 5；diagnostic_steps >= 5；symptoms >= 3

用法:
    python scripts/synthesize_ev_details.py [--dry-run]
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "obd_codes.db"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

# 各系统领域模板
# detail 模板：系统原理 + 码含义 + 影响 + 严重度安全提示
SYSTEM_TEMPLATES = {
    "EV-BMS": {
        "name": "电池管理系统（BMS）",
        "principle": "电池管理系统（BMS）负责实时采集各单体电池的电压、电流与温度，"
                     "对电池组进行均衡、保护与热管理，是保障动力电池安全与寿命的核心控制单元。",
        "impact": {
            "critical": "可能引发热失控或高压安全事故",
            "high": "可能导致电池性能骤降或充放电异常",
            "medium": "可能导致电池寿命缩短或效率下降",
            "low": "影响较小，但长期存在可能加速电池老化",
        },
        "causes": [
            "单体采样线束连接器松动或氧化",
            "采样通道芯片损坏",
            "电池模块间连接虚接",
            "BMS从控板供电异常",
            "线束磨损导致开路或短路",
            "BMS软件标定或版本异常",
        ],
        "steps": [
            "第一步：断开工况并执行下高压安全操作，确认高压互锁已断开。",
            "第二步：连接诊断仪读取相关数据流，核对采样值与实测值是否一致。",
            "第三步：检查对应采样线束与连接器，测量导通性并排查开路或短路。",
            "第四步：检查BMS从控板供电与接地，确认无欠压或虚接。",
            "第五步：核对BMS软件版本，必要时升级或重新标定。",
            "第六步：复测相关数据流，确认故障码清除且数据恢复正常。",
        ],
        "symptoms": [
            "仪表提示电池系统故障报警",
            "充电速度明显变慢或中断",
            "车辆动力受限或无法上高压",
            "电池续航里程异常下降",
        ],
    },
    "EV-MOTOR": {
        "name": "电机驱动系统",
        "principle": "电机驱动系统由电机控制器（MCU）、旋变传感器与驱动电机组成，"
                     "负责将高压直流电逆变为三相交流电驱动车辆，并实时监测电机转速、扭矩与绕组温度。",
        "impact": {
            "critical": "可能导致动力完全中断或驱动部件损坏",
            "high": "可能导致动力明显下降或高温保护",
            "medium": "可能导致扭矩输出波动或效率下降",
            "low": "影响较小，但持续存在可能加剧部件磨损",
        },
        "causes": [
            "电机控制器功率模块老化",
            "旋变传感器线束接触不良",
            "三相动力线束端子氧化或松动",
            "电机控制器供电异常",
            "软件标定或版本错误",
            "电机绕组局部绝缘下降",
        ],
        "steps": [
            "第一步：确认车辆安全停驶并断开高压，执行下高压操作。",
            "第二步：读取MCU数据流，核对电机转速、三相电流与母线电压。",
            "第三步：检查旋变传感器及其线束，测量信号幅值是否正常。",
            "第四步：检查三相动力线束连接与相间绝缘。",
            "第五步：核对MCU软件版本并重新标定。",
            "第六步：试运行复测，确认故障码不再出现。",
        ],
        "symptoms": [
            "仪表提示驱动系统故障",
            "加速无力或动力中断",
            "车辆报过温或过流告警",
            "行驶中出现顿挫感",
        ],
    },
    "EV-OBC": {
        "name": "车载充电机（OBC）",
        "principle": "车载充电机（OBC）将交流电网电能转换为高压直流电能，"
                     "在充电过程中与电池管理系统配合完成恒流恒压控制，并对输入输出进行绝缘与过温保护。",
        "impact": {
            "critical": "可能导致充电失效或高压安全隐患",
            "high": "可能导致充电中断或充电机过温",
            "medium": "可能导致充电功率下降或充电时间延长",
            "low": "影响较小，可能表现为偶发充电异常",
        },
        "causes": [
            "充电机主控板供电异常",
            "交流输入端子接触不良",
            "充电枪与插座连接异常",
            "OBC散热风扇故障导致过温",
            "与BMS通信线路异常",
            "软件版本不匹配",
        ],
        "steps": [
            "第一步：确认充电桩与车辆连接可靠，检查充电枪锁止状态。",
            "第二步：读取OBC与BMS数据流，核对充电电压、电流与请求信号。",
            "第三步：检查交流输入端子与保险，测量输入电压是否正常。",
            "第四步：检查OBC散热风扇与风道，确认无过温现象。",
            "第五步：核对软件版本并升级或复位。",
            "第六步：重新插枪充电测试，确认故障排除。",
        ],
        "symptoms": [
            "无法启动充电或充电中断",
            "充电功率明显下降",
            "充电过程中发热异常",
            "充电口指示灯异常",
        ],
    },
    "EV-DCDC": {
        "name": "DC-DC变换器",
        "principle": "DC-DC变换器将动力电池的高压直流电转换为低压直流电，"
                     "为12V蓄电池及低压用电设备供电，并根据负载需求实时调节输出电压与电流。",
        "impact": {
            "critical": "可能导致低压系统失电，车辆无法启动",
            "high": "可能导致低压电压波动或用电设备异常",
            "medium": "可能导致充电效率下降或电压不稳",
            "low": "影响较小，多为轻微效率损失",
        },
        "causes": [
            "DC-DC主开关管损坏",
            "输出滤波电容老化",
            "低压侧线束或保险异常",
            "输入高压连接器接触不良",
            "控制板供电或通信异常",
            "软件保护阈值误触发",
        ],
        "steps": [
            "第一步：确认低压蓄电池电压正常，断开高压并执行下高压操作。",
            "第二步：读取DC-DC数据流，核对输出电压、电流与转换效率。",
            "第三步：检查低压侧保险、线束与蓄电池接线。",
            "第四步：检查高压输入连接器与接地是否牢靠。",
            "第五步：核对软件版本并复位或升级。",
            "第六步：上电复测，确认输出电压稳定且故障码清除。",
        ],
        "symptoms": [
            "12V系统电压波动",
            "启动困难或用电设备异常",
            "仪表提示充电系统故障",
            "低压蓄电池亏电加快",
        ],
    },
    "EV-THERMAL": {
        "name": "热管理系统",
        "principle": "热管理系统通过冷却液循环、电子风扇与PTC加热器对电池和电驱进行温度控制，"
                     "维持整车处于最佳工作温度区间，防止过热或低温性能衰减。",
        "impact": {
            "critical": "可能导致电池过热引发安全风险",
            "high": "可能导致动力降额或电池温度持续偏高",
            "medium": "可能导致温控效率下降或温差增大",
            "low": "影响较小，多为轻微温控偏差",
        },
        "causes": [
            "冷却液液位过低或缺失",
            "水泵故障或空转",
            "电子风扇卡滞或转速异常",
            "冷却管路堵塞或排气不足",
            "温度传感器漂移",
            "热管理控制器供电或通信异常",
        ],
        "steps": [
            "第一步：检查冷却液液位与外观，确认无泄漏。",
            "第二步：读取热管理数据流，核对各回路温度、流量与水泵转速。",
            "第三步：检查水泵、电子风扇供电与PWM控制信号。",
            "第四步：检查管路是否堵塞、排气是否充分。",
            "第五步：核对温度传感器读数与控制器软件版本。",
            "第六步：运行温度循环测试，确认温控恢复正常。",
        ],
        "symptoms": [
            "电池或电机温度偏高",
            "空调制冷或制热效果变差",
            "仪表提示热管理故障",
            "行驶中动力降额",
        ],
    },
    "EV-HV": {
        "name": "高压系统",
        "principle": "高压系统涵盖动力电池、高压配电箱、高压接触器与绝缘监测等部件，"
                     "负责高压电能的分配、通断与安全隔离，是整车电气安全的关键回路。",
        "impact": {
            "critical": "存在触电或热失控风险，必须立即停驶",
            "high": "可能导致高压系统断电或无法上高压",
            "medium": "可能导致绝缘性能下降或偶发告警",
            "low": "影响较小，多为监测类告警",
        },
        "causes": [
            "高压线束绝缘破损或进水",
            "连接器未锁紧或端子氧化",
            "高压接触器触点烧蚀",
            "绝缘监测模块故障",
            "维修开关状态异常",
            "高压部件爬电或积污",
        ],
        "steps": [
            "第一步：立即停止使用车辆，严禁带电操作，确认高压互锁断开。",
            "第二步：使用绝缘测试仪分段测量高压回路对地绝缘电阻。",
            "第三步：检查高压连接器锁止、端子与线束绝缘层外观。",
            "第四步：检查高压接触器吸合与断开是否正常。",
            "第五步：检查绝缘监测模块供电与自检状态。",
            "第六步：排除故障后复测绝缘与系统上电流程。",
        ],
        "symptoms": [
            "仪表提示高压系统故障",
            "车辆无法上高压或行驶",
            "高压互锁报警",
            "充电被禁止",
        ],
    },
    "EV-REGEN": {
        "name": "再生制动系统",
        "principle": "再生制动系统在减速或制动时让驱动电机反向发电，将动能回收为电能回充电池，"
                     "并与液压制动、ABS/ESP协调工作以保证制动稳定性。",
        "impact": {
            "critical": "可能导致制动协调失效，影响行车安全",
            "high": "可能导致回收功能失效或制动异常",
            "medium": "可能导致回收功率受限或效率下降",
            "low": "影响较小，多为轻微回收波动",
        },
        "causes": [
            "制动踏板位置传感器异常",
            "再生制动与ESP协调信号丢失",
            "能量回收电机控制异常",
            "相关CAN通信丢帧",
            "电池SOC过高限制回收",
            "软件标定异常",
        ],
        "steps": [
            "第一步：确认车辆安全停驶，检查制动踏板传感器与开关状态。",
            "第二步：读取能量回收数据流，核对回收扭矩请求与实际值。",
            "第三步：检查与ESP/ABS协调的CAN报文与信号。",
            "第四步：检查电机控制器在回收工况下的工作状态。",
            "第五步：核对软件版本并复位或升级。",
            "第六步：路试验证回收功能恢复且制动稳定。",
        ],
        "symptoms": [
            "制动时回收介入不明显",
            "能量回收时车辆顿挫",
            "仪表提示制动系统异常",
            "续航里程下降明显",
        ],
    },
    "EV-VCU": {
        "name": "整车控制器（VCU）",
        "principle": "整车控制器（VCU）是新能源汽车的核心控制大脑，负责整车上/下电管理、"
                     "扭矩需求仲裁、挡位控制、整车网络通信与故障降级策略，"
                     "协调 BMS、电机控制器及各低压控制单元协同工作。",
        "impact": {
            "critical": "可能导致整车上电失败或高压安全异常",
            "high": "可能导致车辆动力受限或无法正常行驶",
            "medium": "可能导致部分功能异常或控制协调问题",
            "low": "影响较小，多为偶发告警或降级表现",
        },
        "causes": [
            "VCU 控制板供电异常",
            "整车 CAN 网络故障或报文丢失",
            "VCU 与相关控制器通信中断",
            "传感器信号线束接触不良",
            "VCU 软件版本或标定异常",
            "整车继电器或保险故障",
        ],
        "steps": [
            "第一步：确认车辆安全停驶，断开低压供电后重新上电观察故障是否重现。",
            "第二步：读取 VCU 相关数据流，核对上/下电状态、挡位与扭矩请求信号。",
            "第三步：检查整车 CAN 网络终端电阻与通信报文，确认无丢帧或超时。",
            "第四步：检查 VCU 供电、接地与相关硬线信号连接。",
            "第五步：核对 VCU 软件版本与标定参数，必要时升级或复位。",
            "第六步：复测上下电流程与整车控制逻辑，确认故障码清除。",
        ],
        "symptoms": [
            "仪表提示整车系统故障",
            "车辆无法上电或启动",
            "挡位无响应或切换异常",
            "行驶中出现动力受限告警",
        ],
    },
}

SEVERITY_SAFETY = {
    "critical": "该故障涉及高压系统，存在触电与热失控风险，务必在专业指导下处理。",
    "high": "该故障对行车安全影响较大，建议尽快安排检修。",
    "medium": "建议在方便时安排检修，避免故障影响扩大。",
    "low": "可结合常规保养一并排查处理。",
}


def build_detail(system, code, description, severity):
    """生成 detail：系统原理 + 码含义 + 影响 + 安全提示"""
    tpl = SYSTEM_TEMPLATES[system]
    impact = tpl["impact"].get(severity, tpl["impact"]["medium"])
    safety = SEVERITY_SAFETY.get(severity, SEVERITY_SAFETY["medium"])
    return (
        f"{tpl['principle']}"
        f"{code}故障码表示「{description}」这一异常状态，通常由相关组件老化、"
        f"线路连接不良或控制逻辑错误引起；若不及时处理，{impact}。{safety}"
    )


def build_common_causes(system, description):
    """生成 common_causes：系统通用原因池"""
    return list(SYSTEM_TEMPLATES[system]["causes"])


def build_diagnostic_steps(system, description):
    """生成 diagnostic_steps：系统通用诊断流程"""
    return list(SYSTEM_TEMPLATES[system]["steps"])


def build_symptoms(system, description):
    """生成 symptoms：系统通用症状"""
    return list(SYSTEM_TEMPLATES[system]["symptoms"])


def main():
    import argparse
    parser = argparse.ArgumentParser(description="确定性生成 EV 系统码详细诊断信息（纯模板）")
    parser.add_argument("--dry-run", action="store_true", help="只统计不写入")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"[ERROR] 数据库不存在: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT code, system, description, severity FROM obd_codes "
        "WHERE code LIKE 'EV-%' AND (detail IS NULL OR detail = '') "
        "ORDER BY code"
    ).fetchall()

    if not rows:
        print("[OK] 没有需要补充详情的 EV 码")
        conn.close()
        return

    print(f"[PLAN] 待处理 {len(rows)} 条 EV 码")
    if args.dry_run:
        for r in rows[:10]:
            print(f"  {r['code']}: {r['description'][:30]}")
        conn.close()
        return

    updated = 0
    for r in rows:
        system = r["system"]
        code = r["code"]
        description = r["description"] or code
        severity = r["severity"] or "medium"

        detail = build_detail(system, code, description, severity)
        causes = build_common_causes(system, description)
        steps = build_diagnostic_steps(system, description)
        symptoms = build_symptoms(system, description)

        if len(detail) < 100:
            print(f"  [WARN] {code} detail 过短 ({len(detail)} 字)")
        conn.execute(
            "UPDATE obd_codes SET detail = ?, common_causes = ?, "
            "diagnostic_steps = ?, symptoms = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE code = ?",
            (
                detail,
                json.dumps(causes, ensure_ascii=False),
                json.dumps(steps, ensure_ascii=False),
                json.dumps(symptoms, ensure_ascii=False),
                code,
            ),
        )
        updated += 1

    conn.commit()

    # 汇总
    summary = {}
    for r in conn.execute(
        "SELECT system, COUNT(*) AS total, "
        "SUM(CASE WHEN detail IS NULL OR detail = '' THEN 1 ELSE 0 END) AS empty "
        "FROM obd_codes WHERE code LIKE 'EV-%' GROUP BY system ORDER BY system"
    ):
        summary[r["system"]] = (r["total"], r["empty"])

    total = conn.execute("SELECT COUNT(*) FROM obd_codes WHERE code LIKE 'EV-%'").fetchone()[0]
    empty = conn.execute(
        "SELECT COUNT(*) FROM obd_codes WHERE code LIKE 'EV-%' "
        "AND (detail IS NULL OR detail = '')"
    ).fetchone()[0]
    conn.close()

    print(f"[OK] 更新 {updated} 条")
    for sys_name in sorted(summary):
        t, e = summary[sys_name]
        print(f"     {sys_name}: {t - e}/{t} 有详情")
    print(f"[OK] EV 合计: {total - empty}/{total} 有详情")


if __name__ == "__main__":
    main()
