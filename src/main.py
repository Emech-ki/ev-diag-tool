#!/usr/bin/env python3
"""
EV-Diag-Tool 新能源汽车智能诊断工具
主入口文件

运行方式:
    python src/main.py
"""

import sys
import os

# 将项目根目录加入 Python 路径（兼容调试器运行）
_file_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_file_dir)  # ev-diag-tool/

# 确保项目根目录在 sys.path 最前面
if PROJECT_ROOT in sys.path:
    sys.path.remove(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

# 加载配置（在其他模块导入之前）
from src import config

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QFont
from src.ui.main_window import MainWindow


def check_database():
    """检查数据库是否存在，使用 config 中的统一路径解析"""
    from src.database.db_manager import DatabaseManager
    db_path = DatabaseManager._resolve_db_path()
    if not os.path.exists(db_path):
        QMessageBox.warning(
            None,
            "数据库未初始化",
            "数据库文件不存在！\n\n请先运行以下命令初始化数据库：\n\n"
            f"    python scripts/seed_db.py\n\n"
            f"期待路径: {db_path}"
        )
        return False
    return True


def main():
    """主函数"""
    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("EV-Diag-Tool")
    app.setApplicationDisplayName("新能源汽车智能诊断工具")

    # 设置全局字体
    font = QFont("Microsoft YaHei UI", 10)
    app.setFont(font)

    # 设置全局样式
    app.setStyleSheet("""
        QMainWindow {
            background-color: #F5F5F5;
        }
        QGroupBox {
            font-size: 13px;
            font-weight: bold;
            color: #555;
            border: 1px solid #E0E0E0;
            border-radius: 6px;
            margin-top: 8px;
            padding-top: 16px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
        }
        QTabWidget::pane {
            border: 1px solid #E0E0E0;
            border-radius: 4px;
            background-color: #FAFAFA;
        }
        QTabBar::tab {
            padding: 8px 16px;
            font-size: 13px;
            border: 1px solid transparent;
            border-bottom: none;
        }
        QTabBar::tab:selected {
            background-color: #FAFAFA;
            border-color: #E0E0E0;
            border-bottom: 2px solid #1976D2;
            color: #1976D2;
            font-weight: bold;
        }
        QTabBar::tab:hover:!selected {
            background-color: #E3F2FD;
        }
        QStatusBar {
            font-size: 12px;
            color: #666;
        }
    """)

    # 检查数据库，不存在则退出
    if not check_database():
        sys.exit(1)

    # 启动主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
