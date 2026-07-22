#!/usr/bin/env python3
"""
EV-Diag-Tool 新能源汽车智能诊断工具
主入口文件

运行方式:
    python src/main.py
"""

import sys
import os

# 将项目根目录加入 Python 路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QFont
from src.ui.main_window import MainWindow


def check_database():
    """检查数据库是否存在（统一使用 DatabaseManager 路径解析）"""
    from src.database.db_manager import DatabaseManager
    db = DatabaseManager()
    info = db.get_database_info()
    if not info.get("exists"):
        QMessageBox.warning(
            None,
            "数据库未初始化",
            "数据库文件不存在！\n\n请先运行以下命令初始化数据库：\n\n"
            f"    python scripts/seed_db.py\n\n"
            f"期待路径: {info.get('path', '?')}"
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

    # 检查数据库
    check_database()

    # 启动主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
