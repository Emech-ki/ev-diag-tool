"""
主题辅助模块
提供统一的颜色获取接口，减少重复代码
"""

from src.ui.styles import get_token, is_dark


def get_theme_colors() -> dict:
    """
    获取当前主题的所有颜色值

    Returns:
        包含所有主题颜色的字典
    """
    return {
        # Brand
        "PRIMARY": get_token("PRIMARY"),
        "PRIMARY_DARK": get_token("PRIMARY_DARK"),
        "PRIMARY_LIGHT": get_token("PRIMARY_LIGHT"),
        "PRIMARY_BG": get_token("PRIMARY_BG"),
        "ACCENT": get_token("ACCENT"),
        "ACCENT_BG": get_token("ACCENT_BG"),
        # Background
        "BG": get_token("BG"),
        "CARD_BG": get_token("CARD_BG"),
        "CARD_BORDER": get_token("CARD_BORDER"),
        # Text
        "TEXT_PRIMARY": get_token("TEXT_PRIMARY"),
        "TEXT_SECONDARY": get_token("TEXT_SECONDARY"),
        "TEXT_MUTED": get_token("TEXT_MUTED"),
        # Semantic
        "SUCCESS": get_token("SUCCESS"),
        "SUCCESS_BG": get_token("SUCCESS_BG"),
        "WARNING": get_token("WARNING"),
        "WARNING_BG": get_token("WARNING_BG"),
        "DANGER": get_token("DANGER"),
        "DANGER_BG": get_token("DANGER_BG"),
        "CRITICAL": get_token("CRITICAL"),
        "CRITICAL_BG": get_token("CRITICAL_BG"),
        # Input
        "INPUT_BG": get_token("INPUT_BG"),
        "INPUT_BORDER": get_token("INPUT_BORDER"),
        "INPUT_FOCUS": get_token("INPUT_FOCUS"),
    }


def get_symptom_colors() -> dict:
    """
    获取现象录入区的专用颜色（根据主题动态调整）

    Returns:
        包含现象录入区颜色的字典
    """
    if is_dark():
        return {
            "symptom_bg": "#1E2A1E",
            "symptom_border": "#3D5C3D",
            "symptom_title_color": "#66BB6A",
            "symptom_text_color": "#A5D6A7",
            "symptom_display_bg": "#253525",
            "symptom_disabled": "#2E4A2E",
        }
    else:
        return {
            "symptom_bg": "#F9FBE7",
            "symptom_border": "#E6EE9C",
            "symptom_title_color": "#558B2F",
            "symptom_text_color": "#33691E",
            "symptom_display_bg": "rgba(255,255,255,0.6)",
            "symptom_disabled": "#C5E1A5",
        }
