"""
诊断结果导出工具
支持导出为纯文本和 HTML 格式
"""

import html as html_mod
import json
from typing import Optional, Dict, Any

from src.ui.markdown_renderer import md_to_html, md_to_plain_text


def _parse_json_field(value) -> list:
    """解析 JSON 字段（兼容字符串和列表）"""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return []


def _parse_related_codes(value) -> list:
    """解析相关故障码（兼容逗号分隔和 JSON 格式）"""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # 尝试 JSON
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        # 逗号分隔
        return [r.strip() for r in value.split(",") if r.strip()]
    return []


def _get_severity_label(severity: str) -> str:
    """严重程度中文标签"""
    return {"low": "低", "medium": "中", "high": "高", "critical": "严重"}.get(severity, severity)


def export_as_text(
    code: str,
    knowledge: Optional[Dict[str, Any]] = None,
    ai_suggestion: Optional[str] = None,
    vehicle_info: str = "",
    symptoms: str = "",
    timestamp: str = "",
) -> str:
    """
    生成纯文本诊断报告

    Args:
        code: 故障码
        knowledge: 知识库数据字典
        ai_suggestion: AI 建议文本
        vehicle_info: 车型信息
        symptoms: 症状描述
        timestamp: 诊断时间

    Returns:
        纯文本报告内容
    """
    lines = []
    lines.append("=" * 50)
    lines.append("EV-Diag-Tool 诊断报告")
    lines.append("=" * 50)
    lines.append("")
    lines.append(f"故障码：{code}")

    if knowledge:
        severity = knowledge.get("severity", "")
        if severity:
            lines.append(f"严重程度：{_get_severity_label(severity)}")
        system = knowledge.get("system", "")
        if system:
            lines.append(f"系统：{system}")

    if vehicle_info:
        lines.append(f"车型：{vehicle_info}")
    if symptoms:
        lines.append(f"症状描述：{symptoms}")
    if timestamp:
        lines.append(f"诊断时间：{timestamp}")
    lines.append("")

    # 知识库部分
    if knowledge:
        description = knowledge.get("description", "")
        detail = knowledge.get("detail", "")
        causes = _parse_json_field(knowledge.get("common_causes", []))
        steps = _parse_json_field(knowledge.get("diagnostic_steps", []))
        related = _parse_related_codes(knowledge.get("related_codes", []))

        if description:
            lines.append("-" * 50)
            lines.append(f"[知识库] 故障描述")
            lines.append("-" * 50)
            lines.append(description)
            lines.append("")

        if detail:
            lines.append("-" * 50)
            lines.append("[知识库] 详细说明")
            lines.append("-" * 50)
            lines.append(detail)
            lines.append("")

        if causes:
            lines.append("-" * 50)
            lines.append("[知识库] 常见原因")
            lines.append("-" * 50)
            for i, cause in enumerate(causes, 1):
                lines.append(f"  {i}. {cause}")
            lines.append("")

        if steps:
            lines.append("-" * 50)
            lines.append("[知识库] 诊断步骤")
            lines.append("-" * 50)
            for i, step in enumerate(steps, 1):
                lines.append(f"  {i}. {step}")
            lines.append("")

        if related:
            lines.append("-" * 50)
            lines.append("[知识库] 相关故障码")
            lines.append("-" * 50)
            lines.append("  " + ", ".join(related))
            lines.append("")

    # AI 建议部分
    if ai_suggestion:
        lines.append("-" * 50)
        lines.append("[AI 建议] 仅供参考")
        lines.append("-" * 50)
        lines.append(md_to_plain_text(ai_suggestion))
        lines.append("")

    lines.append("=" * 50)
    lines.append("本报告由 EV-Diag-Tool 生成")
    lines.append("AI 建议仅供参考，请结合实际情况判断")
    lines.append("=" * 50)

    return "\n".join(lines)


