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
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');

:root {
    --body-font: 'Noto Sans KR', '맑은 고딕', sans-serif;
    --body-size: 14pt;
    --small-size: 12pt;
    --spacing-color: transparent;
    --box-accent: #2c3e50;
    --o-indent: 28pt;
    --dash-indent: 48pt;
    --line-height: 1.65;
    --page-bg: #fff;
    --shadow: 0 2px 12px rgba(0,0,0,.08);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: var(--body-font);
    font-size: var(--body-size);
    line-height: var(--line-height);
    color: #1a1a1a;
    background: #eef0f2;
    -webkit-font-smoothing: antialiased;
}

.page {
    max-width: 740px;
    margin: 40px auto;
    padding: 72px 64px 60px;
    background: var(--page-bg);
    box-shadow: var(--shadow);
    border-radius: 2px;
    min-height: 900px;
}

@media print {
    body { background: #fff; }
    .page { margin: 0; padding: 25mm 30mm 20mm; box-shadow: none; max-width: none; }
    .meta-bar { display: none; }
}

@media (max-width: 780px) {
    .page { margin: 0; padding: 32px 24px 28px; border-radius: 0; }
}

/* ── 메타 바 ── */
.meta-bar {
    font-size: 9pt; color: #999; padding-bottom: 12px;
    margin-bottom: 24px; border-bottom: 1px solid #eee;
    display: flex; justify-content: space-between;
}

/* ── 일반 문단 ── */
p { margin: 3pt 0; }
h1 { font-size: 18pt; font-weight: 700; margin: 20pt 0 10pt;
     border-bottom: 2.5px solid #222; padding-bottom: 6pt; }
h2 { font-size: 15pt; font-weight: 700; margin: 16pt 0 8pt; }
h3 { font-size: 13pt; font-weight: 600; margin: 12pt 0 6pt; }

/* ── 일반 블록 ── */
.bullet { padding-left: 22pt; position: relative; margin: 3pt 0; }
.bullet::before { content: '●'; position: absolute; left: 6pt; font-size: 7pt;
                   top: 0.45em; color: #555; }
.numbered { padding-left: 22pt; margin: 3pt 0; }
.indent { padding-left: 32pt; margin: 3pt 0; }
.note { background: #f7f7f2; border-left: 3px solid #b8a040; padding: 10pt 14pt;
        margin: 8pt 0; font-size: 11pt; border-radius: 2px; }
.signature { text-align: right; margin-top: 24pt; font-weight: 600; font-size: 13pt; }
.label-value { display: flex; gap: 14pt; margin: 3pt 0; }
.label-value .lbl { font-weight: 700; min-width: 80pt; color: #444; flex-shrink: 0; }
.pagebreak { border-top: 1px dashed #d0d0d0; margin: 24pt 0; page-break-after: always; }

/* ── 표 ── */
table { border-collapse: collapse; width: 100%; margin: 10pt 0; font-size: 10.5pt; }
th, td { border: 1px solid #bbb; padding: 6pt 10pt; text-align: left; vertical-align: middle; }
th { background: #e6e6e6; font-weight: 600; }
tr:nth-child(even) td { background: #fafafa; }

/* ── 링크/북마크/각주 ── */
a { color: #1a6bc4; text-decoration: none; }
a:hover { text-decoration: underline; }
.bookmark { background: #fff8e1; padding: 1px 6px; border-radius: 3px; font-size: 0.9em; }
.footnote-ref { font-size: 8pt; vertical-align: super; color: #c22; cursor: help; }
.footnotes { border-top: 1px solid #ddd; margin-top: 28pt; padding-top: 10pt;
             font-size: 10pt; color: #666; }

/* ══════════════════════════════════════════════════════════
   KCUP 전용 스타일 — □ / o / - 계층 구조
   ══════════════════════════════════════════════════════════ */

/* □ 섹션 헤더 */
.kcup-box {
    font-size: 14pt; font-weight: 700; color: var(--box-accent);
    margin: 0; padding: 10pt 0 6pt 0;
    border-bottom: 2px solid var(--box-accent);
    position: relative;
}
.kcup-box::before {
    content: '□';
    margin-right: 8pt;
    font-weight: 400;
}
/* □ 앞 간격 */
.kcup-box-gap { height: 18pt; }

/* o 항목 — 키워드+설명 */
.kcup-o {
    margin: 0; padding: 2pt 0 2pt var(--o-indent);
    position: relative; font-size: 14pt;
}
.kcup-o::before {
    content: 'o';
    position: absolute; left: 10pt; top: 2pt;
    font-weight: 400; color: #333;
}
.kcup-o .kw {
    font-weight: 700; color: #1a1a1a;
}
/* o 앞 간격 */
.kcup-o-gap { height: 8pt; }

/* o 강조 소제목 */
.kcup-o-heading {
    margin: 0; padding: 2pt 0 2pt var(--o-indent);
    position: relative; font-size: 14pt; font-weight: 700;
}
.kcup-o-heading::before {
    content: 'o';
    position: absolute; left: 10pt; top: 2pt;
    font-weight: 400; color: #333;
}
/* o소제목 간 넓은 간격 */
.kcup-o-heading-gap { height: 16pt; }

/* - 항목 */
.kcup-dash {
    margin: 0; padding: 2pt 0 2pt var(--dash-indent);
    position: relative; font-size: 14pt;
}
.kcup-dash::before {
    content: '-';
    position: absolute; left: 32pt; top: 2pt;
    font-weight: 700; color: #333;
}
.kcup-dash .kw {
    font-weight: 700; color: #1a1a1a;
}
/* - 앞 간격 */
.kcup-dash-gap { height: 6pt; }

/* kcup 번호항목 ①②③ */
.kcup-num {
    margin: 0; padding: 2pt 0 2pt var(--o-indent);
    position: relative; font-size: 14pt; font-weight: 700;
}

/* kcup 참고 */
.kcup-note-line {
    margin: 0; padding: 2pt 0 2pt var(--o-indent);
    font-size: var(--small-size); color: #555;
}

/* kcup 붙임 */
.kcup-attach {
    margin: 16pt 0 6pt 0; padding: 8pt 0;
    font-size: 14pt; font-weight: 400; color: #333;
    border-top: 1px solid #ccc;
}

/* kcup 포인터 ☞ */
.kcup-pointer {
    margin: 0; padding: 4pt 0 4pt var(--o-indent);
    font-size: 14pt; font-weight: 700; color: #b33;
    position: relative;
}
.kcup-pointer::before {
    content: '☞'; position: absolute; left: 8pt; top: 4pt;
}

/* kcup mixed_run — 일반 텍스트 */
.kcup-mixed {
    margin: 0; padding: 2pt 0 2pt var(--o-indent);
    font-size: 14pt;
}

/* kcup 표지 */
.kcup-cover {
    text-align: center; padding: 80pt 0 40pt;
    border-bottom: 2px solid #333; margin-bottom: 24pt;
}
.kcup-cover .cover-title {
    font-size: 19pt; font-weight: 700; margin-bottom: 20pt;
    font-family: 'Noto Sans KR', sans-serif; letter-spacing: 1pt;
}
.kcup-cover .cover-date { font-size: 14pt; color: #444; margin-top: 12pt; }
.kcup-cover .cover-author { font-size: 14pt; color: #555; margin-top: 6pt; }

/* ── empty (간격줄) ── */
.empty-line { height: 4pt; }
"""


# ── KCUP 블록 렌더러 ─────────────────────────────────────────────
def _render_kcup(block: dict) -> str:
    """KCUP 전용 블록을 HTML로 변환."""
    btype = block.get("type", "")
    sub = btype.replace("kcup_", "")

    # 표지
    if sub == "cover":
        title = escape(block.get("title", block.get("text", "")))
        date = escape(block.get("date", ""))
        author = escape(block.get("author", ""))
        parts = ['<div class="kcup-cover">']
        parts.append(f'<div class="cover-title">{title}</div>')
        if date:
            parts.append(f'<div class="cover-date">{date}</div>')
        if author:
            parts.append(f'<div class="cover-author">{author}</div>')
        parts.append('</div>')
        return "\n".join(parts)

    # □ 섹션 헤더
    if sub == "box":
        title = escape(block.get("title", block.get("text", "")))
        return f'<div class="kcup-box-gap"></div>\n<div class="kcup-box">{title}</div>'

    # □ 앞 간격줄
    if sub == "box_spacing":
        return '<div class="kcup-box-gap"></div>'

    # o 핵심선행 키워드
    if sub == "o":
        kw = block.get("keyword", "")
        text = escape(block.get("text", ""))
        if kw:
            kw_html = f'<span class="kw">({escape(kw)})</span> '
        else:
            kw_html = ""
        return f'<div class="kcup-o-gap"></div>\n<p class="kcup-o">{kw_html}{text}</p>'

    # o 단순 서술
    if sub == "o_plain":
        text = escape(block.get("text", ""))
        return f'<div class="kcup-o-gap"></div>\n<p class="kcup-o">{text}</p>'

    # o 강조 소제목
    if sub == "o_heading":
        text = escape(block.get("text", ""))
        return f'<div class="kcup-o-heading-gap"></div>\n<p class="kcup-o-heading">{text}</p>'

    # o 앞 간격
    if sub == "o_spacing":
        return '<div class="kcup-o-gap"></div>'

    # o소제목 간 넓은 간격
    if sub == "o_heading_spacing":
        return '<div class="kcup-o-heading-gap"></div>'

    # - 핵심선행 키워드
    if sub == "dash":
        kw = block.get("keyword", "")
        text = escape(block.get("text", ""))
        if kw:
            kw_html = f'<span class="kw">({escape(kw)})</span> '
        else:
            kw_html = ""
        return f'<div class="kcup-dash-gap"></div>\n<p class="kcup-dash">{kw_html}{text}</p>'

    # - 단순
    if sub == "dash_plain":
        text = escape(block.get("text", ""))
        return f'<div class="kcup-dash-gap"></div>\n<p class="kcup-dash">{text}</p>'

    # - 간격
    if sub == "dash_spacing":
        return '<div class="kcup-dash-gap"></div>'

    # 번호항목 ①②③
    if sub == "numbered":
        num = block.get("number", "")
        text = escape(block.get("text", ""))
        return f'<div class="kcup-o-gap"></div>\n<p class="kcup-num">{num} {text}</p>'

    # ※ 참고
    if sub == "note":
        text = escape(block.get("text", ""))
        return f'<p class="kcup-note-line">※ {text}</p>'

    # [붙임]
    if sub == "attachment":
        text = escape(block.get("text", block.get("title", "")))
        return f'<div class="kcup-attach">[붙임] {text}</div>'

    # [붙임] + 표 복합
    if sub == "attachment_table":
        title = escape(block.get("title", block.get("text", "")))
        rows = block.get("rows", [])
        headers = block.get("headers", [])
        html = f'<div class="kcup-attach">[붙임] {title}</div>\n'
        html += '<table>'
        if headers:
            html += '<thead><tr>'
            for h in headers:
                html += f'<th>{escape(str(h))}</th>'
            html += '</tr></thead>'
        html += '<tbody>'
        for row in rows:
            html += '<tr>'
            for cell in row:
                html += f'<td>{escape(str(cell))}</td>'
            html += '</tr>'
        html += '</tbody></table>'
        return html

    # ☞ 포인터
    if sub == "pointer":
        text = escape(block.get("text", ""))
        return f'<p class="kcup-pointer">{text}</p>'

    # mixed_run
    if sub == "mixed_run":
        text = escape(block.get("text", ""))
        return f'<p class="kcup-mixed">{text}</p>'

    # fallback
    text = escape(block.get("text", ""))
    return f"<p>{text}</p>" if text else ""


# ── 일반 블록 → HTML ─────────────────────────────────────────────
def _render_block(block: dict, footnotes: list) -> str:
    """단일 블록을 HTML로 변환."""
    btype = block.get("type", "paragraph")

    # KCUP 블록 위임
    if btype.startswith("kcup_"):
        return _render_kcup(block)

    # empty (간격줄)
    if btype == "empty":
        return '<div class="empty-line"></div>'

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

    if btype in ("paragraph", "text"):
        return f"<p>{text}</p>" if text else ""

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
        return (
            f'<div class="label-value">'
            f'<span class="lbl">{label}</span><span>{value}</span></div>'
        )

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

    # fallback
    return f"<p>{text}</p>" if text else ""


def _render_table(block: dict) -> str:
    """테이블 블록 → HTML table."""
    rows = block.get("rows", [])
    if not rows:
        return ""

    html = ["<table>"]

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

    # KCUP 감지
    is_kcup = any(b.get("type", "").startswith("kcup_") for b in blocks)

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
    style_label = "KCUP" if is_kcup else (template or "general")
    meta = (
        f'<div class="meta-bar">'
        f'<span>hwpx-studio preview</span>'
        f'<span>{style_label} | {len(blocks)} blocks</span>'
        f'</div>'
    )

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
