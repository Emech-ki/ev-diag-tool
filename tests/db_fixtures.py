"""
共享测试数据库夹具
供各测试模块创建独立的临时 SQLite 数据库
"""

import json
import sqlite3
import threading

from src.database.schema import (
    CREATE_TABLE_OBD_CODES, CREATE_INDEX_CODE, CREATE_INDEX_SYSTEM,
    CREATE_TABLE_HISTORY, CREATE_INDEX_HISTORY_CODE, CREATE_INDEX_HISTORY_TIME,
    CREATE_TABLE_VEHICLE_MODELS, CREATE_INDEX_VEHICLE_MAKE, CREATE_INDEX_VEHICLE_MODEL
)
from src.database.db_manager import DatabaseManager
from src.engine.knowledge_base import KnowledgeBase


def setup_test_db(db_path):
    """创建测试数据库并插入覆盖各分支的测试数据"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(CREATE_TABLE_OBD_CODES)
    cursor.execute(CREATE_INDEX_CODE)
    cursor.execute(CREATE_INDEX_SYSTEM)
    cursor.execute(CREATE_TABLE_HISTORY)
    cursor.execute(CREATE_INDEX_HISTORY_CODE)
    cursor.execute(CREATE_INDEX_HISTORY_TIME)
    cursor.execute(CREATE_TABLE_VEHICLE_MODELS)
    cursor.execute(CREATE_INDEX_VEHICLE_MAKE)
    cursor.execute(CREATE_INDEX_VEHICLE_MODEL)

    def _insert_code(code, system, code_type, description, detail, severity,
                     common_causes, diagnostic_steps, related_codes, symptoms):
        cursor.execute("""
            INSERT INTO obd_codes (code, system, code_type, description, detail,
                                   severity, common_causes, diagnostic_steps,
                                   related_codes, symptoms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            code, system, code_type, description, detail, severity,
            json.dumps(common_causes, ensure_ascii=False),
            json.dumps(diagnostic_steps, ensure_ascii=False),
            related_codes,
            json.dumps(symptoms, ensure_ascii=False)
        ))

    # 传统 P 码（有详情 + 相关码）
    _insert_code(
        "P0300", "P", "generic", "随机/多缸失火", "ECU检测到多个气缸失火",
        "high",
        ["火花塞故障", "点火线圈故障"],
        ["读取冻结帧", "检查火花塞"],
        "P0301,P0302",
        ["发动机抖动"]
    )
    # 含十六进制字母的码
    _insert_code(
        "P0A00", "P", "generic", "混合动力电池组电压异常", "BMS检测到电池组总电压超出正常范围",
        "critical",
        ["电池单体电压不一致", "高压接触器接触不良"],
        ["读取BMS数据流", "检查单体电压极差"],
        "P0A01,P0A02",
        ["仪表显示电池故障灯", "动力输出受限"]
    )
    # P0Axx 码但描述含电机关键词（触发电机专家路由）
    _insert_code(
        "P0A1F", "P", "generic", "电机旋变位置传感器信号异常", "MCU检测到旋变传感器信号丢失",
        "high",
        ["旋变线束断裂"],
        ["检查旋变线束"],
        "",
        ["动力受限"]
    )
    # B 码
    _insert_code(
        "B1100", "B", "manufacturer", "左前门锁执行器电路故障", "门锁电机电路异常",
        "low",
        ["门锁执行器故障"],
        ["检查门锁开关"],
        "B1101",
        ["车门无法上锁"]
    )
    # C 码（常见原因比步骤多，触发 fixes 缺步骤分支）
    _insert_code(
        "C1201", "C", "generic", "左前轮速传感器信号异常", "ABS模块检测到左前轮速信号缺失",
        "medium",
        ["传感器损坏", "传感器线路断路", "齿圈损坏"],
        ["读取ABS数据流"],
        "C1202",
        ["ABS故障灯亮"]
    )
    # U 码（无相关码）
    _insert_code(
        "U0100", "U", "generic", "与ECM通信丢失", "CAN总线上无法收到ECM报文",
        "high",
        ["CAN总线断路", "ECM供电异常"],
        [],
        "",
        ["仪表多个警告灯亮"]
    )
    # 新能源 EV 系统码
    _insert_code(
        "EV-BMS-001", "EV-BMS", "ev", "电池组绝缘电阻过低", "BMS检测到高压回路对地绝缘电阻低于阈值",
        "critical",
        ["绝缘膜破损", "高压线束进水"],
        ["测量绝缘电阻", "分段检查高压回路"],
        "",
        ["仪表显示绝缘故障"]
    )
    _insert_code(
        "EV-MOTOR-001", "EV-MOTOR", "ev", "电机旋变传感器信号异常", "MCU检测到旋变传感器正弦/余弦信号幅度异常",
        "high",
        ["旋变传感器线束断裂", "旋变传感器损坏"],
        ["检查旋变线束", "测量旋变信号"],
        "",
        ["动力受限"]
    )
    _insert_code(
        "EV-THERMAL-001", "EV-THERMAL", "ev", "电池冷却回路流量过低", "BMS检测到电池冷却回路冷却液流量低于阈值",
        "medium",
        ["水泵故障", "冷却液不足"],
        ["检查水泵转速", "补充冷却液"],
        "",
        ["电池温度偏高"]
    )

    # 车型数据
    def _insert_vehicle(make, model, year_start, year_end, powertrain,
                        battery_type, motor_type, common_codes, known_issues, notes):
        cursor.execute("""
            INSERT INTO vehicle_models (make, model, year_start, year_end, powertrain,
                                        battery_type, motor_type, common_codes, known_issues, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            make, model, year_start, year_end, powertrain,
            battery_type, motor_type,
            json.dumps(common_codes, ensure_ascii=False),
            json.dumps(known_issues, ensure_ascii=False),
            notes
        ))

    _insert_vehicle("比亚迪", "秦PLUS EV", 2021, None, "BEV",
                    "磷酸铁锂", "永磁同步",
                    ["P0A00", "P0A01", "P0A0E"], ["冬季续航衰减明显"], "紧凑型轿车")
    _insert_vehicle("特斯拉", "Model 3", 2019, None, "BEV",
                    "三元锂", "永磁同步",
                    ["P0A00", "P0A01", "P0A32"], ["悬挂异响"], "中型轿车")

    conn.commit()
    conn.close()


def make_test_kb(db_path):
    """基于临时数据库创建 KnowledgeBase 实例"""
    DatabaseManager._instance = None
    DatabaseManager._instance_lock = threading.Lock()
    db = DatabaseManager(db_path=db_path)
    return KnowledgeBase(db=db)
