# -*- coding: utf-8 -*-
"""
生成 EV 系统故障码种子数据 ev_system_codes.csv

覆盖 7 个新能源系统（与 expert_context 路由 / diagnostic_tools 系统枚举对齐）：
    EV-BMS / EV-MOTOR / EV-OBC / EV-DCDC / EV-THERMAL / EV-HV / EV-REGEN

每条含 code/system/code_type/description/severity/related_codes，
detail/common_causes/diagnostic_steps/symptoms 留空，由 AI 批量增强（batch_enhance_codes.py）填充。

用法:
    python scripts/generate_ev_system_codes.py
"""

import csv
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = PROJECT_ROOT / "data" / "seed" / "ev_system_codes.csv"

HEADER = ["code", "system", "code_type", "description", "detail", "severity",
          "common_causes", "diagnostic_steps", "related_codes", "symptoms"]

# (system, [(description, severity, related)])
# related 用代码中的 NNN 表示同系统内引用
EV_BMS = "EV-BMS"
EV_MOTOR = "EV-MOTOR"
EV_OBC = "EV-OBC"
EV_DCDC = "EV-DCDC"
EV_THERMAL = "EV-THERMAL"
EV_HV = "EV-HV"
EV_REGEN = "EV-REGEN"

DATA = {
    EV_BMS: [
        ("电池采样电压异常", "high", []),
        ("单体电池电压不均衡", "medium", []),
        ("电池温度传感器故障", "high", []),
        ("电池包绝缘电阻过低", "critical", []),
        ("BMS 主控通信中断", "high", []),
        ("电池 SOC 估算异常", "medium", []),
        ("电池 SOH 衰减异常", "medium", []),
        ("预充电接触器无法闭合", "high", []),
        ("主接触器粘连", "critical", []),
        ("BMS 高压互锁回路断开", "critical", []),
        ("电池包热失控预警", "critical", []),
        ("电池包气压异常升高", "high", []),
        ("BMS 唤醒失败", "medium", []),
        ("电池采样线束开路", "high", []),
        ("单体电压采样漂移", "medium", []),
        ("电池均衡功能失效", "low", []),
        ("BMS 继电器驱动故障", "high", []),
        ("电池包烟感报警", "critical", []),
        ("BMS 固件版本不匹配", "low", []),
        ("电池包电流传感器异常", "high", []),
        ("BMS 冷启动通信超时", "medium", []),
        ("电池包端子温度过高", "high", []),
    ],
    EV_MOTOR: [
        ("电机控制器过温", "high", []),
        ("电机温度传感器故障", "medium", []),
        ("旋变传感器信号丢失", "critical", []),
        ("电机三相电流不平衡", "high", []),
        ("电机控制器母线电压过高", "critical", []),
        ("电机过速保护触发", "high", []),
        ("IGBT 模块故障", "critical", []),
        ("电机控制器 CAN 通信中断", "high", []),
        ("电机绝缘电阻过低", "critical", []),
        ("电机堵转保护", "high", []),
        ("电机控制器驱动电压异常", "high", []),
        ("旋变信号偏差过大", "medium", []),
        ("电机相电流传感器故障", "high", []),
        ("电机控制器自检失败", "medium", []),
        ("电机冷却液泄漏", "high", []),
        ("电机控制器低压供电异常", "medium", []),
        ("电机反电动势监测异常", "medium", []),
        ("MCU 参数标定错误", "low", []),
        ("电机控制器软件复位", "low", []),
        ("电机扭矩输出限制", "medium", []),
        ("三相线缆接触电阻过大", "high", []),
        ("电机控制器放电电阻故障", "medium", []),
    ],
    EV_OBC: [
        ("车载充电机不启动", "high", []),
        ("充电电流异常", "medium", []),
        ("充电电压异常", "medium", []),
        ("车载充电机过温", "high", []),
        ("交流充电口温度过高", "high", []),
        ("OBC 与 BMS 通信失败", "high", []),
        ("充电互锁信号异常", "medium", []),
        ("车载充电机绝缘故障", "critical", []),
        ("充电机输入电压异常", "medium", []),
        ("OBC 输出短路保护", "critical", []),
        ("充电机风扇故障", "low", []),
        ("CC 信号异常", "medium", []),
        ("CP 信号异常", "medium", []),
        ("充电枪锁止机构故障", "low", []),
        ("OBC 通信超时", "medium", []),
        ("充电机整流桥故障", "high", []),
        ("车载充电机软件异常", "low", []),
        ("充电功率受限", "medium", []),
        ("OBC 高压输入断开", "high", []),
        ("充电机温度传感器故障", "low", []),
        ("交流充电桩握手失败", "medium", []),
        ("OBC 待机功耗异常", "low", []),
    ],
    EV_DCDC: [
        ("DC-DC 变换器输出电压异常", "high", []),
        ("DC-DC 输出电流过大", "high", []),
        ("DC-DC 过温保护", "medium", []),
        ("DC-DC 高压侧绝缘故障", "critical", []),
        ("DC-DC 通信中断", "medium", []),
        ("低压电池充电异常", "medium", []),
        ("DC-DC 使能信号异常", "medium", []),
        ("DC-DC 输出短路", "critical", []),
        ("DC-DC 降压失效", "high", []),
        ("低压系统电压波动", "medium", []),
        ("DC-DC 散热风扇故障", "low", []),
        ("DC-DC 输入电压欠压", "medium", []),
        ("DC-DC 输出纹波过大", "low", []),
        ("DC-DC 温度传感器故障", "low", []),
        ("DC-DC 转换效率下降", "low", []),
        ("低压蓄电池亏电", "medium", []),
        ("DC-DC 软件保护触发", "low", []),
        ("DC-DC 高压输入断开", "high", []),
        ("12V 负载短路", "medium", []),
        ("DC-DC 工作模式切换失败", "low", []),
    ],
    EV_THERMAL: [
        ("电池冷却液温度过高", "critical", []),
        ("电池加热功能失效", "medium", []),
        ("冷却水泵故障", "high", []),
        ("电子风扇故障", "medium", []),
        ("热管理水路堵塞", "high", []),
        ("PTC 加热器故障", "high", []),
        ("空调压缩机驱动故障", "medium", []),
        ("热泵系统制冷剂泄漏", "medium", []),
        ("电池冷却回路电磁阀故障", "medium", []),
        ("冷却液液位过低", "high", []),
        ("热管理控制器通信中断", "medium", []),
        ("冷却回路传感器故障", "low", []),
        ("电池温差过大", "medium", []),
        ("散热器堵塞", "medium", []),
        ("冷却液循环不足", "high", []),
        ("PTC 高压互锁断开", "critical", []),
        ("空调压力异常", "medium", []),
        ("热管理 CAN 总线故障", "medium", []),
        ("电动水泵控制异常", "medium", []),
        ("冷却液温度传感器漂移", "low", []),
    ],
    EV_HV: [
        ("高压系统绝缘故障", "critical", []),
        ("高压互锁回路断开", "critical", []),
        ("高压继电器故障", "high", []),
        ("高压母线电压异常", "high", []),
        ("高压泄漏检测异常", "critical", []),
        ("高压系统主动放电失败", "critical", []),
        ("高压接触器粘连", "critical", []),
        ("高压维修开关状态异常", "medium", []),
        ("高压互锁短路", "critical", []),
        ("高压系统被动放电异常", "medium", []),
        ("高压母线预充失败", "high", []),
        ("高压系统 EMI 干扰", "low", []),
        ("高压线束屏蔽层断裂", "medium", []),
        ("高压配电箱过温", "high", []),
        ("高压系统快插未锁紧", "high", []),
        ("高压传感器故障", "medium", []),
        ("高压系统碰撞断电解锁", "critical", []),
        ("高压系统爬电距离不足", "medium", []),
        ("高压母线电容放电异常", "high", []),
        ("高压系统供电波动", "medium", []),
    ],
    EV_REGEN: [
        ("再生制动失效", "high", []),
        ("能量回收功率受限", "medium", []),
        ("再生制动扭矩波动", "medium", []),
        ("制动踏板信号异常", "high", []),
        ("再生制动与液压制动协调异常", "high", []),
        ("能量回收系统通信中断", "medium", []),
        ("再生制动时电池过充保护", "medium", []),
        ("滑行能量回收失效", "low", []),
        ("制动能量回收效率下降", "low", []),
        ("再生制动退出异常", "medium", []),
        ("制动主缸压力传感器故障", "high", []),
        ("ESP 与再生制动协调失败", "high", []),
        ("能量回收过温限制", "medium", []),
        ("再生制动扭矩需求超限", "medium", []),
        ("坡道辅助与回收冲突", "low", []),
        ("再生制动回馈电流异常", "high", []),
        ("蠕行功能异常", "low", []),
        ("制动能量回收 CAN 信号丢失", "high", []),
        ("电池 SOC 高时回收受限", "low", []),
        ("再生制动泵电机故障", "medium", []),
    ],
}

