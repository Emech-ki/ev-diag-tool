"""
tests/test_theme_helper.py
theme_helper 纯函数单元测试（不依赖 qtbot）
覆盖 get_theme_colors() 和 get_symptom_colors()
"""

import sys
import os
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.ui.theme_helper import get_theme_colors, get_symptom_colors
from src.ui.styles import get_token


class TestGetThemeColors(unittest.TestCase):
    """get_theme_colors() 返回完整颜色字典"""

    def test_returns_dict(self):
        result = get_theme_colors()
        self.assertIsInstance(result, dict)

    def test_contains_all_required_keys(self):
        result = get_theme_colors()
        required = [
            "PRIMARY", "PRIMARY_DARK", "PRIMARY_LIGHT", "PRIMARY_BG",
            "ACCENT", "ACCENT_BG",
            "BG", "CARD_BG", "CARD_BORDER",
            "TEXT_PRIMARY", "TEXT_SECONDARY", "TEXT_MUTED",
            "SUCCESS", "SUCCESS_BG", "WARNING", "WARNING_BG",
            "DANGER", "DANGER_BG", "CRITICAL", "CRITICAL_BG",
            "INPUT_BG", "INPUT_BORDER", "INPUT_FOCUS",
        ]
        for key in required:
            self.assertIn(key, result, f"Missing key: {key}")

    def test_values_are_hex_strings(self):
        result = get_theme_colors()
        for key, val in result.items():
            self.assertIsInstance(val, str, f"{key} should be str")
            # 颜色值以 # 开头（除 INPUT_FOCUS 可能是主题色名）
            self.assertTrue(
                val.startswith("#") or val.startswith("rgb"),
                f"{key}={val!r} does not look like a color"
            )

    def test_matches_get_token(self):
        """每个键的值应与直接调用 get_token 一致"""
        result = get_theme_colors()
        for key, val in result.items():
            self.assertEqual(val, get_token(key), f"{key} mismatch")


class TestGetSymptomColors(unittest.TestCase):
    """get_symptom_colors() 根据主题返回不同颜色"""

    def test_returns_dict(self):
        result = get_symptom_colors()
        self.assertIsInstance(result, dict)

    def test_contains_required_keys(self):
        result = get_symptom_colors()
        required = [
            "symptom_bg", "symptom_border", "symptom_title_color",
            "symptom_text_color", "symptom_display_bg",
        ]
        for key in required:
            self.assertIn(key, result, f"Missing key: {key}")

    def test_light_theme_values(self):
        """浅色主题返回浅色背景"""
        with patch("src.ui.theme_helper.is_dark", return_value=False):
            result = get_symptom_colors()
            self.assertEqual(result["symptom_bg"], "#F9FBE7")
            self.assertEqual(result["symptom_border"], "#E6EE9C")
            self.assertEqual(result["symptom_title_color"], "#558B2F")

    def test_dark_theme_values(self):
        """深色主题返回深色背景"""
        with patch("src.ui.theme_helper.is_dark", return_value=True):
            result = get_symptom_colors()
            self.assertEqual(result["symptom_bg"], "#1E2A1E")
            self.assertEqual(result["symptom_border"], "#3D5C3D")
            self.assertEqual(result["symptom_title_color"], "#66BB6A")

    def test_values_are_strings(self):
        result = get_symptom_colors()
        for key, val in result.items():
            self.assertIsInstance(val, str, f"{key} should be str")


if __name__ == "__main__":
    unittest.main()
