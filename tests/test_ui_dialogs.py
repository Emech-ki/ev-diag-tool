"""
tests/test_ui_dialogs.py
AddEndpointDialog 对话框单元测试（使用 qtbot + offscreen）
覆盖添加模式、编辑模式、字段验证、URL 格式检查
"""

import sys
import os
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

from src.ui.add_endpoint_dialog import AddEndpointDialog


def _make_dialog(parent=None, endpoint_data=None):
    """创建对话框实例（offscreen 下无需 show）"""
    dlg = AddEndpointDialog(parent=parent, endpoint_data=endpoint_data)
    return dlg


class TestAddEndpointDialogInit(unittest.TestCase):
    """__init__ 和 _init_ui 行为"""

    def test_add_mode_window_title(self):
        dlg = _make_dialog()
        self.assertEqual(dlg.windowTitle(), "添加远程模型")
        self.assertFalse(dlg._edit_mode)

    def test_edit_mode_window_title(self):
        data = {"name": "DeepSeek", "base_url": "https://api.deepseek.com", "api_key": "sk-x", "model_name": "deepseek-chat"}
        dlg = _make_dialog(endpoint_data=data)
        self.assertEqual(dlg.windowTitle(), "编辑远程模型")
        self.assertTrue(dlg._edit_mode)

    def test_edit_mode_prefills_fields(self):
        data = {"name": "DeepSeek", "base_url": "https://api.deepseek.com", "api_key": "sk-x", "model_name": "deepseek-chat"}
        dlg = _make_dialog(endpoint_data=data)
        self.assertEqual(dlg.name_input.text(), "DeepSeek")
        self.assertEqual(dlg.url_input.text(), "https://api.deepseek.com")
        self.assertEqual(dlg.key_input.text(), "sk-x")
        self.assertEqual(dlg.model_input.text(), "deepseek-chat")

    def test_edit_mode_name_is_readonly(self):
        data = {"name": "DeepSeek", "base_url": "https://api.deepseek.com", "api_key": "sk-x", "model_name": "deepseek-chat"}
        dlg = _make_dialog(endpoint_data=data)
        self.assertTrue(dlg.name_input.isReadOnly())

    def test_add_mode_name_not_readonly(self):
        dlg = _make_dialog()
        self.assertFalse(dlg.name_input.isReadOnly())

    def test_result_data_initially_none(self):
        dlg = _make_dialog()
        self.assertIsNone(dlg.result_data)


