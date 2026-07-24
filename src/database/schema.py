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
