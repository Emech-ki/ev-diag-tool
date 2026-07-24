"""
诊断结果面板
显示知识库信息和 AI 诊断建议
"""

import html
import json
import re

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextBrowser, QFrame, QSplitter, QLineEdit, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor

from src.engine.diagnostic import DiagnosticResult
from src.engine.knowledge_base import KnowledgeBase
from src.ui.styles import (
    PRIMARY, PRIMARY_DARK, PRIMARY_BG, CARD_BG, CARD_BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, BG, FONT_MONO,
    SEVERITY_STYLES, WARNING, WARNING_BG
)


class ResultPanel(QWidget):
    """诊断结果展示面板"""

    diagnose_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.kb = KnowledgeBase()
        self._current_code = None
        self._ai_stream_started = False
        self._ai_stream_content = ""
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

        self.knowledge_browser = QTextBrowser()
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
            code = url.path().strip("/")
            if code:
                self.diagnose_requested.emit(code)

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

    def show_result(self, result: DiagnosticResult):
        """显示诊断结果"""
        self.clear()

        self._current_code = result.code if result.has_knowledge() else None
        self._refresh_symptoms_display()

        if result.has_knowledge():
            html = self._build_knowledge_html(result)
        else:
            html = self._build_not_found_html(result)

        self.knowledge_browser.setHtml(html)

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

        self._current_code = result.code if result.has_knowledge() else None
        self._refresh_symptoms_display()

        if result.has_knowledge():
            html = self._build_knowledge_html(result)
        else:
            html = self._build_not_found_html(result)

        self.knowledge_browser.setHtml(html)

        if result.ai_available:
            self._show_ai_loading()
        else:
            self._show_ai_unavailable()

    def show_lookup_result(self, result: DiagnosticResult):
        """快速查询展示（用于相关码跳转），只显示知识库，不显示 AI 状态"""
        self.clear()

        self._current_code = result.code if result.has_knowledge() else None
        self._refresh_symptoms_display()

        if result.has_knowledge():
            html = self._build_knowledge_html(result)
        else:
            html = self._build_not_found_html(result)

        self.knowledge_browser.setHtml(html)

    def append_ai_text(self, token: str):
        """追加 AI 流式 token 到 AI 浏览器"""
        if not self._ai_stream_started:
            self.ai_browser.clear()
            self._ai_stream_started = True
            self._ai_stream_content = ""

        self._ai_stream_content += token
        escaped = token.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        escaped = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', escaped)
        escaped = escaped.replace('\n', '<br>')

        cursor = self.ai_browser.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(escaped)
        self.ai_browser.ensureCursorVisible()

    def finalize_ai_suggestion(self, code: str, full_text: str, timestamp: str = ""):
        """AI 流式完成，重建完整格式化的 HTML"""
        if not full_text:
            return

        suggestion = html.escape(full_text)
        suggestion = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', suggestion)
        suggestion = suggestion.replace('\n', '<br>')

        self.ai_browser.setHtml(f"""
            <div style="font-family: 'Microsoft YaHei UI', sans-serif;">
                <div style="color: {TEXT_SECONDARY}; font-size: 12px; margin-bottom: 12px;">
                    基于 {code} + 车型/症状信息生成
                    <span style="float: right;">{timestamp}</span>
                </div>
                <div style="color: {TEXT_PRIMARY}; line-height: 1.7; font-size: 14px;">
                    {suggestion}
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

        desc = kb.get("description", "")
        sys = self.kb.get_system_info(kb.get("system", ""))["name"]

        html = f"""
        <div style="font-family: 'Microsoft YaHei UI', Consolas, sans-serif;">"""

        html += f"""
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 4px;">
                <span style="font-family: Consolas; font-size: 32px; font-weight: bold; color: {TEXT_PRIMARY};">
                    {result.code}
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
                <span>系统: {sys}</span>
                <span>类型: {kb.get('code_type', '通用')}</span>
            </div>

            <div style="height: 1px; background-color: {CARD_BORDER}; margin-bottom: 14px;"></div>
        """

        detail = kb.get("detail", "")
        if detail:
            html += f"""
            <div style="margin-bottom: 14px;">
                <div style="font-size: 13px; font-weight: bold; color: {TEXT_PRIMARY}; margin-bottom: 6px;">详细说明</div>
                <div style="font-size: 14px; color: {TEXT_SECONDARY}; line-height: 1.7;">{detail}</div>
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
                f'<li style="margin: 6px 0; padding-left: 4px; color: {TEXT_SECONDARY};">{c}</li>'
                for c in causes
            )
            html += f"""
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
            items = "".join(
                f'<li style="margin: 8px 0; padding-left: 4px; color: {TEXT_SECONDARY}; line-height: 1.6;">{s}</li>'
                for s in steps
            )
            html += f"""
            <div style="margin-bottom: 14px;">
                <div style="font-size: 13px; font-weight: bold; color: {TEXT_PRIMARY}; margin-bottom: 6px;">诊断步骤</div>
                <ol style="margin: 0; padding-left: 20px;">{items}</ol>
            </div>
            """

        related = kb.get("related_codes", [])
        if isinstance(related, str):
            related = [r.strip() for r in related.split(",") if r.strip()]
        if related:
            chips = " ".join(
                f'<a href="dtc://{r}" style="text-decoration: none; '
                f'background-color: {PRIMARY_BG}; color: {PRIMARY}; '
                f'font-family: Consolas; font-size: 12px; padding: 2px 10px; border-radius: 4px;">{r}</a>'
                for r in related
            )
            html += f"""
            <div style="height: 1px; background-color: {CARD_BORDER}; margin-bottom: 10px;"></div>
            <div style="margin-bottom: 4px;">
                <div style="font-size: 13px; font-weight: bold; color: {TEXT_PRIMARY}; margin-bottom: 6px;">相关故障码</div>
                <div>{chips}</div>
            </div>
            """

        html += "</div>"
        return html

    def _build_not_found_html(self, result: DiagnosticResult) -> str:
        """构建未找到故障码的 HTML"""
        return f"""
        <div style="text-align: center; margin-top: 60px;
                    font-family: 'Microsoft YaHei UI', sans-serif;">
            <div style="font-size: 48px; margin-bottom: 12px; color: {CARD_BORDER};">?</div>
            <div style="font-size: 20px; font-weight: bold; color: {TEXT_PRIMARY}; margin-bottom: 8px;">
                未找到故障码 "{result.code}"
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
        suggestion = html.escape(suggestion)
        suggestion = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', suggestion)
        suggestion = suggestion.replace('\n', '<br>')

        return f"""
        <div style="font-family: 'Microsoft YaHei UI', sans-serif;">
            <div style="color: {TEXT_SECONDARY}; font-size: 12px; margin-bottom: 12px;">
                基于 {result.code} + 车型/症状信息生成
                <span style="float: right;">{result.timestamp}</span>
            </div>
            <div style="color: {TEXT_PRIMARY}; line-height: 1.7; font-size: 14px;">
                {suggestion}
            </div>
            <div style="margin-top: 16px; padding: 10px 14px; background-color: {WARNING_BG};
                        border-radius: 6px; font-size: 12px; color: {WARNING};">
                AI 建议仅供参考，请结合实际情况和专业判断做出维修决策。
            </div>
        </div>
        """
