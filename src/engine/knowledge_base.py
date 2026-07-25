"""
知识库查询模块
负责从 SQLite 数据库中查询故障码知识
"""

import json
from typing import Optional, Dict, Any, List
from src.database.db_manager import get_db, DatabaseManager


class KnowledgeBase:
    """
    知识库引擎
    提供故障码的知识查询功能，返回结构化的诊断信息
    """

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or get_db()

    def lookup(self, code: str) -> Optional[Dict[str, Any]]:
        """
        查询故障码

        Args:
            code: 故障码，如 "P0300"

        Returns:
            包含以下字段的字典:
                - code: 故障码
                - system: 所属系统
                - code_type: 类型
                - description: 简短描述
                - detail: 详细说明
                - severity: 严重程度
                - common_causes: 常见原因列表
                - diagnostic_steps: 诊断步骤列表
                - related_codes: 相关故障码列表

            未找到时返回 None
        """
        result = self.db.query_by_code(code)

        if result is None:
            return None

        # 解析 JSON 字段
        result["common_causes"] = self.db.parse_json_field(result.get("common_causes", "[]"))
        result["diagnostic_steps"] = self.db.parse_json_field(result.get("diagnostic_steps", "[]"))

        # 解析相关故障码（兼容 JSON 数组和逗号分隔两种格式）
        related = result.get("related_codes", "")
        if isinstance(related, str) and related:
            try:
                parsed = json.loads(related)
                if isinstance(parsed, list):
                    result["related_codes"] = [str(c).strip() for c in parsed if str(c).strip()]
                else:
                    result["related_codes"] = [c.strip() for c in related.split(",") if c.strip()]
            except (json.JSONDecodeError, TypeError):
                result["related_codes"] = [c.strip() for c in related.split(",") if c.strip()]
        elif isinstance(related, list):
            result["related_codes"] = related
        else:
            result["related_codes"] = []

        return result

    def search(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        搜索故障码

        Args:
            keyword: 搜索关键词
            limit: 最大返回数量

        Returns:
            匹配的故障码列表
        """
        return self.db.search_codes(keyword, limit)

    def get_suggestions(self, partial: str, limit: int = 10) -> List[str]:
        """
        获取自动补全建议

        Args:
            partial: 用户输入的部分故障码
            limit: 最大建议数量

        Returns:
            匹配的故障码字符串列表
        """
        results = self.db.search_codes(partial, limit)
        return [r["code"] for r in results]

    def record_symptoms(self, code: str, symptom: str) -> bool:
        """记录技师观察到的现象"""
        return self.db.record_symptoms(code, symptom)

    def get_symptoms(self, code: str) -> list:
        """获取指定故障码的已记录现象"""
        return self.db.get_symptoms(code)

    def get_severity_info(self, severity: str) -> Dict[str, Any]:
        """获取严重程度对应的显示信息"""
        severity_map = {
            "low": {
                "label": "低",
                "color": "#4CAF50",      # 绿色
                "icon": "ℹ️",
                "description": "建议尽快检查，暂时不影响行驶安全"
            },
            "medium": {
                "label": "中",
                "color": "#FF9800",      # 橙色
                "icon": "⚠️",
                "description": "建议尽快维修，可能影响排放或性能"
            },
            "high": {
                "label": "高",
                "color": "#F44336",      # 红色
                "icon": "🔴",
                "description": "建议立即检查，可能影响行车安全"
            },
            "critical": {
                "label": "严重",
                "color": "#9C27B0",      # 紫色
                "icon": "🚨",
                "description": "立即停止行驶，存在严重安全隐患"
            }
        }
        return severity_map.get(severity, severity_map["medium"])

    def get_system_info(self, system_code: str) -> Dict[str, str]:
        """获取系统代码对应的显示名称"""
        system_map = {
            "P": {"name": "动力总成", "full_name": "Powertrain (动力总成/发动机)", "icon": "🚗"},
            "B": {"name": "车身", "full_name": "Body (车身电器)", "icon": "🚙"},
            "C": {"name": "底盘", "full_name": "Chassis (底盘系统)", "icon": "🔧"},
            "U": {"name": "网络", "full_name": "Network (网络通讯)", "icon": "📡"},
        }
        # 新能源系统映射到 P 类
        ev_systems = {"EV-BMS", "EV-MOTOR", "EV-OBC", "EV-DCDC", "EV-THERMAL", "EV-HV"}
        if system_code in ev_systems:
            return {"name": "新能源动力", "full_name": f"EV ({system_code})", "icon": "⚡"}
        first_letter = system_code[0].upper() if system_code else ""
        return system_map.get(first_letter, {"name": "未知", "full_name": "未知系统", "icon": "❓"})

    # ── 车型数据库查询 ──

    def get_vehicle_makes(self) -> List[str]:
        """获取所有品牌列表"""
        try:
            rows = self.db.execute_query(
                "SELECT DISTINCT make FROM vehicle_models ORDER BY make"
            )
            return [r["make"] for r in rows]
        except Exception:
            return []

    def get_models_by_make(self, make: str) -> List[Dict[str, Any]]:
        """获取指定品牌的所有车型"""
        try:
            rows = self.db.execute_query(
                "SELECT model, year_start, year_end, powertrain FROM vehicle_models WHERE make = ? ORDER BY model",
                (make,)
            )
            return rows
        except Exception:
            return []

    def get_vehicle_info(self, make: str, model: str) -> Optional[Dict[str, Any]]:
        """获取特定车型详细信息"""
        try:
            rows = self.db.execute_query(
                "SELECT * FROM vehicle_models WHERE make = ? AND model = ?",
                (make, model)
            )
            if not rows:
                return None

            result = dict(rows[0])
            # 解析 JSON 字段
            result["common_codes"] = self.db.parse_json_field(result.get("common_codes", "[]"))
            result["known_issues"] = self.db.parse_json_field(result.get("known_issues", "[]"))
            return result
        except Exception:
            return None

    def get_common_codes_for_vehicle(self, make: str, model: str) -> List[str]:
        """获取车型常见故障码列表"""
        info = self.get_vehicle_info(make, model)
        if info:
            return info.get("common_codes", [])
        return []


