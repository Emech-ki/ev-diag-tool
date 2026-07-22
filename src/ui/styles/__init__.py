"""Unified Design Tokens — v1.0.0"""

# ── Brand ──
PRIMARY = "#1565C0"
PRIMARY_DARK = "#0D47A1"
PRIMARY_LIGHT = "#42A5F5"
PRIMARY_BG = "#E3F2FD"

ACCENT = "#7C4DFF"
ACCENT_BG = "#EDE7F6"

BG = "#F0F2F5"

CARD_BG = "#FFFFFF"
CARD_BORDER = "#EAECF0"

# ── Text ──
TEXT_PRIMARY = "#1A1A2E"
TEXT_SECONDARY = "#5F6368"
TEXT_MUTED = "#9AA0A6"

# ── Semantic ──
SUCCESS = "#2E7D32"
SUCCESS_BG = "#E8F5E9"
WARNING = "#E65100"
WARNING_BG = "#FFF3E0"
DANGER = "#C62828"
DANGER_BG = "#FFEBEE"
CRITICAL = "#7B1FA2"
CRITICAL_BG = "#F3E5F5"

SEVERITY_STYLES = {
    "low":     {"text": SUCCESS, "bg": SUCCESS_BG, "border": "#4CAF50", "label": "低"},
    "medium":  {"text": WARNING, "bg": WARNING_BG, "border": "#FF9800", "label": "中"},
    "high":    {"text": DANGER,  "bg": DANGER_BG,  "border": "#F44336", "label": "高"},
    "critical":{"text": CRITICAL,"bg": CRITICAL_BG,"border": "#9C27B0", "label": "严重"},
}

# ── Typography ──
FONT_FAMILY = "Microsoft YaHei UI"
FONT_MONO = "Consolas"

RADIUS_MD = 10
RADIUS_LG = 16
