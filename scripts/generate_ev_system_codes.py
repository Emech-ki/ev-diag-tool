# -*- coding: utf-8 -*-
"""
生成 EV 系统故障码种子数据 ev_system_codes.csv

覆盖 8 个新能源系统（与 expert_context 路由 / diagnostic_tools 系统枚举对齐）：
    EV-BMS / EV-MOTOR / EV-OBC / EV-DCDC / EV-THERMAL / EV-HV / EV-REGEN / EV-VCU

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
          "common_causes", "diagnostic_steps", "related_codes", "symptoms", "frequency"]

# (system, [(description, severity, related)])
# related 用代码中的 NNN 表示同系统内引用
EV_BMS = "EV-BMS"
EV_MOTOR = "EV-MOTOR"
EV_OBC = "EV-OBC"
EV_DCDC = "EV-DCDC"
EV_THERMAL = "EV-THERMAL"
EV_HV = "EV-HV"
EV_REGEN = "EV-REGEN"
EV_VCU = "EV-VCU"

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
        ("电池包漏液检测异常", "critical", []),
        ("单体电池内阻异常升高", "medium", []),
        ("BMS 从控采集通信中断", "high", []),
        ("电池温度采样不均衡", "medium", []),
        ("高压接触器断开延迟", "high", []),
        ("预充电阻过温", "high", []),
        ("电池包密封性下降", "medium", []),
        ("绝缘监测仪自检异常", "low", []),
        ("BMS 供电电压异常", "high", []),
        ("电池包碰撞信号触发", "critical", []),
        ("单体电压采样线短路", "high", []),
        ("电池冷却请求信号异常", "medium", []),
        ("充电中接触器误断开", "high", []),
        ("BMS 休眠电流异常", "medium", []),
        ("电池正负极端子松动", "high", []),
        ("高压母线对地短路监测", "critical", []),
        ("电池加热请求信号异常", "medium", []),
        ("单体充电接受能力下降", "medium", []),
        ("BMS 内部时钟异常", "low", []),
        ("电池包内部湿度异常", "medium", []),
        ("放电时电压骤降", "high", []),
        ("总电压采样电路故障", "high", []),
        ("均衡开关击穿", "medium", []),
        ("BMS 看门狗复位", "low", []),
        ("电池温度采样线开路", "high", []),
        ("高压互锁线路短路", "critical", []),
        ("预充电时序异常", "high", []),
        ("电池包局部过热", "critical", []),
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
        ("电机轴承磨损报警", "medium", []),
        ("电机绕组温度过高", "high", []),
        ("旋变信号幅值异常", "high", []),
        ("电机控制器过流保护", "critical", []),
        ("电机转速传感器信号丢失", "high", []),
        ("逆变器直流母线电容故障", "critical", []),
        ("电机三相输出缺相", "critical", []),
        ("MCU 供电电压异常", "medium", []),
        ("电机控制器过热降额", "medium", []),
        ("电机编码器信号异常", "high", []),
        ("电机定子绕组短路", "critical", []),
        ("电机扭矩指令与实际不符", "high", []),
        ("电机控制器 PWM 输出异常", "high", []),
        ("旋变励磁信号异常", "high", []),
        ("电机冷却回路流量不足", "medium", []),
        ("电机控制器低压唤醒失败", "low", []),
        ("电机反电动势检测超限", "medium", []),
        ("三相电流采样漂移", "medium", []),
        ("电机控制器散热风扇故障", "low", []),
        ("电机驻车锁止机构故障", "medium", []),
        ("电机过热保护触发", "high", []),
        ("MCU 与整车通信丢帧", "medium", []),
        ("电机控制器母线电流异常", "high", []),
        ("旋变安装偏差过大", "medium", []),
        ("电机空载电流异常", "low", []),
        ("电机控制器固件损坏", "medium", []),
        ("电机相间绝缘电阻下降", "high", []),
        ("扭矩指令超限保护", "medium", []),
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
        ("充电桩握手超时", "medium", []),
        ("OBC 输出功率不足", "medium", []),
        ("充电指示灯状态异常", "low", []),
        ("OBC 高压侧绝缘电阻下降", "critical", []),
        ("充电启动时序错误", "medium", []),
        ("OBC 主控芯片通信异常", "medium", []),
        ("充电桩导引信号异常", "medium", []),
        ("OBC 低压输出过压", "high", []),
        ("充电电流纹波过大", "low", []),
        ("OBC 散热风道堵塞", "low", []),
        ("充电枪电子锁故障", "low", []),
        ("OBC 输入过流保护", "high", []),
        ("充电结束异常", "medium", []),
        ("OBC 与整车 CAN 通信中断", "high", []),
        ("充电枪温度传感器故障", "low", []),
        ("OBC 输出继电器故障", "high", []),
        ("充电功率因数异常", "low", []),
        ("OBC 待机状态误唤醒", "low", []),
        ("交流充电桩电压不稳定", "medium", []),
        ("OBC 控制板供电异常", "medium", []),
        ("充电效率异常下降", "low", []),
        ("OBC 输入 EMI 滤波故障", "low", []),
        ("充电桩与车辆接地异常", "medium", []),
        ("OBC 输出直流电压漂移", "medium", []),
        ("充电枪插拔检测异常", "medium", []),
        ("OBC 过载保护", "high", []),
        ("充电机散热风扇转速异常", "low", []),
        ("OBC 输入欠压保护", "medium", []),
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
        ("DC-DC 输出电压过高", "high", []),
        ("DC-DC 输出电压过低", "high", []),
        ("DC-DC 软启动失败", "medium", []),
        ("DC-DC 电流采样异常", "medium", []),
        ("DC-DC 输入过压保护", "high", []),
        ("DC-DC 输出过压保护", "high", []),
        ("DC-DC 同步整流故障", "medium", []),
        ("DC-DC 主开关管故障", "critical", []),
        ("DC-DC 变压器温度异常", "medium", []),
        ("DC-DC 休眠/唤醒异常", "low", []),
        ("DC-DC 输出电压纹波异常", "low", []),
        ("DC-DC 与 BMS 通信异常", "medium", []),
        ("低压母线电压骤降", "high", []),
        ("DC-DC 控制板供电异常", "medium", []),
        ("DC-DC 负载突增保护", "medium", []),
        ("DC-DC 过载降额", "medium", []),
        ("DC-DC 接地故障检测", "high", []),
        ("低压电池反接检测", "critical", []),
        ("DC-DC 使能后无输出", "high", []),
        ("DC-DC 输出电压漂移", "medium", []),
        ("DC-DC 散热风道堵塞", "low", []),
        ("DC-DC 高压侧电流异常", "medium", []),
        ("低压系统过压保护", "high", []),
        ("DC-DC 效率异常告警", "low", []),
        ("DC-DC 通信丢帧", "medium", []),
        ("DC-DC 输出电流采样漂移", "low", []),
        ("DC-DC 工作状态回读异常", "low", []),
        ("低压蓄电池充电电流过大", "medium", []),
        ("DC-DC 高压输入过流", "high", []),
        ("DC-DC 自检失败", "medium", []),
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
        ("电池加热回路过流", "high", []),
        ("热泵压缩机转速异常", "medium", []),
        ("空调制冷剂压力过高", "high", []),
        ("电池冷却回路阀门卡滞", "medium", []),
        ("冷却液温度传感器开路", "medium", []),
        ("电子风扇 PWM 控制异常", "medium", []),
        ("电池温控模式切换失败", "low", []),
        ("热管理水泵转速反馈丢失", "medium", []),
        ("PTC 加热器功率异常", "medium", []),
        ("空调蒸发器结冰", "medium", []),
        ("冷却系统旁通阀故障", "medium", []),
        ("电池温度上升过快", "high", []),
        ("热泵系统压缩机高压保护", "high", []),
        ("冷却液压力异常", "medium", []),
        ("电池冷却回路流量计故障", "medium", []),
        ("加热器水温传感器故障", "low", []),
        ("热管理控制器供电异常", "medium", []),
        ("空调鼓风机故障", "low", []),
        ("电池低温充电加热超时", "medium", []),
        ("冷却液循环泵空转", "high", []),
        ("热泵系统膨胀阀故障", "medium", []),
        ("电池包均温性变差", "medium", []),
        ("空调冷凝器散热不良", "low", []),
        ("冷却液管路排气不足", "low", []),
        ("PTC 高压输入异常", "high", []),
        ("电池热管理系统自检失败", "low", []),
        ("空调压缩机过载保护", "medium", []),
        ("冷却液液位传感器故障", "low", []),
        ("电池冷却功率不足", "medium", []),
        ("热泵化霜功能异常", "low", []),
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
        ("高压母线对地短路", "critical", []),
        ("高压接触器控制电路故障", "high", []),
        ("高压系统主动放电超时", "high", []),
        ("高压维修开关误断开", "critical", []),
        ("高压配电箱接触器粘连", "critical", []),
        ("高压母线预充电流异常", "high", []),
        ("高压系统绝缘监测丢失", "critical", []),
        ("高压线束连接器过温", "high", []),
        ("高压互锁回路阻抗异常", "medium", []),
        ("高压继电器触点烧蚀", "high", []),
        ("高压母线电压采样异常", "medium", []),
        ("高压系统快插端子过热", "high", []),
        ("高压配电单元通信中断", "medium", []),
        ("高压系统主动放电使能失败", "high", []),
        ("高压母线电容过压", "critical", []),
        ("高压接触器线圈开路", "high", []),
        ("高压系统漏电流异常", "critical", []),
        ("高压线束绝缘层磨损", "medium", []),
        ("高压配电箱温度传感器故障", "low", []),
        ("高压互锁回路电压异常", "medium", []),
        ("高压系统上电时序错误", "high", []),
        ("高压接触器吸合噪声异常", "low", []),
        ("高压母线谐波异常", "low", []),
        ("高压系统接地电阻过大", "medium", []),
        ("高压维修开关锁止失效", "high", []),
        ("高压母线电流传感器漂移", "medium", []),
        ("高压系统预充继电器故障", "high", []),
        ("高压配电箱风扇故障", "low", []),
        ("高压系统绝缘电阻波动", "medium", []),
        ("高压接触器驱动电压异常", "medium", []),
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
        ("再生制动进入失败", "high", []),
        ("能量回收扭矩响应延迟", "medium", []),
        ("再生制动退出超时", "medium", []),
        ("制动踏板开度信号异常", "high", []),
        ("再生制动系统过压保护", "high", []),
        ("能量回收时车轮抱死趋势", "high", []),
        ("再生制动扭矩指令超限", "medium", []),
        ("滑行回收触发条件异常", "low", []),
        ("制动能量回收与 ESP 冲突", "high", []),
        ("再生制动回馈电压异常", "medium", []),
        ("能量回收功率曲线异常", "low", []),
        ("再生制动系统温度过高", "medium", []),
        ("制动能量回收目标扭矩错误", "medium", []),
        ("再生制动泵压力建立失败", "high", []),
        ("坡道驻车与回收冲突", "low", []),
        ("再生制动时电池电流超限", "high", []),
        ("能量回收请求信号丢失", "high", []),
        ("再生制动扭矩不平滑", "medium", []),
        ("制动能量回收效率降低", "low", []),
        ("再生制动模块软件复位", "low", []),
        ("再生制动时电机反向扭矩异常", "medium", []),
        ("能量回收功能权限受限", "low", []),
        ("再生制动系统自检失败", "medium", []),
        ("制动能量回收电流纹波过大", "low", []),
        ("再生制动与 ABS 协调失败", "high", []),
        ("能量回收扭矩中断恢复异常", "medium", []),
        ("再生制动系统高压互锁断开", "critical", []),
        ("再生制动时电池温升过快", "medium", []),
        ("滑行回收禁止信号异常", "medium", []),
        ("再生制动泵电机过载", "medium", []),
    ],
    EV_VCU: [
        ("整车上电时序错误", "critical", []),
        ("整车下电时序错误", "medium", []),
        ("VCU 主控通信中断", "high", []),
        ("整车网络 CAN 总线故障", "high", []),
        ("网关通信异常", "medium", []),
        ("钥匙认证失败", "medium", []),
        ("无钥匙启动信号异常", "medium", []),
        ("挡位信号异常", "high", []),
        ("挡位驻车请求冲突", "medium", []),
        ("整车休眠唤醒异常", "medium", []),
        ("VCU 唤醒源丢失", "medium", []),
        ("扭矩仲裁异常", "high", []),
        ("扭矩需求信号丢失", "high", []),
        ("加速踏板信号异常", "high", []),
        ("制动踏板信号异常", "high", []),
        ("整车故障降级策略异常", "medium", []),
        ("VCU 供电电压异常", "high", []),
        ("VCU 内部时钟异常", "low", []),
        ("VCU 看门狗复位", "low", []),
        ("整车 CAN 报文丢失", "medium", []),
        ("VCU 与 BMS 通信超时", "high", []),
        ("VCU 与 MCU 通信超时", "high", []),
        ("VCU 与 OBC 通信超时", "medium", []),
        ("整车低压系统供电异常", "high", []),
        ("VCU 固件版本不匹配", "low", []),
        ("碰撞信号处理异常", "critical", []),
        ("高压上下电协同异常", "critical", []),
        ("整车模式切换异常", "low", []),
        ("蠕行扭矩请求异常", "medium", []),
        ("坡道辅助请求异常", "low", []),
        ("整车能量管理策略异常", "medium", []),
        ("VCU 标定参数错误", "low", []),
        ("整车控制器过温", "medium", []),
        ("VCU 低压唤醒失败", "medium", []),
        ("整车安全状态异常", "critical", []),
        ("整车 CAN 报文周期异常", "medium", []),
        ("VCU 与热管理通信异常", "medium", []),
        ("整车制动协调异常", "high", []),
        ("VCU 数据存储异常", "low", []),
        ("整车充电请求仲裁异常", "medium", []),
        ("整车放电功率限制异常", "medium", []),
        ("VCU 硬线信号异常", "medium", []),
        ("整车继电器驱动异常", "high", []),
        ("VCU 休眠电流异常", "medium", []),
        ("整车诊断通信失败", "medium", []),
        ("VCU 与车身控制器通信中断", "medium", []),
        ("整车高压许可请求异常", "critical", []),
        ("VCU 软件复位", "low", []),
        ("整车远程控制请求异常", "low", []),
        ("整车故障存储写满", "low", []),
    ],
}

ORDER = [EV_BMS, EV_MOTOR, EV_OBC, EV_DCDC, EV_THERMAL, EV_HV, EV_REGEN, EV_VCU]


def _to_num(n: int) -> str:
    return f"{n:03d}"


# 确定性频次 seed：severity 基分 + 系统/序号抖动（无需 AI，可复现）
# 抖动用内部稳定哈希（Python 内置 hash() 每次进程随机化，不适用）
_SEV_FREQ_BASE = {"low": 40, "medium": 60, "high": 80, "critical": 95}


def _stable_hash(s: str) -> int:
    h = 0
    for ch in s:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def _frequency_for(system: str, code: str, severity: str) -> int:
    base = _SEV_FREQ_BASE.get(severity, 50)
    return max(10, min(100, base + _system_freq_bias(system, code)))


def _system_freq_bias(system: str, code: str) -> int:
    bias = {
        "EV-BMS": 5, "EV-HV": 3, "EV-OBC": 2, "EV-DCDC": 1,
        "EV-THERMAL": -1, "EV-MOTOR": 4, "EV-REGEN": -2, "EV-VCU": 3,
    }.get(system, 0)
    return bias - (_stable_hash(code) % 5)


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
                "frequency": _frequency_for(system, code, sev),
            })
    return rows


def _load_existing_rows() -> dict:
    """读取现有 CSV，返回 {code: row}"""
    if not OUT_PATH.exists():
        return {}
    with open(str(OUT_PATH), encoding="utf-8") as f:
        return {r["code"]: r for r in csv.DictReader(f)}


def _ensure_frequency(rows):
    """为缺少 frequency 的行回填确定性频次（兼容升级前的旧 CSV/DB 行）"""
    for r in rows:
        if r.get("frequency") in (None, ""):
            code = r["code"]
            r["frequency"] = _frequency_for(r.get("system", ""), code, r.get("severity", "medium"))
    return rows


def _print_summary(rows):
    by_sys = {}
    for r in rows:
        by_sys[r["system"]] = by_sys.get(r["system"], 0) + 1
    print(f"[OK] 共 {len(rows)} 条:")
    for sys_name in ORDER:
        print(f"     {sys_name}: {by_sys.get(sys_name, 0)}")


def do_merge():
    """增量合并：保留现有行（含 AI 详情），只追加缺失的新码"""
    existing = _load_existing_rows()
    merged = {}
    # 按 canonical 顺序写：已有行按原顺序，新行按生成顺序
    for r in build_rows():
        if r["code"] in existing:
            merged[r["code"]] = existing[r["code"]]
        else:
            merged[r["code"]] = r
    rows = [merged[r["code"]] for r in build_rows()]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(str(OUT_PATH), "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(_ensure_frequency(rows))

    print(f"[MERGE] 已有 {len(existing)} 条，新增 {len(rows) - len(existing)} 条，共 {len(rows)} 条")
    _print_summary(rows)


def _merge_sync_rows(generated: list, by_code: dict, existing: dict) -> list:
    """合并 DB → CSV 回写行：只有 DB 有详情时才用 DB 覆盖，否则保留 CSV 原值（纯逻辑，便于测试）"""
    merged = {}
    for r in generated:
        code = r["code"]
        if code in by_code:
            db_row = dict(by_code[code])
            if db_row.get("detail"):
                merged[code] = db_row
            else:
                merged[code] = existing.get(code, r)
        elif code in existing:
            merged[code] = existing[code]
        else:
            merged[code] = r
    return [merged[r["code"]] for r in generated]


def do_sync_db():
    """把数据库中的 EV 详情回写到 CSV（CSV 与 DB 保持一致）"""
    import sqlite3
    import sys as _sys
    db_path = PROJECT_ROOT / "data" / "obd_codes.db"
    if not db_path.exists():
        print(f"[ERROR] 数据库不存在: {db_path}")
        _sys.exit(1)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT code, system, code_type, description, detail, severity, "
        "common_causes, diagnostic_steps, related_codes, symptoms, frequency "
        "FROM obd_codes WHERE code LIKE 'EV-%'"
    ).fetchall()
    conn.close()

    by_code = {r["code"]: r for r in rows}
    existing = _load_existing_rows()
    rows_out = _merge_sync_rows(build_rows(), by_code, existing)
    _ensure_frequency(rows_out)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(str(OUT_PATH), "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows_out)

    has_detail = sum(1 for r in rows_out if r.get("detail"))
    print(f"[SYNC] DB → CSV 回写完成，共 {len(rows_out)} 条，含详情 {has_detail} 条")
    _print_summary(rows_out)


def do_upsert_db():
    """把 CSV 中的 EV 系统码增量写入数据库（仅 EV-% 行，不重建库，幂等）"""
    import sqlite3
    import sys as _sys
    db_path = PROJECT_ROOT / "data" / "obd_codes.db"
    if not db_path.exists():
        print(f"[ERROR] 数据库不存在: {db_path}")
        _sys.exit(1)

    existing = _load_existing_rows()
    if not existing:
        print(f"[ERROR] CSV 为空: {OUT_PATH}")
        _sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    before = conn.execute(
        "SELECT COUNT(*) FROM obd_codes WHERE code LIKE 'EV-%'"
    ).fetchone()[0]

    # CSV 是 EV 系统码的唯一真源：先删后插，保证幂等且无重复
    # （obd_codes 无 UNIQUE(code) 约束，INSERT OR REPLACE 会造成重复行）
    conn.execute("DELETE FROM obd_codes WHERE code LIKE 'EV-%'")
    for row in existing.values():
        code = row["code"]
        conn.execute(
            "INSERT INTO obd_codes "
            "(code, system, code_type, description, detail, severity, "
            " common_causes, diagnostic_steps, related_codes, symptoms, frequency) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                code,
                row.get("system", ""),
                row.get("code_type", "manufacturer"),
                row.get("description", ""),
                row.get("detail", ""),
                row.get("severity", "medium"),
                row.get("common_causes", "[]"),
                row.get("diagnostic_steps", "[]"),
                row.get("related_codes", ""),
                row.get("symptoms", "[]"),
                int(row.get("frequency", 0) or 0),
            ),
        )
    conn.commit()

    after = conn.execute(
        "SELECT COUNT(*) FROM obd_codes WHERE code LIKE 'EV-%'"
    ).fetchone()[0]
    conn.close()

    print(f"[UPSERT] 重写 EV 码 {len(existing)} 条: {before} → {after}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="生成 EV 系统故障码种子数据")
    parser.add_argument("--merge", action="store_true",
                        help="增量合并：保留现有行详情，只追加缺失新码")
    parser.add_argument("--sync-db", action="store_true",
                        help="把数据库 EV 详情回写到 CSV")
    parser.add_argument("--upsert-db", action="store_true",
                        help="把 CSV 的 EV 码增量写入数据库（不重建库）")
    args = parser.parse_args()

    if args.sync_db:
        do_sync_db()
        return

    if args.merge:
        do_merge()
        return

    if args.upsert_db:
        do_upsert_db()
        return

    rows = build_rows()
    # 保护：若目标已存在且含 AI 增强的详情，提示后退出，避免误覆盖
    if OUT_PATH.exists():
        with open(str(OUT_PATH), encoding="utf-8") as f:
            existing = list(csv.DictReader(f))
        if existing and all(r.get("detail") for r in existing):
            print(f"[WARN] {OUT_PATH} 已存在且全部条目均已含 AI 增强详情。")
            print("       该脚本用于初始生成种子，重跑会清空 detail 交给 batch_enhance_codes 重新增强。")
            print("       如需保留详情并只追加新码，请使用 --merge。")
            resp = input("   确认继续（会清空 detail）? (y/N): ").strip().lower()
            if resp != "y":
                print("[CANCEL] 未改动")
                return
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(str(OUT_PATH), "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] 生成 {OUT_PATH}")
    _print_summary(rows)


if __name__ == "__main__":
    main()