ORDER = [EV_BMS, EV_MOTOR, EV_OBC, EV_DCDC, EV_THERMAL, EV_HV, EV_REGEN]


def _to_num(n: int) -> str:
    return f"{n:03d}"


def build_rows():
    rows = []
    for system in ORDER:
        entries = DATA[system]
        for i, (desc, sev, related) in enumerate(entries, start=1):
            code = f"{system}-{_to_num(i)}"
            rows.append({
                "code": code,
                "system": system,
                "code_type": "manufacturer",
                "description": desc,
                "detail": "",
                "severity": sev,
                "common_causes": "[]",
                "diagnostic_steps": "[]",
                "related_codes": ",".join(related),
                "symptoms": "[]",
            })
    return rows


def main():
    rows = build_rows()
    # 保护：若目标已存在且含 AI 增强的详情，提示后退出，避免误覆盖
    if OUT_PATH.exists():
        with open(str(OUT_PATH), encoding="utf-8") as f:
            existing = list(csv.DictReader(f))
        if existing and all(r.get("detail") for r in existing):
            print(f"[WARN] {OUT_PATH} 已存在且 146 条均已含 AI 增强详情。")
            print("       该脚本用于初始生成种子，重跑会清空 detail 交给 batch_enhance_codes 重新增强。")
            import sys as _sys
            resp = input("   确认继续（会清空 detail）? (y/N): ").strip().lower()
            if resp != "y":
                print("[CANCEL] 未改动")
                return
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(str(OUT_PATH), "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)

    by_sys = {}
    for r in rows:
        by_sys[r["system"]] = by_sys.get(r["system"], 0) + 1
    print(f"[OK] 生成 {OUT_PATH}")
    print(f"[OK] 共 {len(rows)} 条:")
    for sys_name in ORDER:
        print(f"     {sys_name}: {by_sys.get(sys_name, 0)}")


if __name__ == "__main__":
    main()
