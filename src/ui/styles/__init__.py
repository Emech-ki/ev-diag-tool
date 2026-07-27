"""Unified Design Tokens — v2.0.0 with Dark Mode Support"""

import os
from pathlib import Path
from dotenv import load_dotenv, set_key

# ── 项目根目录 ──
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"

# 加载 .env
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH, override=True)

# ── 浅色主题 ──
_LIGHT = {
    "PRIMARY": "#1565C0",
    "PRIMARY_DARK": "#0D47A1",
    "PRIMARY_LIGHT": "#42A5F5",
    "PRIMARY_BG": "#E3F2FD",
    "ACCENT": "#7C4DFF",
    "ACCENT_BG": "#EDE7F6",
    "BG": "#F0F2F5",
    "CARD_BG": "#FFFFFF",
    "CARD_BORDER": "#EAECF0",
    "TEXT_PRIMARY": "#1A1A2E",
    "TEXT_SECONDARY": "#5F6368",
    "TEXT_MUTED": "#9AA0A6",
    "SUCCESS": "#2E7D32",
    "SUCCESS_BG": "#E8F5E9",
    "WARNING": "#E65100",
    "WARNING_BG": "#FFF3E0",
    "DANGER": "#C62828",
    "DANGER_BG": "#FFEBEE",
    "CRITICAL": "#7B1FA2",
    "CRITICAL_BG": "#F3E5F5",
    "INPUT_BG": "#FFFFFF",
    "INPUT_BORDER": "#EAECF0",
    "INPUT_FOCUS": "#1565C0",
    "SEVERITY_STYLES": {
        "low":     {"text": "#2E7D32", "bg": "#E8F5E9", "border": "#4CAF50", "label": "低"},
        "medium":  {"text": "#E65100", "bg": "#FFF3E0", "border": "#FF9800", "label": "中"},
        "high":    {"text": "#C62828", "bg": "#FFEBEE", "border": "#F44336", "label": "高"},
        "critical":{"text": "#7B1FA2", "bg": "#F3E5F5", "border": "#9C27B0", "label": "严重"},
    },
}

# ── 深色主题 ──
_DARK = {
    "PRIMARY": "#42A5F5",
    "PRIMARY_DARK": "#1565C0",
    "PRIMARY_LIGHT": "#90CAF9",
    "PRIMARY_BG": "#1A237E",
    "ACCENT": "#B388FF",
    "ACCENT_BG": "#311B92",
    "BG": "#121218",
    "CARD_BG": "#1E1E2A",
    "CARD_BORDER": "#2D2D3F",
    "TEXT_PRIMARY": "#E8E8EC",
    "TEXT_SECONDARY": "#A0A0B4",
    "TEXT_MUTED": "#6B6B80",
    "SUCCESS": "#66BB6A",
    "SUCCESS_BG": "#1B3A1D",
    "WARNING": "#FFA726",
    "WARNING_BG": "#3E2A0A",
    "DANGER": "#EF5350",
    "DANGER_BG": "#3E1212",
    "CRITICAL": "#CE93D8",
    "CRITICAL_BG": "#2A1230",
    "INPUT_BG": "#252535",
    "INPUT_BORDER": "#3D3D5C",
    "INPUT_FOCUS": "#42A5F5",
    "SEVERITY_STYLES": {
        "low":     {"text": "#66BB6A", "bg": "#1B3A1D", "border": "#4CAF50", "label": "低"},
        "medium":  {"text": "#FFA726", "bg": "#3E2A0A", "border": "#FF9800", "label": "中"},
        "high":    {"text": "#EF5350", "bg": "#3E1212", "border": "#F44336", "label": "高"},
        "critical":{"text": "#CE93D8", "bg": "#2A1230", "border": "#9C27B0", "label": "严重"},
    },
}

# ── Typography (不变) ──
FONT_FAMILY = "Microsoft YaHei UI"
FONT_MONO = "Consolas"

# ── 主题管理 ──
_current_theme = None


def _load_theme() -> str:
    """从 .env 加载主题设置"""
    theme = os.getenv("THEME", "light").lower().strip()
    return theme if theme in ("light", "dark") else "light"


def _init_theme():
    """初始化当前主题"""
    global _current_theme
    if _current_theme is None:
        _current_theme = _load_theme()


def get_theme() -> str:
    """获取当前主题名称: 'light' 或 'dark'"""
    _init_theme()
    return _current_theme


def set_theme(theme: str):
    """切换主题并保存到 .env"""
    global _current_theme
    theme = theme.lower().strip()
    if theme not in ("light", "dark"):
        return
    _current_theme = theme
    # 保存到 .env
    try:
        if _ENV_PATH.exists():
            set_key(str(_ENV_PATH), "THEME", theme)
        else:
            with open(_ENV_PATH, "w", encoding="utf-8") as f:
                f.write(f"THEME={theme}\n")
    except Exception:
        pass
    # 同步到环境变量
    os.environ["THEME"] = theme


def toggle_theme() -> str:
    """切换主题，返回新主题名"""
    current = get_theme()
    new_theme = "dark" if current == "light" else "light"
    set_theme(new_theme)
    return new_theme


def is_dark() -> bool:
    """是否深色模式"""
    return get_theme() == "dark"


def get_tokens() -> dict:
    """获取当前主题的设计令牌"""
    _init_theme()
    return _DARK if _current_theme == "dark" else _LIGHT


def get_token(name: str, default: str = "") -> str:
    """获取单个令牌值（动态，随主题切换而变化）"""
    return get_tokens().get(name, default)


# ── 初始化 ──
_init_theme()

# ── 静态导出（向后兼容，初始主题值） ──
# 新代码应使用 get_token() 获取动态值
_tokens = get_tokens()

PRIMARY = _tokens["PRIMARY"]
PRIMARY_DARK = _tokens["PRIMARY_DARK"]
PRIMARY_LIGHT = _tokens["PRIMARY_LIGHT"]
PRIMARY_BG = _tokens["PRIMARY_BG"]
ACCENT = _tokens["ACCENT"]
ACCENT_BG = _tokens["ACCENT_BG"]
BG = _tokens["BG"]
CARD_BG = _tokens["CARD_BG"]
CARD_BORDER = _tokens["CARD_BORDER"]
TEXT_PRIMARY = _tokens["TEXT_PRIMARY"]
TEXT_SECONDARY = _tokens["TEXT_SECONDARY"]
TEXT_MUTED = _tokens["TEXT_MUTED"]
SUCCESS = _tokens["SUCCESS"]
SUCCESS_BG = _tokens["SUCCESS_BG"]
WARNING = _tokens["WARNING"]
WARNING_BG = _tokens["WARNING_BG"]
DANGER = _tokens["DANGER"]
DANGER_BG = _tokens["DANGER_BG"]
CRITICAL = _tokens["CRITICAL"]
CRITICAL_BG = _tokens["CRITICAL_BG"]
INPUT_BG = _tokens["INPUT_BG"]
INPUT_BORDER = _tokens["INPUT_BORDER"]
INPUT_FOCUS = _tokens["INPUT_FOCUS"]
SEVERITY_STYLES = _tokens["SEVERITY_STYLES"]