class TestAddEndpointValidation(unittest.TestCase):
    """_on_confirm 字段验证（mock QMessageBox 阻塞）"""

    @patch("src.ui.add_endpoint_dialog.QMessageBox")
    def test_empty_name_rejected(self, mock_msgbox):
        dlg = _make_dialog()
        dlg.url_input.setText("https://api.example.com")
        dlg.key_input.setText("sk-key")
        dlg.model_input.setText("gpt-4")
        dlg._on_confirm()
        self.assertIsNone(dlg.result_data)
        mock_msgbox.warning.assert_called_once()

    @patch("src.ui.add_endpoint_dialog.QMessageBox")
    def test_empty_url_rejected(self, mock_msgbox):
        dlg = _make_dialog()
        dlg.name_input.setText("Test")
        dlg.key_input.setText("sk-key")
        dlg.model_input.setText("gpt-4")
        dlg._on_confirm()
        self.assertIsNone(dlg.result_data)

    @patch("src.ui.add_endpoint_dialog.QMessageBox")
    def test_empty_key_rejected(self, mock_msgbox):
        dlg = _make_dialog()
        dlg.name_input.setText("Test")
        dlg.url_input.setText("https://api.example.com")
        dlg.model_input.setText("gpt-4")
        dlg._on_confirm()
        self.assertIsNone(dlg.result_data)

    @patch("src.ui.add_endpoint_dialog.QMessageBox")
    def test_empty_model_rejected(self, mock_msgbox):
        dlg = _make_dialog()
        dlg.name_input.setText("Test")
        dlg.url_input.setText("https://api.example.com")
        dlg.key_input.setText("sk-key")
        dlg._on_confirm()
        self.assertIsNone(dlg.result_data)

    @patch("src.ui.add_endpoint_dialog.QMessageBox")
    def test_invalid_url_format_rejected(self, mock_msgbox):
        dlg = _make_dialog()
        dlg.name_input.setText("Test")
        dlg.url_input.setText("ftp://bad-protocol.com")
        dlg.key_input.setText("sk-key")
        dlg.model_input.setText("gpt-4")
        dlg._on_confirm()
        self.assertIsNone(dlg.result_data)

    @patch("src.ui.add_endpoint_dialog.QMessageBox")
    def test_invalid_url_no_scheme_rejected(self, mock_msgbox):
        dlg = _make_dialog()
        dlg.name_input.setText("Test")
        dlg.url_input.setText("api.example.com/v1")
        dlg.key_input.setText("sk-key")
        dlg.model_input.setText("gpt-4")
        dlg._on_confirm()
        self.assertIsNone(dlg.result_data)

    def test_valid_input_accepts(self):
        """所有字段填写正确 → accept，result_data 被设置"""
        dlg = _make_dialog()
        dlg.name_input.setText("TestAPI")
        dlg.url_input.setText("https://api.openai.com/v1")
        dlg.key_input.setText("sk-test123")
        dlg.model_input.setText("gpt-4")
        dlg._on_confirm()
        self.assertIsNotNone(dlg.result_data)
        self.assertEqual(dlg.result_data["name"], "TestAPI")
        self.assertEqual(dlg.result_data["base_url"], "https://api.openai.com/v1")
        self.assertEqual(dlg.result_data["api_key"], "sk-test123")
        self.assertEqual(dlg.result_data["model_name"], "gpt-4")

    def test_whitespace_trimmed(self):
        dlg = _make_dialog()
        dlg.name_input.setText("  Test  ")
        dlg.url_input.setText("  https://api.example.com  ")
        dlg.key_input.setText("  sk-key  ")
        dlg.model_input.setText("  gpt-4  ")
        dlg._on_confirm()
        self.assertEqual(dlg.result_data["name"], "Test")
        self.assertEqual(dlg.result_data["base_url"], "https://api.example.com")
        self.assertEqual(dlg.result_data["api_key"], "sk-key")
        self.assertEqual(dlg.result_data["model_name"], "gpt-4")

    def test_http_scheme_accepted(self):
        dlg = _make_dialog()
        dlg.name_input.setText("Local")
        dlg.url_input.setText("http://localhost:11434/v1")
        dlg.key_input.setText("sk-key")
        dlg.model_input.setText("llama")
        dlg._on_confirm()
        self.assertIsNotNone(dlg.result_data)

    def test_https_scheme_accepted(self):
        dlg = _make_dialog()
        dlg.name_input.setText("OpenAI")
        dlg.url_input.setText("https://api.openai.com/v1")
        dlg.key_input.setText("sk-key")
        dlg.model_input.setText("gpt-4")
        dlg._on_confirm()
        self.assertIsNotNone(dlg.result_data)


class TestAddEndpointGetResult(unittest.TestCase):
    """get_result() 返回值"""

    def test_get_result_returns_none_before_confirm(self):
        dlg = _make_dialog()
        self.assertIsNone(dlg.get_result())

    def test_get_result_returns_data_after_confirm(self):
        dlg = _make_dialog()
        dlg.name_input.setText("Test")
        dlg.url_input.setText("https://api.example.com")
        dlg.key_input.setText("sk-key")
        dlg.model_input.setText("gpt-4")
        dlg._on_confirm()
        self.assertIsNotNone(dlg.get_result())
        self.assertEqual(dlg.get_result()["name"], "Test")


if __name__ == "__main__":
    unittest.main()
