"""
测试公共 fixtures
为 PyQt6 UI 测试提供 QApplication 实例
"""

import os
import sys

# 强制 offscreen 渲染（CI 无显示器时也通过）
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 确保 src 在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

_app = None


@pytest.fixture(scope="session", autouse=True)
def qapp_instance():
    """Session 级 QApplication 实例（所有 UI 测试共享）"""
    global _app
    from PyQt6.QtWidgets import QApplication
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)
    else:
        _app = QApplication.instance()
    return _app
