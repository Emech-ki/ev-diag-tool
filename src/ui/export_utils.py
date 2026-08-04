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


def export_multi_as_text(
    codes: list,
    correlation,
    results: list,
    combined_ai: Optional[str] = None,
    vehicle_info: str = "",
    symptoms: str = "",
    timestamp: str = "",
) -> str:
    """
    生成多故障码纯文本诊断报告

    Args:
        codes: 故障码列表
        correlation: CorrelationResult 对象
        results: DiagnosticResult 列表
        combined_ai: 综合 AI 建议文本
        vehicle_info: 车型信息
        symptoms: 症状描述
        timestamp: 诊断时间

    Returns:
        纯文本报告内容
    """
    lines = []
    lines.append("=" * 60)
    lines.append("EV-Diag-Tool 多故障码诊断报告")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"故障码：{', '.join(codes)}")

    if vehicle_info:
        lines.append(f"车型：{vehicle_info}")
    if symptoms:
        lines.append(f"症状描述：{symptoms}")
    if timestamp:
        lines.append(f"诊断时间：{timestamp}")

    # 关联性分析
    lines.append("")
    lines.append("-" * 60)
    lines.append("[关联性分析]")
    lines.append("-" * 60)
    lines.append(correlation.analysis_summary)
    lines.append("")

    # 逐码信息
    for i, (code, result) in enumerate(zip(codes, results), 1):
        lines.append("-" * 60)
        lines.append(f"[故障码 {i}] {code}")
        lines.append("-" * 60)
        
        if result and result.knowledge:
            kb = result.knowledge
            description = kb.get("description", "")
            if description:
                lines.append(f"描述: {description}")
            
            severity = kb.get("severity", "")
            if severity:
                lines.append(f"严重程度: {_get_severity_label(severity)}")
            
            system = kb.get("system", "")
            if system:
                lines.append(f"系统: {system}")
            
            causes = _parse_json_field(kb.get("common_causes", []))
            if causes:
                lines.append("常见原因:")
                for j, cause in enumerate(causes, 1):
                    lines.append(f"  {j}. {cause}")
            
            steps = _parse_json_field(kb.get("diagnostic_steps", []))
            if steps:
                lines.append("诊断步骤:")
                for j, step in enumerate(steps, 1):
                    lines.append(f"  {j}. {step}")
        else:
            lines.append("未在知识库中找到")
        
        lines.append("")

    # 综合 AI 建议
    if combined_ai:
        lines.append("-" * 60)
        lines.append("[AI 综合建议] 仅供参考")
        lines.append("-" * 60)
        lines.append(md_to_plain_text(combined_ai))
        lines.append("")

    lines.append("=" * 60)
    lines.append("本报告由 EV-Diag-Tool 生成")
    lines.append("AI 建议仅供参考，请结合实际情况判断")
    lines.append("=" * 60)

    return "\n".join(lines)


def export_multi_as_html(
    codes: list,
    correlation,
    results: list,
    combined_ai: Optional[str] = None,
    vehicle_info: str = "",
    symptoms: str = "",
    timestamp: str = "",
) -> str:
    """
    生成多故障码 HTML 诊断报告

    Returns:
        完整 HTML 文档字符串
    """
    # 构建内容块
    content = ""

    # 头部信息
    codes_str = ", ".join(codes)
    content += f"""
    <div class="header">
        <h1>EV-Diag-Tool 多故障码诊断报告</h1>
        <table class="meta-table">
            <tr><td class="label">故障码</td><td class="code">{html_mod.escape(codes_str)}</td></tr>
    """
    if vehicle_info:
        content += f'<tr><td class="label">车型</td><td>{html_mod.escape(vehicle_info)}</td></tr>\n'
    if symptoms:
        content += f'<tr><td class="label">症状描述</td><td>{html_mod.escape(symptoms)}</td></tr>\n'
    if timestamp:
        content += f'<tr><td class="label">诊断时间</td><td>{html_mod.escape(timestamp)}</td></tr>\n'
    content += "</table></div>\n"

    # 关联性分析
    if correlation.is_correlated:
        content += f"""
        <div class="section correlation-section correlated">
            <h2>✅ 关联故障</h2>
            <p>{html_mod.escape(correlation.analysis_summary)}</p>
        </div>
        """
    else:
        content += f"""
        <div class="section correlation-section independent">
            <h2>⚠️ 独立故障</h2>
            <p>{html_mod.escape(correlation.analysis_summary)}</p>
        </div>
        """

    # 逐码信息
    for i, (code, result) in enumerate(zip(codes, results), 1):
        content += f'<div class="code-section">\n'
        content += f'<h2>故障码 {i}: {html_mod.escape(code)}</h2>\n'
        
        if result and result.knowledge:
            kb = result.knowledge
            description = kb.get("description", "")
            severity = kb.get("severity", "")
            system = kb.get("system", "")
            
            if description:
                content += f'<p><strong>描述:</strong> {html_mod.escape(description)}</p>\n'
            if severity:
                sev_class = f"severity-{severity}"
                content += f'<p><strong>严重程度:</strong> <span class="{sev_class}">{_get_severity_label(severity)}</span></p>\n'
            if system:
                content += f'<p><strong>系统:</strong> {html_mod.escape(system)}</p>\n'
            
            causes = _parse_json_field(kb.get("common_causes", []))
            if causes:
                items = "".join(f"<li>{html_mod.escape(c)}</li>" for c in causes)
                content += f'<h3>常见原因</h3><ol>{items}</ol>\n'
            
            steps = _parse_json_field(kb.get("diagnostic_steps", []))
            if steps:
                items = "".join(f"<li>{html_mod.escape(s)}</li>" for s in steps)
                content += f'<h3>诊断步骤</h3><ol>{items}</ol>\n'
        else:
            content += '<p style="color: #E65100;">未在知识库中找到</p>\n'
        
        content += '</div>\n'

    # 综合 AI 建议
    if combined_ai:
        rendered = md_to_html(combined_ai)
        content += f"""
        <div class="section ai-section">
            <h2>AI 综合建议 <span class="ai-badge">仅供参考</span></h2>
            <div class="ai-content">{rendered}</div>
        </div>
        """

    # 组装完整 HTML
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>多故障码诊断报告 - {html_mod.escape(codes_str)}</title>
    <style>
        body {{
            font-family: "Microsoft YaHei UI", "PingFang SC", sans-serif;
            max-width: 900px;
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
            font-size: 18px;
            color: #333;
            margin: 16px 0 10px 0;
            padding-bottom: 6px;
            border-bottom: 1px solid #eee;
        }}
        h3 {{
            font-size: 15px;
            color: #555;
            margin: 12px 0 8px 0;
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
            font-size: 16px;
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
        .code-section {{
            background: #FAFAFA;
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 16px;
        }}
        .correlation-section {{
            padding: 12px 16px;
            border-radius: 6px;
            margin-bottom: 20px;
        }}
        .correlated {{
            background: #E8F5E9;
            border: 1px solid #A5D6A7;
        }}
        .independent {{
            background: #FFF3E0;
            border: 1px solid #FFE0B2;
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
