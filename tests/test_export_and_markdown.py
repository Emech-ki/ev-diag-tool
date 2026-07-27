"""
export_utils.py 和 markdown_renderer.py 单元测试
"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.ui.markdown_renderer import md_to_html, md_to_plain_text
from src.ui.export_utils import (
    _parse_json_field, _parse_related_codes, _get_severity_label,
    export_as_text, export_as_html
)


class TestMarkdownToHtml(unittest.TestCase):
    """md_to_html 测试"""

    def test_empty_input(self):
        self.assertEqual(md_to_html(""), "")
        self.assertEqual(md_to_html(None), "")

    def test_header_h1(self):
        result = md_to_html("# 标题")
        self.assertIn("<h1", result)
        self.assertIn("标题", result)

    def test_header_h2(self):
        result = md_to_html("## 二级标题")
        self.assertIn("<h2", result)
        self.assertIn("二级标题", result)

    def test_header_h3(self):
        result = md_to_html("### 三级标题")
        self.assertIn("<h3", result)
        self.assertIn("三级标题", result)

    def test_bold(self):
        result = md_to_html("**粗体**")
        self.assertIn("<strong>粗体</strong>", result)

    def test_italic(self):
        result = md_to_html("*斜体*")
        self.assertIn("<em>斜体</em>", result)

    def test_strikethrough(self):
        result = md_to_html("~~删除~~")
        self.assertIn("<del>删除</del>", result)

    def test_inline_code(self):
        result = md_to_html("`code`")
        self.assertIn("<code", result)
        self.assertIn("code", result)

    def test_code_block(self):
        result = md_to_html("```python\nprint('hello')\n```")
        self.assertIn("print", result)
        self.assertIn("python", result)

    def test_unordered_list(self):
        result = md_to_html("- 项目1\n- 项目2")
        self.assertIn("<ul", result)
        self.assertIn("<li>项目1</li>", result)
        self.assertIn("<li>项目2</li>", result)

    def test_ordered_list(self):
        result = md_to_html("1. 第一步\n2. 第二步")
        self.assertIn("<ol", result)
        self.assertIn("<li>第一步</li>", result)
        self.assertIn("<li>第二步</li>", result)

    def test_link(self):
        result = md_to_html("[Google](https://google.com)")
        self.assertIn("<a href", result)
        self.assertIn("https://google.com", result)
        self.assertIn("Google", result)

    def test_horizontal_rule(self):
        result = md_to_html("---")
        self.assertIn("<hr", result)

    def test_blockquote(self):
        result = md_to_html("> 引用内容")
        self.assertIn("<blockquote", result)
        self.assertIn("引用内容", result)

    def test_html_escape_in_text(self):
        """普通文本中的HTML字符应被转义"""
        result = md_to_html("a < b & c")
        self.assertIn("&lt;", result)
        self.assertIn("&amp;", result)

    def test_mixed_content(self):
        """混合Markdown内容"""
        text = "## 标题\n\n**粗体**和*斜体*\n\n- 列表1\n- 列表2"
        result = md_to_html(text)
        self.assertIn("<h2", result)
        self.assertIn("<strong>", result)
        self.assertIn("<em>", result)
        self.assertIn("<ul", result)


class TestMarkdownToPlainText(unittest.TestCase):
    """md_to_plain_text 测试"""

    def test_empty_input(self):
        self.assertEqual(md_to_plain_text(""), "")
        self.assertEqual(md_to_plain_text(None), "")

    def test_header(self):
        result = md_to_plain_text("## 标题")
        self.assertEqual(result, "标题")

    def test_bold(self):
        result = md_to_plain_text("**粗体**")
        self.assertEqual(result, "粗体")

    def test_italic(self):
        result = md_to_plain_text("*斜体*")
        self.assertEqual(result, "斜体")

    def test_strikethrough(self):
        result = md_to_plain_text("~~删除~~")
        self.assertEqual(result, "删除")

    def test_inline_code(self):
        result = md_to_plain_text("`code`")
        self.assertEqual(result, "code")

    def test_code_block(self):
        result = md_to_plain_text("```python\nprint('hello')\n```")
        self.assertIn("print('hello')", result)

    def test_link(self):
        result = md_to_plain_text("[Google](https://google.com)")
        self.assertEqual(result, "Google")

    def test_horizontal_rule(self):
        result = md_to_plain_text("---")
        self.assertIn("-" * 40, result)

    def test_blockquote(self):
        result = md_to_plain_text("> 引用内容")
        self.assertIn("引用内容", result)


class TestParseJsonField(unittest.TestCase):
    """_parse_json_field 测试"""

    def test_list_input(self):
        self.assertEqual(_parse_json_field(["a", "b"]), ["a", "b"])

    def test_json_string(self):
        self.assertEqual(_parse_json_field('["a", "b"]'), ["a", "b"])

    def test_invalid_json(self):
        self.assertEqual(_parse_json_field("not json"), [])

    def test_empty_string(self):
        self.assertEqual(_parse_json_field(""), [])

    def test_none(self):
        self.assertEqual(_parse_json_field(None), [])

    def test_dict_input(self):
        self.assertEqual(_parse_json_field({"key": "value"}), [])


class TestParseRelatedCodes(unittest.TestCase):
    """_parse_related_codes 测试"""

    def test_list_input(self):
        self.assertEqual(_parse_related_codes(["P0301", "P0302"]), ["P0301", "P0302"])

    def test_json_string(self):
        self.assertEqual(_parse_related_codes('["P0301", "P0302"]'), ["P0301", "P0302"])

    def test_comma_separated(self):
        result = _parse_related_codes("P0301, P0302, P0303")
        self.assertEqual(result, ["P0301", "P0302", "P0303"])

    def test_empty_string(self):
        self.assertEqual(_parse_related_codes(""), [])

    def test_none(self):
        self.assertEqual(_parse_related_codes(None), [])


class TestGetSeverityLabel(unittest.TestCase):
    """_get_severity_label 测试"""

    def test_low(self):
        self.assertEqual(_get_severity_label("low"), "低")

    def test_medium(self):
        self.assertEqual(_get_severity_label("medium"), "中")

    def test_high(self):
        self.assertEqual(_get_severity_label("high"), "高")

    def test_critical(self):
        self.assertEqual(_get_severity_label("critical"), "严重")

    def test_unknown(self):
        self.assertEqual(_get_severity_label("unknown"), "unknown")


class TestExportAsText(unittest.TestCase):
    """export_as_text 测试"""

    def test_basic_export(self):
        result = export_as_text(code="P0300")
        self.assertIn("P0300", result)
        self.assertIn("EV-Diag-Tool", result)

    def test_with_knowledge(self):
        knowledge = {
            "description": "随机/多缸失火",
            "severity": "high",
            "system": "动力总成",
            "detail": "ECU检测到多个气缸失火",
            "common_causes": '["火花塞故障", "点火线圈故障"]',
            "diagnostic_steps": '["检查火花塞", "检查点火线圈"]',
        }
        result = export_as_text(code="P0300", knowledge=knowledge)
        self.assertIn("随机/多缸失火", result)
        self.assertIn("高", result)
        self.assertIn("动力总成", result)
        self.assertIn("火花塞故障", result)

    def test_with_vehicle_info(self):
        result = export_as_text(code="P0300", vehicle_info="比亚迪汉EV")
        self.assertIn("比亚迪汉EV", result)

    def test_with_symptoms(self):
        result = export_as_text(code="P0300", symptoms="发动机抖动")
        self.assertIn("发动机抖动", result)

    def test_with_timestamp(self):
        result = export_as_text(code="P0300", timestamp="2026-07-27 10:00")
        self.assertIn("2026-07-27 10:00", result)

    def test_with_ai_suggestion(self):
        result = export_as_text(code="P0300", ai_suggestion="建议检查火花塞")
        self.assertIn("建议检查火花塞", result)
        self.assertIn("AI 建议", result)


class TestExportAsHtml(unittest.TestCase):
    """export_as_html 测试"""

    def test_basic_export(self):
        result = export_as_html(code="P0300")
        self.assertIn("<!DOCTYPE html>", result)
        self.assertIn("P0300", result)
        self.assertIn("EV-Diag-Tool", result)

    def test_with_knowledge(self):
        knowledge = {
            "description": "随机/多缸失火",
            "severity": "high",
            "system": "动力总成",
            "detail": "ECU检测到多个气缸失火",
            "common_causes": '["火花塞故障", "点火线圈故障"]',
            "diagnostic_steps": '["检查火花塞"]',
        }
        result = export_as_html(code="P0300", knowledge=knowledge)
        self.assertIn("随机/多缸失火", result)
        self.assertIn("severity-high", result)
        self.assertIn("火花塞故障", result)

    def test_with_vehicle_info(self):
        result = export_as_html(code="P0300", vehicle_info="比亚迪汉EV")
        self.assertIn("比亚迪汉EV", result)

    def test_with_ai_suggestion(self):
        result = export_as_html(code="P0300", ai_suggestion="建议检查火花塞")
        self.assertIn("ai-section", result)
        self.assertIn("仅供参考", result)

    def test_html_escape(self):
        """用户输入中的HTML字符应被转义"""
        result = export_as_html(code="<script>alert(1)</script>")
        self.assertNotIn("<script>", result)

    def test_severity_classes(self):
        """不同严重程度应有不同的CSS类"""
        for severity, expected_class in [("low", "severity-low"), ("medium", "severity-medium"),
                                          ("high", "severity-high"), ("critical", "severity-critical")]:
            knowledge = {"severity": severity}
            result = export_as_html(code="P0300", knowledge=knowledge)
            self.assertIn(expected_class, result, f"severity={severity} should have class {expected_class}")


if __name__ == "__main__":
    unittest.main()
