"""
Markdown → HTML 渲染器
支持 LLM 输出常用的 Markdown 子集：标题、粗体、斜体、行内代码、代码块、列表、引用、链接、分隔线
"""

import html as html_mod
import re

# 预编译正则
_RE_CODE_FENCE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
_RE_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_RE_HEADER = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
_RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_RE_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_RE_STRIKETHROUGH = re.compile(r"~~(.+?)~~")
_RE_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_RE_HR = re.compile(r"^[-*_]{3,}\s*$", re.MULTILINE)
_RE_BLOCKQUOTE = re.compile(r"^&gt;\s?(.*)$", re.MULTILINE)
_RE_UNORDERED_LIST = re.compile(r"^(\s*)[-*+]\s+(.*)$", re.MULTILINE)
_RE_ORDERED_LIST = re.compile(r"^(\s*)\d+\.\s+(.*)$", re.MULTILINE)


def md_to_html(text: str) -> str:
    """
    将 Markdown 文本转换为 HTML

    支持的语法：
    - 标题: # H1, ## H2, ### H3
    - 粗体: **text**
    - 斜体: *text*
    - 删除线: ~~text~~
    - 行内代码: `code`
    - 代码块: ```lang ... ```
    - 无序列表: - item, * item
    - 有序列表: 1. item
    - 引用: > text
    - 链接: [text](url)
    - 分隔线: ---, ***, ___
    - 换行: \n → <br>

    Args:
        text: 原始 Markdown 文本

    Returns:
        HTML 字符串
    """
    if not text:
        return ""

    # 1. HTML 转义（保护代码块内容不被后续处理影响）
    text = html_mod.escape(text)

    # 2. 代码块（```）— 先处理，避免代码块内的其他语法被转换
    code_blocks = []

    def _replace_code_block(m):
        lang = m.group(1) or ""
        code = m.group(2)
        idx = len(code_blocks)
        code_blocks.append((lang, code))
        return f"__CODE_BLOCK_{idx}__"

    text = _RE_CODE_FENCE.sub(_replace_code_block, text)

    # 3. 行内代码（`）
    inline_codes = []

    def _replace_inline_code(m):
        code = m.group(1)
        idx = len(inline_codes)
        inline_codes.append(code)
        return f"__INLINE_CODE_{idx}__"

    text = _RE_INLINE_CODE.sub(_replace_inline_code, text)

    # 4. 标题
    text = _RE_HEADER.sub(lambda m: f'<h{len(m.group(1))} style="{_header_style(len(m.group(1)))}">{m.group(2)}</h{len(m.group(1))}>', text)

    # 5. 粗体
    text = _RE_BOLD.sub(r"<strong>\1</strong>", text)

    # 6. 斜体
    text = _RE_ITALIC.sub(r"<em>\1</em>", text)

    # 7. 删除线
    text = _RE_STRIKETHROUGH.sub(r"<del>\1</del>", text)

    # 8. 链接（只允许 http/https 等安全协议，防止 javascript: 等注入）
    def _safe_link(m):
        url = m.group(2)
        if re.match(r'^(https?|dtc)://', url, re.IGNORECASE):
            return f'<a href="{url}" style="color: #1565C0; text-decoration: none;">{m.group(1)}</a>'
        return m.group(1)
    text = _RE_LINK.sub(_safe_link, text)

    # 9. 分隔线
    text = _RE_HR.sub('<hr style="border: none; border-top: 1px solid #E0E0E0; margin: 12px 0;">', text)

    # 10. 引用
    text = _RE_BLOCKQUOTE.sub(
        lambda m: f'<blockquote style="border-left: 3px solid #1565C0; padding-left: 12px; color: #555; margin: 8px 0;">{m.group(1)}</blockquote>',
        text
    )

    # 11. 列表（按行处理，避免跨类型嵌套问题）
    lines = text.split("\n")
    result_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # 检查无序列表
        ul_match = re.match(r"^(\s*)[-*+]\s+(.*)$", line)
        if ul_match:
            items = []
            while i < len(lines) and re.match(r"^(\s*)[-*+]\s+(.*)$", lines[i]):
                items.append(re.match(r"^(\s*)[-*+]\s+(.*)$", lines[i]).group(2))
                i += 1
            lis = "".join(f"<li>{item}</li>" for item in items)
            result_lines.append(f"<ul style='padding-left: 20px; margin: 4px 0;'>{lis}</ul>")
            continue
        # 检查有序列表
        ol_match = re.match(r"^(\s*)\d+\.\s+(.*)$", line)
        if ol_match:
            items = []
            while i < len(lines) and re.match(r"^(\s*)\d+\.\s+(.*)$", lines[i]):
                items.append(re.match(r"^(\s*)\d+\.\s+(.*)$", lines[i]).group(2))
                i += 1
            lis = "".join(f"<li>{item}</li>" for item in items)
            result_lines.append(f"<ol style='padding-left: 20px; margin: 4px 0;'>{lis}</ol>")
            continue
        result_lines.append(line)
        i += 1
    text = "\n".join(result_lines)

    # 12. 换行
    text = text.replace("\n", "<br>")

    # 14. 还原代码块
    from src.ui.styles import get_token
    code_bg = get_token("INPUT_BG")
    code_border = get_token("CARD_BORDER")
    for idx, (lang, code) in enumerate(code_blocks):
        lang_label = f'<span style="font-size: 11px; color: {get_token("TEXT_MUTED")};">{lang}</span><br>' if lang else ""
        block_html = (
            f'<div style="background: {code_bg}; border: 1px solid {code_border}; border-radius: 6px; '
            f'padding: 10px 14px; margin: 8px 0; font-family: Consolas, monospace; font-size: 13px; '
            f'line-height: 1.5; overflow-x: auto; color: {get_token("TEXT_PRIMARY")};">'
            f'{lang_label}{code}</div>'
        )
        text = text.replace(f"__CODE_BLOCK_{idx}__", block_html)

    # 15. 还原行内代码
    inline_bg = get_token("INPUT_BG")
    for idx, code in enumerate(inline_codes):
        inline_html = (
            f'<code style="background: {inline_bg}; padding: 1px 5px; border-radius: 3px; '
            f'font-family: Consolas, monospace; font-size: 13px; color: {get_token("TEXT_PRIMARY")};">{code}</code>'
        )
        text = text.replace(f"__INLINE_CODE_{idx}__", inline_html)

    return text


def _header_style(level: int) -> str:
    """标题样式"""
    if level == 1:
        return "font-size: 18px; font-weight: bold; color: #1565C0; margin: 12px 0 8px 0;"
    elif level == 2:
        return "font-size: 16px; font-weight: bold; color: #333; margin: 10px 0 6px 0;"
    else:
        return "font-size: 14px; font-weight: bold; color: #555; margin: 8px 0 4px 0;"


def md_to_plain_text(text: str) -> str:
    """
    将 Markdown 文本转换为纯文本（用于 txt 导出）

    去除 Markdown 标记，保留内容文字
    """
    if not text:
        return ""

    # 代码块 → 保留内容
    text = re.sub(r"```(\w*)\n(.*?)```", lambda m: m.group(2), text, flags=re.DOTALL)
    # 行内代码 → 去反引号
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # 标题 → 去 # 号
    text = re.sub(r"^#{1,3}\s+", "", text, flags=re.MULTILINE)
    # 粗体
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # 斜体
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    # 删除线
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    # 链接
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # 分隔线
    text = re.sub(r"^[-*_]{3,}\s*$", "-" * 40, text, flags=re.MULTILINE)
    # 引用
    text = re.sub(r"^>\s?", "  ", text, flags=re.MULTILINE)

    return text
