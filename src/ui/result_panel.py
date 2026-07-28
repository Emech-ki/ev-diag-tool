"""
诊断结果面板
显示知识库信息和 AI 诊断建议
"""

import html
import json
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextBrowser, QFrame, QSplitter, QLineEdit, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QTextCursor

from src.engine.diagnostic import DiagnosticResult
from src.engine.knowledge_base import KnowledgeBase
from src.ui.markdown_renderer import md_to_html
from src.ui.styles import (
    PRIMARY, PRIMARY_DARK, PRIMARY_BG, CARD_BG, CARD_BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, BG, FONT_MONO,
    SEVERITY_STYLES, WARNING, WARNING_BG
)


class DtcTextBrowser(QTextBrowser):
    def setSource(self, url):
        if url.scheme() == "dtc":
            return
        super().setSource(url)


class ResultPanel(QWidget):
    """诊断结果展示面板"""

    diagnose_requested = pyqtSignal(str)
    export_requested = pyqtSignal()  # 导出按钮点击信号

    def __init__(self):
        super().__init__()
        self.kb = KnowledgeBase()
        self._current_code = None
        self._current_result = None  # 保存当前诊断结果（用于导出）
        self._ai_stream_started = False
        self._ai_stream_content = ""
        self._multi_results = []  # 多码诊断结果列表
        self._individual_ai_contents = {}  # 单码 AI 内容 {index: content}
        self._init_ui()
        self._init_connections()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {CARD_BORDER};
                width: 1px;
            }}
        """)

        # === 左：知识库结果 ===
        knowledge_widget = QWidget()
        knowledge_layout = QVBoxLayout(knowledge_widget)
        knowledge_layout.setContentsMargins(0, 0, 8, 0)
        knowledge_layout.setSpacing(8)

        self.knowledge_browser = DtcTextBrowser()
        self.knowledge_browser.setOpenExternalLinks(False)
        self.knowledge_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: transparent;
                border: none;
                padding: 4px;
                font-size: 14px;
                line-height: 1.7;
                color: {TEXT_PRIMARY};
            }}
        """)
        knowledge_layout.addWidget(self.knowledge_browser, 1)

        splitter.addWidget(knowledge_widget)

        # === 右：AI 建议 ===
        ai_widget = QWidget()
        ai_layout = QVBoxLayout(ai_widget)
        ai_layout.setContentsMargins(8, 0, 0, 0)
        ai_layout.setSpacing(8)

        ai_header = QFrame()
        ai_header.setStyleSheet(f"""
            QFrame {{
                background-color: {PRIMARY_BG};
                border-radius: 8px; padding: 10px;
            }}
        """)
        ai_header_layout = QHBoxLayout(ai_header)
        ai_header_layout.setContentsMargins(12, 8, 12, 8)

        ai_title = QLabel("AI 诊断建议")
        ai_title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {PRIMARY};")
        ai_header_layout.addWidget(ai_title)

        self.ai_status_label = QLabel()
        self.ai_status_label.setStyleSheet(f"font-size: 11px; color: {TEXT_SECONDARY};")
        ai_header_layout.addWidget(self.ai_status_label)
        ai_header_layout.addStretch()

        ai_layout.addWidget(ai_header)

        self.ai_browser = QTextBrowser()
        self.ai_browser.setOpenExternalLinks(True)
        self.ai_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: transparent;
                border: none;
                padding: 4px;
                font-size: 14px;
                line-height: 1.7;
                color: {TEXT_PRIMARY};
            }}
        """)
        ai_layout.addWidget(self.ai_browser, 1)

        splitter.addWidget(ai_widget)

        splitter.setSizes([500, 500])
        layout.addWidget(splitter, 1)

        # === 现象录入区 ===
        symptom_card = QFrame()
        symptom_card.setObjectName("card")
        symptom_card.setStyleSheet(f"""
            QFrame#card {{
                background-color: #F9FBE7;
                border: 1px solid #E6EE9C;
                border-radius: 8px;
            }}
        """)
        symptom_layout = QVBoxLayout(symptom_card)
        symptom_layout.setContentsMargins(14, 10, 14, 10)
        symptom_layout.setSpacing(8)

        symptom_header = QHBoxLayout()
        symptom_title = QLabel("记录观察到的现象")
        symptom_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: #558B2F;")
        symptom_header.addWidget(symptom_title)
        symptom_header.addStretch()

        self.export_btn = QPushButton("导出报告")
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 12px;
                background-color: {PRIMARY_BG}; color: {PRIMARY};
                border: 1px solid {PRIMARY}; border-radius: 4px;
                padding: 2px 12px; min-height: 24px;
            }}
            QPushButton:hover {{ background-color: {PRIMARY}; color: white; }}
        """)
        self.export_btn.clicked.connect(self.export_requested.emit)
        symptom_header.addWidget(self.export_btn)
        symptom_layout.addLayout(symptom_header)

        self.symptom_display = QLabel()
        self.symptom_display.setWordWrap(True)
        self.symptom_display.setStyleSheet("""
            font-size: 12px; color: #33691E; padding: 8px;
            background-color: rgba(255,255,255,0.6);
            border-radius: 4px;
        """)
        symptom_layout.addWidget(self.symptom_display)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self.symptom_input = QLineEdit()
        self.symptom_input.setPlaceholderText("输入你观察到的故障现象...")
        self.symptom_input.setMaxLength(500)
        self.symptom_input.setStyleSheet(f"""
            QLineEdit {{
                font-size: 13px; padding: 6px 10px;
                border: 1px solid #E6EE9C; border-radius: 6px;
                background-color: white; min-height: 20px;
            }}
            QLineEdit:focus {{ border-color: #8BC34A; }}
        """)
        input_row.addWidget(self.symptom_input, 1)

        self.symptom_btn = QPushButton("保存")
        self.symptom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.symptom_btn.setStyleSheet("""
            QPushButton {
                font-size: 13px; font-weight: bold;
                background-color: #8BC34A; color: white;
                border: none; border-radius: 6px;
                padding: 4px 20px; min-height: 32px;
            }
            QPushButton:hover { background-color: #7CB342; }
            QPushButton:disabled { background-color: #C5E1A5; }
        """)
        self.symptom_btn.clicked.connect(self._on_save_symptom)
        self.symptom_btn.setEnabled(False)
        input_row.addWidget(self.symptom_btn)

        symptom_layout.addLayout(input_row)
        layout.addWidget(symptom_card)

    def _init_connections(self):
        """初始化信号连接"""
        self.knowledge_browser.anchorClicked.connect(self._on_anchor_clicked)

    def _on_anchor_clicked(self, url):
        """处理知识库中的可点击链接（如相关故障码）"""
        if url.scheme() == "dtc":
            # QUrl 将 dtc://P0300 中的 P0300 解析为 host（且转为小写），path 为空
            code = url.host().upper() if url.host() else url.path().strip("/")
            if code:
                QTimer.singleShot(0, lambda c=code: self.diagnose_requested.emit(c))

    def _on_save_symptom(self):
        """保存技师记录的现象"""
        text = self.symptom_input.text().strip()
        if not text or not self._current_code:
            return

        success = self.kb.record_symptoms(self._current_code, text)
        if success:
            self.symptom_input.clear()
            self._refresh_symptoms_display()
            self.symptom_display.setStyleSheet("""
                font-size: 12px; color: #444; padding: 6px;
                background-color: #E8F5E9; border-radius: 4px;
            """)
        else:
            QMessageBox.warning(self, "提示", f"故障码 {self._current_code} 不存在")

    def _refresh_symptoms_display(self):
        """刷新已记录现象展示"""
        if not self._current_code:
            self.symptom_display.setText("暂无记录")
            self.symptom_btn.setEnabled(False)
            return

        symptoms = self.kb.get_symptoms(self._current_code)
        if symptoms:
            items = " | ".join(f"• {s}" for s in symptoms)
            self.symptom_display.setText(f"已记录现象: {items}")
            self.symptom_btn.setEnabled(True)
        else:
            self.symptom_display.setText("该故障码暂未记录现象，请在下方录入")
            self.symptom_btn.setEnabled(True)

    def clear(self):
        """清空所有内容"""
        self.knowledge_browser.clear()
        self.ai_browser.clear()
        self.ai_status_label.clear()
        self._ai_stream_started = False
        self._ai_stream_content = ""

    def get_current_result(self) -> Optional[DiagnosticResult]:
        """获取当前诊断结果（用于导出）"""
        return self._current_result

    def show_result(self, result: DiagnosticResult):
        """显示诊断结果"""
        self.clear()
        self._current_result = result

        self._current_code = result.code if result.has_knowledge() else None
        self._refresh_symptoms_display()

        if result.has_knowledge():
            kb_html = self._build_knowledge_html(result)
        else:
            kb_html = self._build_not_found_html(result)

        self.knowledge_browser.setHtml(kb_html)

        if result.has_ai():
            ai_html = self._build_ai_html(result)
            self.ai_browser.setHtml(ai_html)
            self.ai_status_label.setText("✅ AI 诊断建议已生成（仅供参考）")
            self.ai_status_label.setStyleSheet("font-size: 12px; color: #4CAF50; padding: 4px;")
        else:
            self._show_ai_unavailable()

    def show_kb_result(self, result: DiagnosticResult):
        """仅显示知识库结果，AI 区域显示加载/不可用状态"""
        self.clear()
        self._current_result = result

        self._current_code = result.code if result.has_knowledge() else None
        self._refresh_symptoms_display()

        if result.has_knowledge():
            kb_html = self._build_knowledge_html(result)
        else:
            kb_html = self._build_not_found_html(result)

        self.knowledge_browser.setHtml(kb_html)

        if result.ai_available:
            self._show_ai_loading()
        else:
            self._show_ai_unavailable()

    def show_lookup_result(self, result: DiagnosticResult):
        """快速查询展示（用于相关码跳转），只显示知识库，不显示 AI 状态"""
        self.clear()
        self._current_result = result

        self._current_code = result.code if result.has_knowledge() else None
        self._refresh_symptoms_display()

        if result.has_knowledge():
            kb_html = self._build_knowledge_html(result)
        else:
            kb_html = self._build_not_found_html(result)

        self.knowledge_browser.setHtml(kb_html)

    def append_ai_text(self, token: str):
        """追加 AI 流式 token 到 AI 浏览器（基础渲染，完成后会重建）"""
        if not self._ai_stream_started:
            self.ai_browser.clear()
            self._ai_stream_started = True
            self._ai_stream_content = ""

        self._ai_stream_content += token
        # 流式阶段用基础转义，不做完整 Markdown 渲染（避免跨 token 问题）
        escaped = html.escape(token)
        escaped = escaped.replace('\n', '<br>')

        cursor = self.ai_browser.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(escaped)
        self.ai_browser.ensureCursorVisible()

    def finalize_ai_suggestion(self, code: str, full_text: str, timestamp: str = ""):
        """AI 流式完成，用完整 Markdown 渲染重建 HTML"""
        if not full_text:
            return

        rendered = md_to_html(full_text)

        self.ai_browser.setHtml(f"""
            <div style="font-family: 'Microsoft YaHei UI', sans-serif;">
                <div style="color: {TEXT_SECONDARY}; font-size: 12px; margin-bottom: 12px;">
                    基于 {code} + 车型/症状信息生成
                    <span style="float: right;">{timestamp}</span>
                </div>
                <div style="color: {TEXT_PRIMARY}; line-height: 1.7; font-size: 14px;">
                    {rendered}
                </div>
                <div style="margin-top: 16px; padding: 10px 14px; background-color: {WARNING_BG};
                            border-radius: 6px; font-size: 12px; color: {WARNING};">
                    AI 建议仅供参考，请结合实际情况和专业判断做出维修决策。
                </div>
            </div>
        """)
        self.ai_status_label.setText("✅ AI 诊断建议已生成（仅供参考）")
        self.ai_status_label.setStyleSheet("font-size: 12px; color: #4CAF50; padding: 4px;")

    def _show_ai_loading(self):
        """显示 AI 生成中占位"""
        self.ai_browser.setHtml("""
            <div style="text-align: center; color: #999; margin-top: 40px;">
                <p style="font-size: 24px;">⏳</p>
                <p>AI 诊断建议生成中...</p>
            </div>
        """)
        self.ai_status_label.setText("⏳ 生成中...")
        self.ai_status_label.setStyleSheet("font-size: 12px; color: #1976D2; padding: 4px;")

    def _show_ai_unavailable(self):
        """显示 AI 不可用"""
        self.ai_browser.setHtml("""
            <div style="text-align: center; color: #999; margin-top: 40px;">
                <p style="font-size: 24px;">🤖</p>
                <p>AI 诊断暂不可用</p>
                <p style="font-size: 12px;">请确保 Ollama 已启动且模型已加载</p>
            </div>
        """)
        self.ai_status_label.setText("⚠️ AI 服务未连接")
        self.ai_status_label.setStyleSheet("font-size: 12px; color: #FF9800; padding: 4px;")

    def _build_knowledge_html(self, result: DiagnosticResult) -> str:
        """构建知识库信息的 HTML（卡片式布局）"""
        kb = result.knowledge
        severity = kb.get("severity", "medium")
        sev = SEVERITY_STYLES.get(severity, SEVERITY_STYLES["medium"])

        desc = html.escape(kb.get("description", ""))
        sys_info = self.kb.get_system_info(kb.get("system", ""))
        sys_name = html.escape(sys_info.get("name", "未知") if isinstance(sys_info, dict) else "未知")

        kb_html = f"""
        <div style="font-family: 'Microsoft YaHei UI', Consolas, sans-serif;">"""

        kb_html += f"""
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 4px;">
                <span style="font-family: Consolas; font-size: 32px; font-weight: bold; color: {TEXT_PRIMARY};">
                    {html.escape(result.code)}
                </span>
                <span style="background-color: {sev['bg']}; color: {sev['text']};
                             font-size: 12px; font-weight: bold; padding: 3px 10px;
                             border-radius: 4px; border: 1px solid {sev['border']};">
                    {sev['label']}
                </span>
            </div>

            <div style="font-size: 16px; color: {TEXT_SECONDARY}; margin-bottom: 14px;">
                {desc}
            </div>

            <div style="display: flex; gap: 16px; font-size: 12px; color: {TEXT_SECONDARY}; margin-bottom: 16px;">
                <span>系统: {sys_name}</span>
                <span>类型: {html.escape(kb.get('code_type', '通用'))}</span>
            </div>

            <div style="height: 1px; background-color: {CARD_BORDER}; margin-bottom: 14px;"></div>
        """

        detail = kb.get("detail", "")
        if detail:
            kb_html += f"""
            <div style="margin-bottom: 14px;">
                <div style="font-size: 13px; font-weight: bold; color: {TEXT_PRIMARY}; margin-bottom: 6px;">详细说明</div>
                <div style="font-size: 14px; color: {TEXT_SECONDARY}; line-height: 1.7;">{html.escape(detail)}</div>
            </div>
            <div style="height: 1px; background-color: {CARD_BORDER}; margin-bottom: 14px;"></div>
            """

        causes = kb.get("common_causes", [])
        if isinstance(causes, str):
            try:
                causes = json.loads(causes)
            except (json.JSONDecodeError, TypeError):
                causes = []
        if causes:
            items = "".join(
                f'<li style="margin: 6px 0; padding-left: 4px; color: {TEXT_SECONDARY};">{html.escape(c)}</li>'
                for c in causes
            )
            kb_html += f"""
            <div style="margin-bottom: 14px;">
                <div style="font-size: 13px; font-weight: bold; color: {TEXT_PRIMARY}; margin-bottom: 6px;">常见原因</div>
                <ul style="margin: 0; padding-left: 20px;">{items}</ul>
            </div>
            <div style="height: 1px; background-color: {CARD_BORDER}; margin-bottom: 14px;"></div>
            """

        steps = kb.get("diagnostic_steps", [])
        if isinstance(steps, str):
            try:
                steps = json.loads(steps)
            except (json.JSONDecodeError, TypeError):
                steps = []
        if steps:
            items = "".join(
                f'<li style="margin: 8px 0; padding-left: 4px; color: {TEXT_SECONDARY}; line-height: 1.6;">{html.escape(s)}</li>'
                for s in steps
            )
            kb_html += f"""
            <div style="margin-bottom: 14px;">
                <div style="font-size: 13px; font-weight: bold; color: {TEXT_PRIMARY}; margin-bottom: 6px;">诊断步骤</div>
                <ol style="margin: 0; padding-left: 20px;">{items}</ol>
            </div>
            <div style="height: 1px; background-color: {CARD_BORDER}; margin-bottom: 14px;"></div>
            """

        related = kb.get("related_codes", [])
        if isinstance(related, str):
            related = [r.strip() for r in related.split(",") if r.strip()]
        if related:
            chips = " ".join(
                f'<a href="dtc://{html.escape(r)}" style="text-decoration: none; '
                f'background-color: {PRIMARY_BG}; color: {PRIMARY}; '
                f'font-family: Consolas; font-size: 12px; padding: 2px 10px; border-radius: 4px;">{html.escape(r)}</a>'
                for r in related
            )
            kb_html += f"""
            <div style="height: 1px; background-color: {CARD_BORDER}; margin-bottom: 10px;"></div>
            <div style="margin-bottom: 4px;">
                <div style="font-size: 13px; font-weight: bold; color: {TEXT_PRIMARY}; margin-bottom: 6px;">相关故障码</div>
                <div>{chips}</div>
            </div>
            """

        kb_html += "</div>"
        return kb_html

    def _build_not_found_html(self, result: DiagnosticResult) -> str:
        """构建未找到故障码的 HTML"""
        return f"""
        <div style="text-align: center; margin-top: 60px;
                    font-family: 'Microsoft YaHei UI', sans-serif;">
            <div style="font-size: 48px; margin-bottom: 12px; color: {CARD_BORDER};">?</div>
            <div style="font-size: 20px; font-weight: bold; color: {TEXT_PRIMARY}; margin-bottom: 8px;">
                未找到故障码 "{html.escape(result.code)}"
            </div>
            <div style="font-size: 14px; color: {TEXT_SECONDARY};">
                该故障码暂未收录到知识库中
            </div>
            <div style="font-size: 12px; color: {TEXT_MUTED}; margin-top: 20px; line-height: 1.8;">
                建议：<br>
                1. 检查故障码格式是否正确（如 P0300）<br>
                2. 使用 AI 诊断助手进行对话分析
            </div>
        </div>
        """

    def _build_ai_html(self, result: DiagnosticResult) -> str:
        """构建 AI 建议的 HTML"""
        suggestion = result.ai_suggestion or ""
        rendered = md_to_html(suggestion)

        return f"""
        <div style="font-family: 'Microsoft YaHei UI', sans-serif;">
            <div style="color: {TEXT_SECONDARY}; font-size: 12px; margin-bottom: 12px;">
                基于 {html.escape(result.code)} + 车型/症状信息生成
                <span style="float: right;">{result.timestamp}</span>
            </div>
            <div style="color: {TEXT_PRIMARY}; line-height: 1.7; font-size: 14px;">
                {rendered}
            </div>
            <div style="margin-top: 16px; padding: 10px 14px; background-color: {WARNING_BG};
                        border-radius: 6px; font-size: 12px; color: {WARNING};">
                AI 建议仅供参考，请结合实际情况和专业判断做出维修决策。
            </div>
        </div>
        """

    # ── 多故障码展示方法 ──

    def show_multi_results(self, codes: list, correlation):
        """初始化多码结果展示"""
        self.clear()
        self._multi_results = [None] * len(codes)
        self._individual_ai_contents = {}
        
        # 构建概览 HTML
        overview_html = self._build_multi_overview_html(codes, correlation)
        self.knowledge_browser.setHtml(overview_html)
        
        if correlation.is_correlated:
            self._show_ai_loading()
            self.ai_status_label.setText("⏳ 综合 AI 诊断生成中...")
        else:
            self.ai_browser.clear()

    def show_multi_kb_result(self, index: int, result: DiagnosticResult):
        """更新多码结果中某个码的知识库信息"""
        if index >= len(self._multi_results):
            return
        
        self._multi_results[index] = result
        
        # 重建完整展示
        codes = [r.code for r in self._multi_results if r]
        if codes:
            html_parts = []
            for i, r in enumerate(self._multi_results):
                if r and r.has_knowledge():
                    html_parts.append(self._build_single_code_section(r, i))
                elif r:
                    html_parts.append(self._build_not_found_section(r, i))
            
            combined_html = f"""
            <div style="font-family: 'Microsoft YaHei UI', Consolas, sans-serif;">
                {''.join(html_parts)}
            </div>
            """
            self.knowledge_browser.setHtml(combined_html)

    def append_combined_ai_token(self, token: str):
        """追加综合 AI 流式 token（多码关联模式）"""
        if not hasattr(self, '_combined_ai_content'):
            self._combined_ai_content = ""
            self._combined_ai_started = False

        if not self._combined_ai_started:
            self.ai_browser.clear()
            self._combined_ai_started = True
            # 显示头部
            codes_str = ", ".join(r.code for r in self._multi_results if r)
            header_html = f"""
            <div style="font-family: 'Microsoft YaHei UI', sans-serif; margin-bottom: 12px;">
                <h3 style="color: {PRIMARY}; font-size: 15px; margin-bottom: 8px;">
                    综合诊断建议（生成中...）
                </h3>
                <div style="font-size: 12px; color: {TEXT_SECONDARY}; margin-bottom: 12px;">
                    {html.escape(codes_str)}
                </div>
            </div>
            """
            cursor = self.ai_browser.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertHtml(header_html)

        self._combined_ai_content += token
        # 流式阶段用基础转义，不做完整 Markdown 渲染
        escaped = html.escape(token).replace('\n', '<br>')
        cursor = self.ai_browser.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(escaped)
        self.ai_browser.ensureCursorVisible()

    def show_combined_ai(self, full_text: str):
        """展示综合 AI 建议"""
        # 清理流式状态
        if hasattr(self, '_combined_ai_content'):
            del self._combined_ai_content
        if hasattr(self, '_combined_ai_started'):
            del self._combined_ai_started

        rendered = md_to_html(full_text)
        codes_str = ", ".join(r.code for r in self._multi_results if r)
        
        self.ai_browser.setHtml(f"""
            <div style="font-family: 'Microsoft YaHei UI', sans-serif;">
                <div style="color: {TEXT_SECONDARY}; font-size: 12px; margin-bottom: 12px;">
                    综合分析: {html.escape(codes_str)}
                    <span style="float: right;">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</span>
                </div>
                <div style="color: {TEXT_PRIMARY}; line-height: 1.7; font-size: 14px;">
                    {rendered}
                </div>
                <div style="margin-top: 16px; padding: 10px 14px; background-color: {WARNING_BG};
                            border-radius: 6px; font-size: 12px; color: {WARNING};">
                    AI 建议仅供参考，请结合实际情况和专业判断做出维修决策。
                </div>
            </div>
        """)
        self.ai_status_label.setText("✅ 综合 AI 诊断建议已生成（仅供参考）")
        self.ai_status_label.setStyleSheet("font-size: 12px; color: #4CAF50; padding: 4px;")

    def append_individual_ai_token(self, index: int, token: str):
        """追加单码 AI 流式 token"""
        if index not in self._individual_ai_contents:
            self._individual_ai_contents[index] = ""
        self._individual_ai_contents[index] += token

        # 更新展示（当前正在处理的码）
        if index < len(self._multi_results) and self._multi_results[index]:
            current_code = self._multi_results[index].code
            # 重建当前码的完整内容，而不是只显示最新 token
            full_content = self._individual_ai_contents.get(index, "")
            if full_content:
                # 清空并重新显示当前码的完整内容
                self.ai_browser.clear()
                header_html = f"""
                <div style="font-family: 'Microsoft YaHei UI', sans-serif; margin-bottom: 12px;">
                    <h3 style="color: {PRIMARY}; font-size: 15px; margin-bottom: 8px;">
                        {html.escape(current_code)} 诊断建议（生成中...）
                    </h3>
                </div>
                """
                cursor = self.ai_browser.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.insertHtml(header_html)

                # 插入当前内容（用基础转义，流式阶段不做完整 Markdown 渲染）
                escaped = html.escape(full_content).replace('\n', '<br>')
                cursor.insertHtml(escaped)
                self.ai_browser.ensureCursorVisible()

    def finalize_individual_ai(self, index: int, text: str):
        """单码 AI 完成，渲染最终 HTML"""
        if not text or index >= len(self._multi_results):
            return
        
        rendered = md_to_html(text)
        code = self._multi_results[index].code if self._multi_results[index] else ""
        
        # 在 AI 浏览器中追加该码的完整建议
        new_section = f"""
        <div style="margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid {CARD_BORDER};">
            <h3 style="color: {PRIMARY}; font-size: 15px; margin-bottom: 10px;">
                {html.escape(code)} 诊断建议
            </h3>
            <div style="color: {TEXT_PRIMARY}; line-height: 1.7; font-size: 14px;">
                {rendered}
            </div>
        </div>
        """
        # 追加到浏览器
        cursor = self.ai_browser.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(new_section)
        self.ai_browser.ensureCursorVisible()

    def _build_single_code_section(self, result: DiagnosticResult, index: int) -> str:
        """构建单个故障码的知识库 HTML 区块"""
        kb = result.knowledge
        severity = kb.get("severity", "medium")
        sev = SEVERITY_STYLES.get(severity, SEVERITY_STYLES["medium"])
        desc = html.escape(kb.get("description", ""))
        
        return f"""
        <div style="margin-bottom: 20px; padding: 16px; 
                    background: white; border-radius: 8px; 
                    border: 1px solid {CARD_BORDER};">
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
                <span style="font-family: Consolas; font-size: 24px; font-weight: bold; color: {TEXT_PRIMARY};">
                    {html.escape(result.code)}
                </span>
                <span style="background-color: {sev['bg']}; color: {sev['text']};
                             font-size: 11px; font-weight: bold; padding: 2px 8px;
                             border-radius: 4px; border: 1px solid {sev['border']};">
                    {sev['label']}
                </span>
            </div>
            <div style="font-size: 14px; color: {TEXT_SECONDARY}; margin-bottom: 8px;">
                {desc}
            </div>
        </div>
        """

    def _build_not_found_section(self, result: DiagnosticResult, index: int) -> str:
        """构建未找到故障码的区块"""
        return f"""
        <div style="margin-bottom: 16px; padding: 12px; 
                    background: #FFF3E0; border-radius: 8px;
                    border: 1px solid #FFE0B2;">
            <span style="font-family: Consolas; font-weight: bold;">{html.escape(result.code)}</span>
            <span style="color: #E65100; margin-left: 8px;">未在知识库中找到</span>
        </div>
        """

    def _build_multi_overview_html(self, codes: list, correlation) -> str:
        """构建多码概览 HTML"""
        html_parts = [f"""
        <div style="font-family: 'Microsoft YaHei UI', Consolas, sans-serif;">
            <div style="margin-bottom: 16px;">
                <h2 style="color: {TEXT_PRIMARY}; font-size: 18px; margin-bottom: 8px;">
                    多故障码诊断
                </h2>
                <div style="font-size: 13px; color: {TEXT_SECONDARY};">
                    共 {len(codes)} 个故障码
                </div>
            </div>
        """]
        
        # 关联性状态
        if correlation.is_correlated:
            html_parts.append(f"""
            <div style="padding: 10px 14px; background: #E8F5E9; border-radius: 6px;
                        border: 1px solid #A5D6A7; margin-bottom: 16px;">
                <span style="color: #2E7D32; font-weight: bold;">✅ 关联故障</span>
                <span style="color: #388E3C; font-size: 13px; margin-left: 8px;">
                    {correlation.analysis_summary}
                </span>
            </div>
            """)
        else:
            html_parts.append(f"""
            <div style="padding: 10px 14px; background: #FFF3E0; border-radius: 6px;
                        border: 1px solid #FFE0B2; margin-bottom: 16px;">
                <span style="color: #E65100; font-weight: bold;">⚠️ 独立故障</span>
                <span style="color: #F57C00; font-size: 13px; margin-left: 8px;">
                    {correlation.analysis_summary}
                </span>
            </div>
            """)
        
        # 码列表
        for i, code in enumerate(codes, 1):
            html_parts.append(f"""
            <div style="padding: 8px 12px; margin-bottom: 4px; 
                        background: {CARD_BG}; border-radius: 6px;
                        border: 1px solid {CARD_BORDER};">
                <span style="font-family: Consolas; font-weight: bold;">{i}. {html.escape(code)}</span>
                <span style="color: {TEXT_MUTED}; font-size: 12px; margin-left: 8px;">加载中...</span>
            </div>
            """)
        
        html_parts.append("</div>")
        return "".join(html_parts)
