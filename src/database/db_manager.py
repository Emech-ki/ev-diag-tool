"""
数据库管理器
负责 SQLite 数据库的连接、查询和事务管理
"""

import sqlite3
import json
import os
import sys
import shutil
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from src.config import DB_PATH as CONFIG_DB_PATH


class DatabaseManager:
    """数据库管理器（单例模式，线程安全）"""

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, db_path: Optional[str] = None):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        if self._initialized:
            return

        if db_path is None:
            db_path = self._resolve_db_path()

        self.db_path = db_path
        self._write_lock = threading.Lock()
        self._initialized = True
        self._ensure_tables()

    def _ensure_tables(self):
        """检查并创建缺失的表（数据库自动迁移）"""
        from src.database.schema import (
            CREATE_TABLE_HISTORY,
            CREATE_INDEX_HISTORY_CODE,
            CREATE_INDEX_HISTORY_TIME,
        )
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='diagnostic_history'"
            )
            if cursor.fetchone() is None:
                conn.execute(CREATE_TABLE_HISTORY)
                conn.execute(CREATE_INDEX_HISTORY_CODE)
                conn.execute(CREATE_INDEX_HISTORY_TIME)
                conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _resolve_db_path() -> str:
        """确定数据库持久化路径（支持 exe 模式）"""
        # 如果配置中指定了路径，优先使用
        if CONFIG_DB_PATH:
            return CONFIG_DB_PATH

        is_exe = getattr(sys, "frozen", False)

        if is_exe:
            # exe 模式：数据库放在 exe 同目录
            exe_dir = Path(sys.executable).parent
            dest = exe_dir / "data" / "obd_codes.db"

            # 如果目标不存在，从内嵌的数据库复制一份
            if not dest.exists():
                src = Path(sys._MEIPASS) / "data" / "obd_codes.db"
                if src.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(src), str(dest))

            return str(dest)
        else:
            # 开发模式：项目根目录/data/obd_codes.db
            project_root = Path(__file__).resolve().parent.parent.parent
            return str(project_root / "data" / "obd_codes.db")

    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接（每次调用新建连接，WAL 模式支持并发读）"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def query_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """
        根据故障码查询

        Args:
            code: 故障码，如 "P0300"

        Returns:
            故障码信息字典，未找到返回 None
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM obd_codes WHERE code = ?", (code.upper(),))
            row = cursor.fetchone()
            if row is None:
                return None
            return dict(row)
        finally:
            conn.close()

    def search_codes(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        搜索故障码（模糊匹配）

        Args:
            keyword: 搜索关键词（匹配code或description）
            limit: 最大返回数量

        Returns:
            匹配的故障码列表
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            pattern = f"%{keyword}%"
            cursor.execute("""
                SELECT code, description, system, severity
                FROM obd_codes
                WHERE code LIKE ? OR description LIKE ?
                ORDER BY code
                LIMIT ?
            """, (pattern, pattern, limit))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_all_codes(self) -> List[Tuple[str, str]]:
        """获取所有故障码列表（用于自动补全）"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT code, description FROM obd_codes ORDER BY code")
            return [(row["code"], row["description"]) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_system_stats(self) -> List[Dict[str, Any]]:
        """获取各系统故障码数量统计"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT system, COUNT(*) as count
                FROM obd_codes
                GROUP BY system
                ORDER BY system
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_total_count(self) -> int:
        """获取故障码总数"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM obd_codes")
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def database_exists(self) -> bool:
        """检查数据库文件是否存在"""
        return os.path.exists(self.db_path)

    def get_database_info(self) -> Dict[str, Any]:
        """获取数据库信息"""
        return {
            "path": self.db_path,
            "exists": self.database_exists(),
            "total_codes": self.get_total_count() if self.database_exists() else 0,
            "systems": self.get_system_stats() if self.database_exists() else []
        }

    @staticmethod
    def _validate_symptom(symptom: str) -> str:
        """校验并清理症状文本"""
        if not isinstance(symptom, str):
            return ""
        cleaned = symptom.strip()
        if len(cleaned) > 500:
            cleaned = cleaned[:500]
        return cleaned

    def record_symptoms(self, code: str, symptom: str) -> bool:
        """
        为指定故障码记录一条观察到的现象（线程安全）

        Args:
            code: 故障码
            symptom: 现象描述文本

        Returns:
            是否成功
        """
        symptom = self._validate_symptom(symptom)
        if not symptom:
            return False

        with self._write_lock:
            conn = self.get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.cursor()
                row = cursor.execute(
                    "SELECT symptoms FROM obd_codes WHERE code = ?", (code.upper(),)
                ).fetchone()
                if row is None:
                    return False

                existing = self.parse_json_field(row["symptoms"])
                if symptom not in existing:
                    existing.append(symptom)
                    cursor.execute(
                        "UPDATE obd_codes SET symptoms = ?, updated_at = CURRENT_TIMESTAMP WHERE code = ?",
                        (json.dumps(existing, ensure_ascii=False), code.upper()),
                    )
                conn.commit()
                return True
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def get_symptoms(self, code: str) -> list:
        """获取指定故障码的已记录现象列表"""
        conn = self.get_connection()
        try:
            row = conn.execute(
                "SELECT symptoms FROM obd_codes WHERE code = ?", (code.upper(),)
            ).fetchone()
            if row is None:
                return []
            return self.parse_json_field(row["symptoms"])
        finally:
            conn.close()

    def save_history(self, code: str, vehicle_info: str = "", symptoms: str = "",
                     knowledge_found: bool = False, ai_suggestion: str = "") -> bool:
        """保存诊断记录"""
        with self._write_lock:
            conn = self.get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO diagnostic_history
                        (code, vehicle_info, symptoms, knowledge_found, ai_suggestion)
                    VALUES (?, ?, ?, ?, ?)
                """, (code, vehicle_info, symptoms, 1 if knowledge_found else 0, ai_suggestion))
                conn.commit()
                return True
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取诊断历史记录"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, code, vehicle_info, symptoms, knowledge_found,
                       ai_suggestion, created_at
                FROM diagnostic_history
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def search_history(self, keyword: str, limit: int = 50) -> List[Dict[str, Any]]:
        """搜索诊断历史"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            pattern = f"%{keyword}%"
            cursor.execute("""
                SELECT id, code, vehicle_info, symptoms, knowledge_found,
                       ai_suggestion, created_at
                FROM diagnostic_history
                WHERE code LIKE ? OR vehicle_info LIKE ? OR symptoms LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (pattern, pattern, pattern, limit))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def clear_history(self) -> bool:
        """清空诊断历史"""
        with self._write_lock:
            conn = self.get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM diagnostic_history")
                conn.commit()
                return True
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    @staticmethod
    def parse_json_field(json_str: str) -> list:
        """解析 JSON 字段为 Python 列表"""
        if not json_str:
            return []
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return []


# 便捷函数
def get_db() -> DatabaseManager:
    """获取默认数据库管理器实例"""
    return DatabaseManager()
