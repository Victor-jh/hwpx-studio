#!/usr/bin/env python3
"""html_preview.py — HWPX → HTML 미리보기.

HWPX 문서를 읽어 브라우저에서 바로 확인할 수 있는 HTML로 변환.
한컴오피스 없이도 문서 결과를 즉시 확인할 수 있도록 함.

Usage:
    python html_preview.py document.hwpx -o preview.html
    python html_preview.py document.hwpx  # stdout 출력
"""
from __future__ import annotations

import argparse
import sys
from html import escape
from pathlib import Path

try:
    from hwpx_studio.read_document import HWPXReader
except ImportError:
    from read_document import HWPXReader


# ── CSS ────────────────────────────────────────────────────────────
_CSS = """\
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Malgun Gothic', '맑은 고딕', 'Apple SD Gothic Neo', sans-serif;
    max-width: 210mm; margin: 20mm auto; padding: 20mm 30mm;
    background: #f5f5f5; color: #222; line-height: 1.7; font-size: 11.5pt;
}
@media print { body { margin: 0; padding: 20mm 30mm 15mm 30mm; background: #fff; } }
.page { background: #fff; padding: 25mm 30mm; box-shadow: 0 1px 4px rgba(0,0,0,.12);
         min-height: 297mm; margin-bottom: 10mm; }
h1 { font-size: 18pt; font-weight: 700; margin: 16pt 0 8pt; border-bottom: 2px solid #333; padding-bottom: 4pt; }
h2 { font-size: 15pt; font-weight: 700; margin: 14pt 0 6pt; }
h3 { font-size: 13pt; font-weight: 700; margin: 12pt 0 4pt; }
p { margin: 4pt 0; }
.bullet { padding-left: 20pt; }
.bullet::before { content: '●'; margin-left: -14pt; margin-right: 6pt; font-size: 8pt; vertical-align: middle; }
.numbered { padding-left: 20pt; }
.indent { padding-left: 30pt; }
.note { background: #f8f8f0; border-left: 3px solid #c0a040; padding: 8pt 12pt; margin: 6pt 0; font-size: 10.5pt; }
.signature { text-align: right; margin-top: 20pt; font-weight: 600; }
.label-value { display: flex; gap: 12pt; margin: 3pt 0; }
.label-value .label { font-weight: 700; min-width: 80pt; color: #555; }
.pagebreak { border-top: 1px dashed #ccc; margin: 20pt 0; page-break-after: always; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 10.5pt; }
th, td { border: 1px solid #999; padding: 5pt 8pt; text-align: left; }
th { background: #e8e8e8; font-weight: 700; }
tr:nth-child(even) td { background: #fafafa; }
a { color: #1a5ab8; }
.bookmark { background: #fff3cd; padding: 1px 4px; border-radius: 2px; }
.footnote-ref { font-size: 8pt; vertical-align: super; color: #c00; }
.footnotes { border-top: 1px solid #ccc; margin-top: 20pt; padding-top: 8pt; font-size: 9.5pt; color: #555; }
.meta { color: #888; font-size: 9pt; margin-bottom: 10pt; }
"""