def export_as_html(
    code: str,
    knowledge: Optional[Dict[str, Any]] = None,
    ai_suggestion: Optional[str] = None,
    vehicle_info: str = "",
    symptoms: str = "",
    timestamp: str = "",
) -> str:
    """
    生成 HTML 诊断报告（带内联 CSS，可直接浏览器打开/打印为 PDF）

    Returns:
        完整 HTML 文档字符串
    """
    # 构建内容块
    content = ""

    # 头部信息
    content += f"""
    <div class="header">
        <h1>EV-Diag-Tool 诊断报告</h1>
        <table class="meta-table">
            <tr><td class="label">故障码</td><td class="code">{html_mod.escape(code)}</td></tr>
    """
    if knowledge:
        severity = knowledge.get("severity", "")
        if severity:
            # 严重程度进入 HTML class 属性，必须先转义防止属性注入
            sev_class = f"severity-{html_mod.escape(severity)}"
            content += f'<tr><td class="label">严重程度</td><td><span class="{sev_class}">{_get_severity_label(severity)}</span></td></tr>\n'
        system = knowledge.get("system", "")
        if system:
            content += f'<tr><td class="label">系统</td><td>{html_mod.escape(system)}</td></tr>\n'
    if vehicle_info:
        content += f'<tr><td class="label">车型</td><td>{html_mod.escape(vehicle_info)}</td></tr>\n'
    if symptoms:
        content += f'<tr><td class="label">症状描述</td><td>{html_mod.escape(symptoms)}</td></tr>\n'
    if timestamp:
        content += f'<tr><td class="label">诊断时间</td><td>{html_mod.escape(timestamp)}</td></tr>\n'
    content += "</table></div>\n"

    # 知识库部分
    if knowledge:
        description = knowledge.get("description", "")
        detail = knowledge.get("detail", "")
        causes = _parse_json_field(knowledge.get("common_causes", []))
        steps = _parse_json_field(knowledge.get("diagnostic_steps", []))
        related = _parse_related_codes(knowledge.get("related_codes", []))

        if description:
            content += f"""
            <div class="section">
                <h2>故障描述</h2>
                <p>{html_mod.escape(description)}</p>
            </div>
            """

        if detail:
            content += f"""
            <div class="section">
                <h2>详细说明</h2>
                <p>{html_mod.escape(detail)}</p>
            </div>
            """

        if causes:
            items = "".join(f"<li>{html_mod.escape(c)}</li>" for c in causes)
            content += f"""
            <div class="section">
                <h2>常见原因</h2>
                <ol>{items}</ol>
            </div>
            """

        if steps:
            items = "".join(f"<li>{html_mod.escape(s)}</li>" for s in steps)
            content += f"""
            <div class="section">
                <h2>诊断步骤</h2>
                <ol>{items}</ol>
            </div>
            """

        if related:
            chips = " ".join(f'<span class="chip">{html_mod.escape(r)}</span>' for r in related)
            content += f"""
            <div class="section">
                <h2>相关故障码</h2>
                <div>{chips}</div>
            </div>
            """

    # AI 建议部分
    if ai_suggestion:
        rendered = md_to_html(ai_suggestion)
        content += f"""
        <div class="section ai-section">
            <h2>AI 建议 <span class="ai-badge">仅供参考</span></h2>
            <div class="ai-content">{rendered}</div>
        </div>
        """

    # 组装完整 HTML
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>诊断报告 - {html_mod.escape(code)}</title>
    <style>
        body {{
            font-family: "Microsoft YaHei UI", "PingFang SC", sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 40px 20px;
            color: #1A1A2E;
            line-height: 1.7;
            background: #fff;
        }}
        h1 {{
            font-size: 24px;
            color: #1565C0;
            border-bottom: 2px solid #1565C0;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        h2 {{
            font-size: 16px;
            color: #333;
            margin: 16px 0 10px 0;
            padding-bottom: 6px;
            border-bottom: 1px solid #eee;
        }}
        .meta-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        .meta-table td {{
            padding: 8px 12px;
            border: 1px solid #eee;
        }}
        .meta-table .label {{
            width: 100px;
            font-weight: bold;
            background: #f5f5f5;
            color: #555;
        }}
        .code {{
            font-family: Consolas, monospace;
            font-size: 18px;
            font-weight: bold;
            color: #1565C0;
        }}
        .severity-low {{ color: #2E7D32; font-weight: bold; }}
        .severity-medium {{ color: #E65100; font-weight: bold; }}
        .severity-high {{ color: #C62828; font-weight: bold; }}
        .severity-critical {{ color: #7B1FA2; font-weight: bold; }}
        .section {{
            margin-bottom: 24px;
        }}
        .section ol {{
            padding-left: 24px;
        }}
        .section li {{
            margin: 6px 0;
        }}
        .chip {{
            display: inline-block;
            font-family: Consolas, monospace;
            font-size: 13px;
            background: #E3F2FD;
            color: #1565C0;
            padding: 2px 10px;
            border-radius: 4px;
            margin: 2px 4px 2px 0;
        }}
        .ai-section {{
            background: #FFF8E1;
            border: 1px solid #FFE082;
            border-radius: 8px;
            padding: 16px 20px;
        }}
        .ai-badge {{
            font-size: 12px;
            color: #E65100;
            font-weight: normal;
            background: #FFF3E0;
            padding: 2px 8px;
            border-radius: 4px;
        }}
        .ai-content {{
            color: #333;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 16px;
            border-top: 1px solid #eee;
            font-size: 12px;
            color: #999;
            text-align: center;
        }}
        @media print {{
            body {{ padding: 20px; }}
            .ai-section {{ break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    {content}
    <div class="footer">
        本报告由 EV-Diag-Tool 生成 | AI 建议仅供参考，请结合实际情况判断
    </div>
</body>
</html>"""


def export_as_pdf(
    code: str,
    knowledge: Optional[Dict[str, Any]] = None,
    ai_suggestion: Optional[str] = None,
    vehicle_info: str = "",
    symptoms: str = "",
    timestamp: str = "",
) -> bytes:
    """
    生成 PDF 诊断报告（reportlab，中文字体自动回退系统常见字体）

    Returns:
        PDF 二进制内容
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.pdfmetrics import registerFontFamily

    import io
    import os

    # 中文字体：按常见性回退（Windows / macOS / Linux）
    _CJK_FONT = None
    candidates = [
        ("msyh", "C:/Windows/Fonts/msyh.ttc"),
        ("simhei", "C:/Windows/Fonts/simhei.ttf"),
        ("simsun", "C:/Windows/Fonts/simsun.ttc"),
        ("pingfang", "/System/Library/Fonts/PingFang.ttc"),
        ("noto", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        ("wenquanyi", "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
    ]
    for name, path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                _CJK_FONT = name
                break
            except Exception:
                continue
    if _CJK_FONT is None:
        _CJK_FONT = "Helvetica"

    registerFontFamily(
        _CJK_FONT,
        normal=_CJK_FONT,
        bold=_CJK_FONT,
        italic=_CJK_FONT,
        boldItalic=_CJK_FONT,
    )

    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName=_CJK_FONT,
        fontSize=10,
        leading=15,
        wordWrap="CJK",
    )
    h1_style = ParagraphStyle(
        "H1CJK",
        parent=styles["Title"],
        fontName=_CJK_FONT,
        fontSize=18,
        leading=24,
        textColor=colors.HexColor("#1565C0"),
        spaceAfter=6,
    )
    h2_style = ParagraphStyle(
        "H2CJK",
        parent=styles["Heading2"],
        fontName=_CJK_FONT,
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#333333"),
        spaceBefore=10,
        spaceAfter=4,
    )
    small_style = ParagraphStyle(
        "Small",
        parent=styles["Normal"],
        fontName=_CJK_FONT,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#888888"),
        alignment=TA_CENTER,
    )

    def esc(text: str) -> str:
        """reportlab Paragraph 使用 XML 转义"""
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"诊断报告 - {code}",
        author="EV-Diag-Tool",
    )
    story = []

    # 标题 + 分隔线
    story.append(Paragraph("EV-Diag-Tool 诊断报告", h1_style))
    story.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor("#1565C0")))

    # 元信息表
    meta = [("故障码", code)]
    if knowledge:
        severity = knowledge.get("severity", "")
        if severity:
            meta.append(("严重程度", _get_severity_label(severity)))
        system = knowledge.get("system", "")
        if system:
            meta.append(("系统", system))
    if vehicle_info:
        meta.append(("车型", vehicle_info))
    if symptoms:
        meta.append(("症状描述", symptoms))
    if timestamp:
        meta.append(("诊断时间", timestamp))

    meta_rows = [[Paragraph(esc(k), ParagraphStyle(
        "MetaLabel", parent=body_style, fontName=_CJK_FONT, textColor=colors.HexColor("#555555"),
        fontSize=9, leading=13, alignment=TA_CENTER,
    )), Paragraph(esc(v), body_style)] for k, v in meta]
    if meta_rows:
        meta_table = Table(meta_rows, colWidths=[28 * mm, None])
        meta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F5F5F5")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(Spacer(1, 4))
        story.append(meta_table)
        story.append(Spacer(1, 8))

    # 知识库部分
    if knowledge:
        description = knowledge.get("description", "")
        detail = knowledge.get("detail", "")
        causes = _parse_json_field(knowledge.get("common_causes", []))
        steps = _parse_json_field(knowledge.get("diagnostic_steps", []))
        related = _parse_related_codes(knowledge.get("related_codes", []))

        if description:
            story.append(Paragraph("故障描述", h2_style))
            story.append(Paragraph(esc(description), body_style))
        if detail:
            story.append(Paragraph("详细说明", h2_style))
            story.append(Paragraph(esc(detail), body_style))
        if causes:
            story.append(Paragraph("常见原因", h2_style))
            for i, c in enumerate(causes, 1):
                story.append(Paragraph(f"{i}.&nbsp; {esc(c)}", body_style))
        if steps:
            story.append(Paragraph("诊断步骤", h2_style))
            for i, s in enumerate(steps, 1):
                story.append(Paragraph(f"{i}.&nbsp; {esc(s)}", body_style))
        if related:
            story.append(Paragraph("相关故障码", h2_style))
            story.append(Paragraph(esc("  ".join(related)), body_style))

    # AI 建议部分
    if ai_suggestion:
        story.append(Paragraph("AI 建议（仅供参考）", h2_style))
        plain = md_to_plain_text(ai_suggestion)
        for line in plain.split("\n"):
            line = line.strip()
            if not line:
                continue
            story.append(Paragraph(esc(line), body_style))

    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CCCCCC")))
    story.append(Spacer(1, 6))
    story.append(Paragraph("本报告由 EV-Diag-Tool 生成 | AI 建议仅供参考，请结合实际情况判断", small_style))

    doc.build(story)
    return buf.getvalue()


