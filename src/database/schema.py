"""
数据库表结构定义
"""

# SQLite 表结构
CREATE_TABLE_OBD_CODES = """
CREATE TABLE IF NOT EXISTS obd_codes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    code             TEXT    NOT NULL,              -- 故障码: P0300
    system           TEXT    NOT NULL,              -- 系统: P/B/C/U
    code_type        TEXT    DEFAULT 'generic',     -- generic 通用 / manufacturer 厂商自定义
    description      TEXT    NOT NULL,              -- 简短描述
    detail           TEXT    DEFAULT '',            -- 详细说明
    severity         TEXT    DEFAULT 'medium',       -- 严重程度: low/medium/high/critical

    -- JSON 格式存储，便于扩展
    common_causes    TEXT    DEFAULT '[]',           -- JSON数组: ["原因1", "原因2"]
    diagnostic_steps TEXT    DEFAULT '[]',           -- JSON数组: ["步骤1", "步骤2"]

    -- 辅助字段
    related_codes    TEXT    DEFAULT '',             -- 相关故障码: "P0301,P0302"
    symptoms         TEXT    DEFAULT '[]',           -- JSON数组: ["现象1", "现象2"]

    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_TABLE_HISTORY = """
CREATE TABLE IF NOT EXISTS diagnostic_history (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    code             TEXT    NOT NULL,
    vehicle_info     TEXT    DEFAULT '',
    symptoms         TEXT    DEFAULT '',
    knowledge_found  INTEGER DEFAULT 0,
    ai_suggestion    TEXT    DEFAULT '',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# 索引
CREATE_INDEX_CODE = "CREATE INDEX IF NOT EXISTS idx_code ON obd_codes(code)"
CREATE_INDEX_SYSTEM = "CREATE INDEX IF NOT EXISTS idx_system ON obd_codes(system)"
CREATE_INDEX_HISTORY_CODE = "CREATE INDEX IF NOT EXISTS idx_history_code ON diagnostic_history(code)"
CREATE_INDEX_HISTORY_TIME = "CREATE INDEX IF NOT EXISTS idx_history_time ON diagnostic_history(created_at)"

# 查询语句
SQL_QUERY_BY_CODE = "SELECT * FROM obd_codes WHERE code = ?"
SQL_SEARCH_CODES = """
    SELECT code, description, system, severity
    FROM obd_codes
    WHERE code LIKE ? OR description LIKE ?
    ORDER BY code
    LIMIT 20
"""
SQL_GET_ALL_CODES = "SELECT code, description FROM obd_codes ORDER BY code"
SQL_GET_COUNT = "SELECT COUNT(*) FROM obd_codes"
SQL_GET_SYSTEM_STATS = """
    SELECT system, COUNT(*) as count
    FROM obd_codes
    GROUP BY system
    ORDER BY system
"""