# ── 블록 → HTML ──────────────────────────────────────────────────
def _render_block(block: dict, footnotes: list) -> str:
    """단일 블록을 HTML로 변환."""
    btype = block.get("type", "paragraph")
    text = escape(block.get("text", ""))

    # charPr 스타일 적용 (dict가 아닌 경우 무시)
    char_pr = block.get("charPr", {})
    if not isinstance(char_pr, dict):
        char_pr = {}
    if char_pr.get("bold"):
        text = f"<strong>{text}</strong>"
    if char_pr.get("italic"):
        text = f"<em>{text}</em>"
    if char_pr.get("underline"):
        text = f"<u>{text}</u>"
    color = char_pr.get("color")
    if color:
        text = f'<span style="color:{color}">{text}</span>'

    if btype in ("heading", "heading_1", "heading_2", "heading_3"):
        level = block.get("level", 1)
        level = min(max(level, 1), 3)
        return f"<h{level}>{text}</h{level}>"

    if btype == "paragraph" or btype == "text":
        return f"<p>{text}</p>"

    if btype == "bullet":
        return f'<p class="bullet">{text}</p>'

    if btype == "numbered":
        num = block.get("number", "")
        prefix = f"{num}. " if num else ""
        return f'<p class="numbered">{prefix}{text}</p>'

    if btype == "indent":
        return f'<p class="indent">{text}</p>'

    if btype == "note":
        return f'<div class="note">{text}</div>'

    if btype == "signature":
        return f'<p class="signature">{text}</p>'

    if btype == "label_value":
        label = escape(block.get("label", ""))
        value = escape(block.get("value", ""))
        return f'<div class="label-value"><span class="label">{label}</span><span>{value}</span></div>'

    if btype == "pagebreak":
        return '<div class="pagebreak"></div>'

    if btype == "table":
        return _render_table(block)

    if btype == "hyperlink":
        url = escape(block.get("url", "#"))
        return f'<p><a href="{url}" target="_blank">{text}</a></p>'

    if btype == "bookmark":
        name = escape(block.get("name", ""))
        return f'<p><span class="bookmark" id="{name}">{text}</span></p>'

    if btype in ("text_footnote", "footnote"):
        fn_text = block.get("footnote", "")
        idx = len(footnotes) + 1
        footnotes.append(fn_text)
        return f'<p>{text}<sup class="footnote-ref">[{idx}]</sup></p>'

    if btype == "image":
        alt = escape(block.get("alt", "이미지"))
        return f'<p><em>[{alt}]</em></p>'

    # KCUP 블록들
    if btype.startswith("kcup_"):
        sub = btype.replace("kcup_", "")
        if sub == "box":
            return f'<div class="note" style="border-left-color:#336;">{text}</div>'
        if sub in ("o", "dash"):
            marker = "○" if sub == "o" else "–"
            return f'<p class="bullet" style="padding-left:24pt;">{marker} {text}</p>'
        if sub == "numbered":
            num = block.get("number", "")
            return f'<p class="numbered">{num}. {text}</p>'
        return f"<p>{text}</p>"

    # fallback
    return f"<p>{text}</p>" if text else ""


def _render_table(block: dict) -> str:
    """테이블 블록 → HTML table."""
    rows = block.get("rows", [])
    if not rows:
        return ""

    html = ['<table>']

    for i, row in enumerate(rows):
        html.append("<tr>")
        for cell in row:
            tag = "th" if i == 0 else "td"
            if isinstance(cell, dict):
                cell_text = escape(str(cell.get("text", "")))
            else:
                cell_text = escape(str(cell))
            html.append(f"<{tag}>{cell_text}</{tag}>")
        html.append("</tr>")

    html.append("</table>")
    return "\n".join(html)


# ── 메인 변환 ─────────────────────────────────────────────────────
def hwpx_to_html(hwpx_path: str) -> str:
    """HWPX 파일을 HTML 문자열로 변환."""
    reader = HWPXReader(hwpx_path)
    reader.load()
    data = reader.to_json()

    blocks = data.get("blocks", [])
    if not blocks:
        # 다중 섹션
        for sec in data.get("sections", []):
            blocks.extend(sec.get("blocks", []))

    footnotes: list[str] = []
    body_parts = []

    for block in blocks:
        html = _render_block(block, footnotes)
        if html:
            body_parts.append(html)

    # 각주 영역
    if footnotes:
        body_parts.append('<div class="footnotes">')
        for i, fn in enumerate(footnotes, 1):
            body_parts.append(f"<p>[{i}] {escape(fn)}</p>")
        body_parts.append("</div>")

    # 메타 정보
    template = data.get("template", "")
    meta = '<div class="meta">hwpx-studio preview'
    if template:
        meta += f" | template: {template}"
    meta += f" | {len(blocks)} blocks</div>"

    body = "\n".join(body_parts)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HWPX Preview</title>
<style>{_CSS}</style>
</head>
<body>
<div class="page">
{meta}
{body}
</div>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="HWPX → HTML 미리보기")
    parser.add_argument("input", help="HWPX 파일 경로")
    parser.add_argument("--output", "-o", help="출력 HTML 파일 (기본: stdout)")
    args = parser.parse_args()

    if not Path(args.input).is_file():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    html = hwpx_to_html(args.input)

    if args.output:
        Path(args.output).write_text(html, encoding="utf-8")
        print(f"Preview: {args.output}", file=sys.stderr)
    else:
        print(html)


if __name__ == "__main__":
    main()
