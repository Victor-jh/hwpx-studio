#!/usr/bin/env python3
"""section_builder.py — JSON → section0.xml 동적 생성기.

COWORK_CONTEXT.md 섹션 6 스펙 기반 재작성 + KCUP 팀장 대응용 스펙 v1.1.

지원 타입 (공통 11):
  text, empty, heading, bullet, numbered, indent, note,
  table (colRatios, 셀 병합, 다중 run, 셀 내 다중 문단),
  signature, label_value, pagebreak

KCUP 전용 타입 (16):
  kcup_box, kcup_box_spacing,
  kcup_o, kcup_o_plain, kcup_o_heading, kcup_o_spacing, kcup_o_heading_spacing,
  kcup_dash, kcup_dash_plain, kcup_dash_spacing,
  kcup_numbered, kcup_note, kcup_attachment, kcup_pointer, kcup_mixed_run
"""

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

from lxml import etree

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HS = "http://www.hancom.co.kr/hwpml/2011/section"
NSMAP = {
    "hp": HP,
    "hs": HS,
    "ha": "http://www.hancom.co.kr/hwpml/2011/app",
    "hp10": "http://www.hancom.co.kr/hwpml/2016/paragraph",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hhs": "http://www.hancom.co.kr/hwpml/2011/history",
    "hm": "http://www.hancom.co.kr/hwpml/2011/master-page",
    "hpf": "http://www.hancom.co.kr/schema/2011/hpf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "opf": "http://www.idpf.org/2007/opf/",
    "ooxmlchart": "http://www.hancom.co.kr/hwpml/2016/ooxmlchart",
    "hwpunitchar": "http://www.hancom.co.kr/hwpml/2016/HwpUnitChar",
    "epub": "http://www.idpf.org/2007/ops",
    "config": "urn:oasis:names:tc:opendocument:xmlns:config:1.0",
}

BODY_WIDTH = 42520  # A4 본문폭 HWPUNIT (report/gonmun 기본)
BODY_WIDTH_MAP = {
    "base": 42520,
    "report": 42520,
    "gonmun": 42520,
    "minutes": 42520,
    "proposal": 42520,
    "kcup": 48190,   # 좌우 20mm 여백 → 170mm 본문폭
}
DEFAULT_ROW_HEIGHT = 2800
DEFAULT_CELL_MARGIN = 113  # 약 0.4mm

# report 템플릿 기준 기본 스타일 매핑
HEADING_STYLES = {
    1: {"charPr": 7, "paraPr": 20},   # 20pt 볼드 CENTER
    2: {"charPr": 8, "paraPr": 0},    # 14pt 볼드
    3: {"charPr": 13, "paraPr": 27},  # 12pt 볼드 돋움 섹션헤더
}

NUMBERED_STYLES = {
    "circle":  {"paraPr": 24, "charPr": 0},   # □ left600
    "dot":     {"paraPr": 25, "charPr": 0},    # ① left1200
    "kcup":    {"paraPr": 24, "charPr": 0},    # KCUP 스타일
    "roman":   {"paraPr": 24, "charPr": 0},    # 로마 숫자
    "dash":    {"paraPr": 26, "charPr": 0},    # - left1800
}

ROMAN = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ"]
CIRCLE_NUMS = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩",
               "⑪", "⑫", "⑬", "⑭", "⑮", "⑯", "⑰", "⑱", "⑲", "⑳"]

# ── KCUP 전용 상수 ──────────────────────────────────────────────
# charPr 매핑 (kcup template header.xml 기준)
KCUP_CP = {
    "cover_title": 15,   # 19pt HY헤드라인M 볼드
    "body": 16,          # 14pt 휴먼명조 일반 — o/- 본문, "o" 글자
    "bold": 17,          # 14pt 휴먼명조 볼드 — 키워드, 번호소제목
    "box": 18,           # 14pt 휴먼명조 볼드(bF) — □항목, o 강조소제목
    "gap14": 19,         # 14pt 일반(bF) — □앞 간격줄, o소제목간 넓은 간격
    "gap14_alt": 20,     # 14pt 일반 — □앞 간격줄 대안
    "gap10": 21,         # 10pt 일반 — o/- 앞 간격줄
    "bracket": 22,       # 12pt 일반 — 괄호축소(-2pt), ※별도줄
    "sp_n4_12": 25,      # 12pt spacing=-4
    "sp_n3": 27,         # 14pt spacing=-3
    "sp_n1_12": 28,      # 12pt spacing=-1
    "sp_n1": 29,         # 14pt spacing=-1
    "sp_n4": 34,         # 14pt spacing=-4
    "sp_n5": 35,         # 14pt spacing=-5
    "sp_p3": 37,         # 14pt spacing=+3
}
# paraPr 매핑
KCUP_PP = {
    "o": 26,             # JUSTIFY 160% indent=-2319 — o 항목
    "box": 28,           # LEFT/CENTER 160% left=252 bF — □항목, □간격줄
    "dash": 30,          # JUSTIFY 160% indent=-3103 — - 항목
    "gap": 31,           # JUSTIFY 100% — o/- 앞 간격줄
}


class IDGen:
    def __init__(self, start=1000000001):
        self._id = start

    def next(self):
        v = self._id
        self._id += 1
        return str(v)


def hp(tag):
    return f"{{{HP}}}{tag}"


def hs(tag):
    return f"{{{HS}}}{tag}"


# ── 기본 요소 생성 ──────────────────────────────────────────────

def make_run(charPrIDRef, text=None):
    run = etree.SubElement(etree.Element("dummy"), hp("run"))
    run.set("charPrIDRef", str(charPrIDRef))
    if text:
        t = etree.SubElement(run, hp("t"))
        t.text = text
    else:
        etree.SubElement(run, hp("t"))
    return run


def make_paragraph(idgen, paraPr=0, charPr=0, text=None, runs=None,
                   pageBreak="0", styleIDRef="0"):
    p = etree.Element(hp("p"))
    p.set("id", idgen.next())
    p.set("paraPrIDRef", str(paraPr))
    p.set("styleIDRef", str(styleIDRef))
    p.set("pageBreak", str(pageBreak))
    p.set("columnBreak", "0")
    p.set("merged", "0")

    if runs:
        for r in runs:
            p.append(r)
    else:
        run = make_run(charPr, text)
        p.append(run)
    return p


def make_empty(idgen, paraPr=0, charPr=0):
    return make_paragraph(idgen, paraPr=paraPr, charPr=charPr)


# ── 다중 run 지원 ───────────────────────────────────────────────

def build_runs(item):
    """item["runs"] 또는 item["text"] + item["charPr"]에서 run 리스트 생성."""
    if "runs" in item:
        runs = []
        for r in item["runs"]:
            run = make_run(r.get("charPr", 0), r.get("text", ""))
            runs.append(run)
        return runs
    return None


# ── 표 생성 ─────────────────────────────────────────────────────

def compute_col_widths(col_count, ratios=None, body_width=None):
    bw = body_width or BODY_WIDTH
    if ratios:
        total = sum(ratios)
        widths = [int(bw * r / total) for r in ratios]
        diff = bw - sum(widths)
        widths[-1] += diff
    else:
        base = bw // col_count
        widths = [base] * col_count
        widths[-1] += bw - sum(widths)
    return widths


def cell_text_to_paragraphs(cell_data, idgen, default_charPr=0, default_paraPr=22):
    """셀 데이터를 문단 리스트로 변환.

    cell_data 형태:
      - str: 단일 문단
      - {"text": "...", "charPr": N}
      - {"lines": [...]}  → 셀 내 다중 문단
      - {"runs": [...]}   → 다중 run
    """
    paragraphs = []

    if isinstance(cell_data, str):
        paragraphs.append(
            make_paragraph(idgen, paraPr=default_paraPr, charPr=default_charPr,
                           text=cell_data))
    elif isinstance(cell_data, dict):
        if "lines" in cell_data:
            for line in cell_data["lines"]:
                if isinstance(line, str):
                    paragraphs.append(
                        make_paragraph(idgen, paraPr=default_paraPr,
                                       charPr=default_charPr, text=line))
                elif isinstance(line, dict):
                    cp = line.get("charPr", default_charPr)
                    pp = line.get("paraPr", default_paraPr)
                    if "runs" in line:
                        runs = build_runs(line)
                        paragraphs.append(
                            make_paragraph(idgen, paraPr=pp, runs=runs))
                    else:
                        paragraphs.append(
                            make_paragraph(idgen, paraPr=pp, charPr=cp,
                                           text=line.get("text", "")))
        elif "runs" in cell_data:
            runs = build_runs(cell_data)
            pp = cell_data.get("paraPr", default_paraPr)
            paragraphs.append(make_paragraph(idgen, paraPr=pp, runs=runs))
        else:
            cp = cell_data.get("charPr", default_charPr)
            pp = cell_data.get("paraPr", default_paraPr)
            paragraphs.append(
                make_paragraph(idgen, paraPr=pp, charPr=cp,
                               text=cell_data.get("text", "")))
    else:
        paragraphs.append(
            make_paragraph(idgen, paraPr=default_paraPr, charPr=default_charPr,
                           text=str(cell_data)))

    if not paragraphs:
        paragraphs.append(make_empty(idgen, paraPr=default_paraPr))

    return paragraphs


def make_cell(idgen, col_addr, row_addr, width, height, cell_data,
              col_span=1, row_span=1, borderFillIDRef="3",
              header=False, default_charPr=0, default_paraPr=22,
              cell_margin=None):
    tc = etree.Element(hp("tc"))
    tc.set("name", "")
    tc.set("header", "1" if header else "0")
    tc.set("hasMargin", "0")
    tc.set("protect", "0")
    tc.set("editable", "0")
    tc.set("dirty", "1")
    tc.set("borderFillIDRef", str(borderFillIDRef))

    sub = etree.SubElement(tc, hp("subList"))
    sub.set("id", "")
    sub.set("textDirection", "HORIZONTAL")
    sub.set("lineWrap", "BREAK")
    sub.set("vertAlign", "CENTER")
    sub.set("linkListIDRef", "0")
    sub.set("linkListNextIDRef", "0")
    sub.set("textWidth", "0")
    sub.set("textHeight", "0")
    sub.set("hasTextRef", "0")
    sub.set("hasNumRef", "0")

    paras = cell_text_to_paragraphs(cell_data, idgen,
                                     default_charPr=default_charPr,
                                     default_paraPr=default_paraPr)
    for para in paras:
        sub.append(para)

    addr = etree.SubElement(tc, hp("cellAddr"))
    addr.set("colAddr", str(col_addr))
    addr.set("rowAddr", str(row_addr))

    span = etree.SubElement(tc, hp("cellSpan"))
    span.set("colSpan", str(col_span))
    span.set("rowSpan", str(row_span))

    sz = etree.SubElement(tc, hp("cellSz"))
    sz.set("width", str(width))
    sz.set("height", str(height))

    margin = cell_margin or DEFAULT_CELL_MARGIN
    cm = etree.SubElement(tc, hp("cellMargin"))
    cm.set("left", str(margin))
    cm.set("right", str(margin))
    cm.set("top", str(margin))
    cm.set("bottom", str(margin))

    return tc


def make_table(idgen, item, body_width=None):
    """JSON table 정의에서 hp:tbl 요소를 포함하는 hp:p를 생성."""
    bw = body_width or BODY_WIDTH
    headers = item.get("headers", [])
    rows = item.get("rows", [])
    col_ratios = item.get("colRatios")
    row_height = item.get("rowHeight", DEFAULT_ROW_HEIGHT)
    header_bf = item.get("headerBorderFill", "4")
    cell_bf = item.get("cellBorderFill", "3")
    table_bf = item.get("tableBorderFill", "3")
    header_charPr = item.get("headerCharPr", 9)
    cell_charPr = item.get("cellCharPr", 0)
    header_paraPr = item.get("headerParaPr", 21)
    cell_paraPr = item.get("cellParaPr", 22)
    cell_margin = item.get("cellMargin")
    merge_map = item.get("merge", [])

    # 열 수 결정
    col_count = item.get("colCount")
    if not col_count:
        if headers:
            col_count = len(headers)
        elif rows:
            col_count = len(rows[0]) if rows[0] else 1
        else:
            col_count = 1

    col_widths = compute_col_widths(col_count, col_ratios, body_width=bw)

    # 전체 행 수
    total_rows = (1 if headers else 0) + len(rows)

    # 셀 병합 맵 구축: (row, col) → {"colSpan": N, "rowSpan": N}
    span_map = {}
    skip_cells = set()
    for m in merge_map:
        r, c = m["row"], m["col"]
        cs = m.get("colSpan", 1)
        rs = m.get("rowSpan", 1)
        span_map[(r, c)] = {"colSpan": cs, "rowSpan": rs}
        for dr in range(rs):
            for dc in range(cs):
                if dr == 0 and dc == 0:
                    continue
                skip_cells.add((r + dr, c + dc))

    # 전체 높이
    total_height = total_rows * row_height

    # 표 래퍼 문단
    p = etree.Element(hp("p"))
    p.set("id", idgen.next())
    p.set("paraPrIDRef", "0")
    p.set("styleIDRef", "0")
    p.set("pageBreak", "0")
    p.set("columnBreak", "0")
    p.set("merged", "0")

    run = etree.SubElement(p, hp("run"))
    run.set("charPrIDRef", "0")

    tbl = etree.SubElement(run, hp("tbl"))
    tbl.set("id", idgen.next())
    tbl.set("zOrder", "0")
    tbl.set("numberingType", "TABLE")
    tbl.set("textWrap", "TOP_AND_BOTTOM")
    tbl.set("textFlow", "BOTH_SIDES")
    tbl.set("lock", "0")
    tbl.set("dropcapstyle", "None")
    tbl.set("pageBreak", "CELL")
    tbl.set("repeatHeader", "1" if headers else "0")
    tbl.set("rowCnt", str(total_rows))
    tbl.set("colCnt", str(col_count))
    tbl.set("cellSpacing", "0")
    tbl.set("borderFillIDRef", str(table_bf))
    tbl.set("noAdjust", "0")

    sz = etree.SubElement(tbl, hp("sz"))
    sz.set("width", str(bw))
    sz.set("widthRelTo", "ABSOLUTE")
    sz.set("height", str(total_height))
    sz.set("heightRelTo", "ABSOLUTE")
    sz.set("protect", "0")

    pos = etree.SubElement(tbl, hp("pos"))
    pos.set("treatAsChar", "1")
    pos.set("affectLSpacing", "0")
    pos.set("flowWithText", "1")
    pos.set("allowOverlap", "0")
    pos.set("holdAnchorAndSO", "0")
    pos.set("vertRelTo", "PARA")
    pos.set("horzRelTo", "COLUMN")
    pos.set("vertAlign", "TOP")
    pos.set("horzAlign", "LEFT")
    pos.set("vertOffset", "0")
    pos.set("horzOffset", "0")

    for tag in ("outMargin", "inMargin"):
        m = etree.SubElement(tbl, hp(tag))
        m.set("left", "0")
        m.set("right", "0")
        m.set("top", "0")
        m.set("bottom", "0")

    # 행 생성
    all_rows_data = []
    if headers:
        all_rows_data.append(("header", headers))
    for row_data in rows:
        all_rows_data.append(("data", row_data))

    for row_idx, (row_type, cells) in enumerate(all_rows_data):
        tr = etree.SubElement(tbl, hp("tr"))

        for col_idx in range(col_count):
            if (row_idx, col_idx) in skip_cells:
                continue

            span_info = span_map.get((row_idx, col_idx), {})
            cs = span_info.get("colSpan", 1)
            rs = span_info.get("rowSpan", 1)

            # 셀 너비 (colSpan 고려)
            w = sum(col_widths[col_idx:col_idx + cs])
            h = row_height * rs

            # 셀 데이터
            cell_data = cells[col_idx] if col_idx < len(cells) else ""

            bf = header_bf if row_type == "header" else cell_bf
            cp = header_charPr if row_type == "header" else cell_charPr
            pp = header_paraPr if row_type == "header" else cell_paraPr
            is_header = row_type == "header"

            tc = make_cell(
                idgen, col_idx, row_idx, w, h, cell_data,
                col_span=cs, row_span=rs, borderFillIDRef=bf,
                header=is_header, default_charPr=cp, default_paraPr=pp,
                cell_margin=cell_margin)
            tr.append(tc)

    return p


# ── label_value 표 ──────────────────────────────────────────────

def make_label_value(idgen, item, body_width=None):
    """라벨:값 형태의 2열 표 생성."""
    items = item.get("items", [])
    label_ratio = item.get("labelRatio", 1)
    value_ratio = item.get("valueRatio", 3)
    row_height = item.get("rowHeight", DEFAULT_ROW_HEIGHT)

    table_item = {
        "colCount": 2,
        "colRatios": [label_ratio, value_ratio],
        "rows": [[i.get("label", ""), i.get("value", "")] for i in items],
        "rowHeight": row_height,
        "headerCharPr": item.get("labelCharPr", 9),
        "cellCharPr": item.get("valueCharPr", 0),
        "headerBorderFill": item.get("labelBorderFill", "4"),
        "cellBorderFill": item.get("valueBorderFill", "3"),
        "headerParaPr": item.get("labelParaPr", 21),
        "cellParaPr": item.get("valueParaPr", 22),
    }
    return make_table(idgen, table_item, body_width=body_width)


# ── signature 블록 ──────────────────────────────────────────────

def make_signature(idgen, item):
    """서명 블록 생성: 날짜 + 조직 + 이름."""
    paragraphs = []
    paragraphs.append(make_empty(idgen))

    date_text = item.get("date", "")
    if date_text:
        paragraphs.append(
            make_paragraph(idgen, paraPr=23, charPr=0, text=date_text))

    paragraphs.append(make_empty(idgen))

    org = item.get("org", "")
    if org:
        paragraphs.append(
            make_paragraph(idgen, paraPr=20, charPr=8, text=org))

    author = item.get("author", "")
    if author:
        paragraphs.append(
            make_paragraph(idgen, paraPr=20, charPr=8, text=author))

    return paragraphs


# ── secPr 첫 문단 생성 ──────────────────────────────────────────

def make_secpr_paragraph(idgen, base_section_path=None):
    """section0.xml의 필수 첫 문단 (secPr + colPr)."""
    if base_section_path:
        tree = etree.parse(str(base_section_path))
        root = tree.getroot()
        first_p = root.find(f".//{{{HP}}}p")
        if first_p is not None:
            # ID 재부여
            first_p.set("id", idgen.next())
            # linesegarray 제거
            for ls in first_p.findall(f".//{{{HP}}}linesegarray"):
                first_p.remove(ls)
            return first_p

    # 폴백: 최소 secPr 문단
    p = make_paragraph(idgen)
    run = p.find(hp("run"))
    secpr = etree.SubElement(run, hp("secPr"))
    secpr.set("id", "")
    secpr.set("textDirection", "HORIZONTAL")
    secpr.set("spaceColumns", "1134")
    secpr.set("tabStop", "8000")
    secpr.set("tabStopVal", "4000")
    secpr.set("tabStopUnit", "HWPUNIT")
    secpr.set("outlineShapeIDRef", "1")
    secpr.set("memoShapeIDRef", "0")
    secpr.set("textVerticalWidthHead", "0")
    secpr.set("masterPageCnt", "0")

    grid = etree.SubElement(secpr, hp("grid"))
    grid.set("lineGrid", "0")
    grid.set("charGrid", "0")
    grid.set("wonggojiFormat", "0")

    startNum = etree.SubElement(secpr, hp("startNum"))
    startNum.set("pageStartsOn", "BOTH")
    startNum.set("page", "0")
    startNum.set("pic", "0")
    startNum.set("tbl", "0")
    startNum.set("equation", "0")

    vis = etree.SubElement(secpr, hp("visibility"))
    for attr in ["hideFirstHeader", "hideFirstFooter", "hideFirstMasterPage",
                 "hideFirstPageNum", "hideFirstEmptyLine", "showLineNumber"]:
        vis.set(attr, "0")
    vis.set("border", "SHOW_ALL")
    vis.set("fill", "SHOW_ALL")

    lns = etree.SubElement(secpr, hp("lineNumberShape"))
    for attr in ["restartType", "countBy", "distance", "startNumber"]:
        lns.set(attr, "0")

    pagePr = etree.SubElement(secpr, hp("pagePr"))
    pagePr.set("landscape", "WIDELY")
    pagePr.set("width", "59528")
    pagePr.set("height", "84186")
    pagePr.set("gutterType", "LEFT_ONLY")
    margin = etree.SubElement(pagePr, hp("margin"))
    margin.set("header", "4252")
    margin.set("footer", "4252")
    margin.set("gutter", "0")
    margin.set("left", "8504")
    margin.set("right", "8504")
    margin.set("top", "5668")
    margin.set("bottom", "4252")

    # footNotePr / endNotePr 생략 (필수 아님)

    for btype in ["BOTH", "EVEN", "ODD"]:
        pbf = etree.SubElement(secpr, hp("pageBorderFill"))
        pbf.set("type", btype)
        pbf.set("borderFillIDRef", "1")
        pbf.set("textBorder", "PAPER")
        pbf.set("headerInside", "0")
        pbf.set("footerInside", "0")
        pbf.set("fillArea", "PAPER")
        off = etree.SubElement(pbf, hp("offset"))
        off.set("left", "1417")
        off.set("right", "1417")
        off.set("top", "1417")
        off.set("bottom", "1417")

    ctrl = etree.SubElement(run, hp("ctrl"))
    colpr = etree.SubElement(ctrl, hp("colPr"))
    colpr.set("id", "")
    colpr.set("type", "NEWSPAPER")
    colpr.set("layout", "LEFT")
    colpr.set("colCount", "1")
    colpr.set("sameSz", "1")
    colpr.set("sameGap", "0")

    return p


# ── KCUP 전용 블록 생성 함수 ──────────────────────────────────────

def _kcup_box_title(title):
    """□ 제목에서 2글자이면 공백 삽입 (균등 배분)."""
    if len(title) == 2:
        return f"{title[0]} {title[1]}"
    return title


def make_kcup_box(idgen, item):
    """□ 항목: paraPr=28, charPr=18, 2글자 제목 공백 삽입."""
    title = item.get("title", item.get("text", ""))
    title = _kcup_box_title(title)
    text = f"□ {title}"
    pp = item.get("paraPr", KCUP_PP["box"])
    cp = item.get("charPr", KCUP_CP["box"])
    return make_paragraph(idgen, paraPr=pp, charPr=cp, text=text)


def make_kcup_box_spacing(idgen, item):
    """□ 앞 간격줄: paraPr=28, charPr=19 (14pt 160%)."""
    pp = item.get("paraPr", KCUP_PP["box"])
    cp = item.get("charPr", KCUP_CP["gap14"])
    return make_empty(idgen, paraPr=pp, charPr=cp)


def make_kcup_o(idgen, item):
    """o 항목 (핵심선행 키워드):
    4-run: charPr17:" " + charPr16:"o " + charPr17:"(키워드)" + charPr16:" 설명"
    """
    keyword = item.get("keyword", "")
    text = item.get("text", "")
    pp = item.get("paraPr", KCUP_PP["o"])

    runs = [
        make_run(KCUP_CP["bold"], " "),
        make_run(KCUP_CP["body"], "o "),
        make_run(KCUP_CP["bold"], f"({keyword})"),
        make_run(KCUP_CP["body"], f" {text}"),
    ]
    return make_paragraph(idgen, paraPr=pp, runs=runs)


def make_kcup_o_plain(idgen, item):
    """o 항목 (단순 서술, 핵심선행 없음):
    2-run: charPr17:" " + charPr16:"o 서술내용"
    """
    text = item.get("text", "")
    pp = item.get("paraPr", KCUP_PP["o"])

    runs = [
        make_run(KCUP_CP["bold"], " "),
        make_run(KCUP_CP["body"], f"o {text}"),
    ]
    return make_paragraph(idgen, paraPr=pp, runs=runs)


def make_kcup_o_heading(idgen, item):
    """o 강조 소제목: charPr17:" o " + charPr18:"소제목"."""
    title = item.get("title", item.get("text", ""))
    pp = item.get("paraPr", KCUP_PP["o"])

    runs = [
        make_run(KCUP_CP["bold"], " o "),
        make_run(KCUP_CP["box"], title),
    ]
    return make_paragraph(idgen, paraPr=pp, runs=runs)


def make_kcup_o_spacing(idgen, item):
    """o/- 앞 간격줄: paraPr=31, charPr=21 (10pt 100%)."""
    pp = item.get("paraPr", KCUP_PP["gap"])
    cp = item.get("charPr", KCUP_CP["gap10"])
    return make_empty(idgen, paraPr=pp, charPr=cp)


def make_kcup_o_heading_spacing(idgen, item):
    """o소제목 간 넓은 간격줄: paraPr=31, charPr=19 (14pt 100%)."""
    pp = item.get("paraPr", KCUP_PP["gap"])
    cp = item.get("charPr", KCUP_CP["gap14"])
    return make_empty(idgen, paraPr=pp, charPr=cp)


def make_kcup_dash(idgen, item):
    """- 항목 (핵심선행 키워드):
    2-run: charPr17:"  - (키워드)" + charPr16:" 설명"
    """
    keyword = item.get("keyword", "")
    text = item.get("text", "")
    pp = item.get("paraPr", KCUP_PP["dash"])

    runs = [
        make_run(KCUP_CP["bold"], f"  - ({keyword})"),
        make_run(KCUP_CP["body"], f" {text}"),
    ]
    return make_paragraph(idgen, paraPr=pp, runs=runs)


def make_kcup_dash_plain(idgen, item):
    """- 항목 (단순):
    2-run: charPr17:"  - " + charPr16:"설명"
    """
    text = item.get("text", "")
    pp = item.get("paraPr", KCUP_PP["dash"])

    runs = [
        make_run(KCUP_CP["bold"], "  - "),
        make_run(KCUP_CP["body"], text),
    ]
    return make_paragraph(idgen, paraPr=pp, runs=runs)


def make_kcup_dash_spacing(idgen, item):
    """- 앞 간격줄 (= o간격과 동일): paraPr=31, charPr=21."""
    return make_kcup_o_spacing(idgen, item)


def make_kcup_numbered(idgen, item):
    """①~⑩ 번호소제목: paraPr=26, charPr=17 (전체 볼드)."""
    num = item.get("num", 1)
    text = item.get("text", "")
    prefix = CIRCLE_NUMS[num - 1] if num <= len(CIRCLE_NUMS) else f"({num})"
    full_text = f" {prefix} {text}"
    pp = item.get("paraPr", KCUP_PP["o"])
    cp = item.get("charPr", KCUP_CP["bold"])
    return make_paragraph(idgen, paraPr=pp, charPr=cp, text=full_text)


def make_kcup_note(idgen, item):
    """※ 참고: 15자 이하 인라인(같은 문단 run), 15자 초과 별도줄(charPr=22).
    JSON에서 명시적으로 type 분리하거나, text 길이로 자동 판별.
    별도줄 모드: paraPr=26, charPr=22.
    """
    text = item.get("text", "")
    mode = item.get("mode")  # "inline" | "line" | None(자동)

    if mode is None:
        mode = "inline" if len(text) <= 15 else "line"

    if mode == "line":
        pp = item.get("paraPr", KCUP_PP["o"])
        cp = item.get("charPr", KCUP_CP["bracket"])
        return make_paragraph(idgen, paraPr=pp, charPr=cp, text=f" ※ {text}")
    else:
        # 인라인은 이전 문단에 run을 붙여야 하므로 단독 문단으로 생성
        # (실제 인라인은 JSON의 runs 배열에서 직접 처리하는 것이 정확)
        pp = item.get("paraPr", KCUP_PP["o"])
        cp = item.get("charPr", KCUP_CP["body"])
        return make_paragraph(idgen, paraPr=pp, charPr=cp, text=f"※ {text}")


def make_kcup_attachment(idgen, item):
    """[붙임] 섹션: paraPr=26, charPr=16."""
    title = item.get("title", item.get("text", ""))
    pp = item.get("paraPr", KCUP_PP["o"])
    cp = item.get("charPr", KCUP_CP["body"])
    return make_paragraph(idgen, paraPr=pp, charPr=cp, text=f"[붙임] {title}")


def make_kcup_pointer(idgen, item):
    """☞ 강조 포인터: charPr17:"☞ " + charPr(지정):"강조 내용"."""
    text = item.get("text", "")
    emphasis_cp = item.get("emphasisCharPr", KCUP_CP["body"])
    pp = item.get("paraPr", KCUP_PP["o"])

    runs = [
        make_run(KCUP_CP["bold"], " ☞ "),
        make_run(emphasis_cp, text),
    ]
    return make_paragraph(idgen, paraPr=pp, runs=runs)


def make_kcup_mixed_run(idgen, item):
    """Mixed run 정교화: JSON의 runs 배열을 그대로 KCUP 문맥에서 사용.
    paraPr 기본값만 KCUP o항목(26)으로 설정.
    """
    pp = item.get("paraPr", KCUP_PP["o"])
    runs = build_runs(item)
    if runs:
        return make_paragraph(idgen, paraPr=pp, runs=runs)
    # fallback
    return make_paragraph(idgen, paraPr=pp, charPr=KCUP_CP["body"],
                          text=item.get("text", ""))


# ── auto_spacing 전처리기 ────────────────────────────────────────

# KCUP 블록 타입 분류
_KCUP_BOX_TYPES = {"kcup_box"}
_KCUP_MID_TYPES = {"kcup_o", "kcup_o_plain", "kcup_numbered"}
_KCUP_MID_HEADING_TYPES = {"kcup_o_heading"}
_KCUP_DETAIL_TYPES = {"kcup_dash", "kcup_dash_plain"}
_KCUP_SPACING_TYPES = {"kcup_box_spacing", "kcup_o_spacing",
                        "kcup_o_heading_spacing", "kcup_dash_spacing"}
_KCUP_CONTENT_TYPES = (_KCUP_BOX_TYPES | _KCUP_MID_TYPES |
                        _KCUP_MID_HEADING_TYPES | _KCUP_DETAIL_TYPES)
# 간격줄 삽입 대상이 아닌 타입 (표지, 서명, 표 등)
_KCUP_PASSTHROUGH = {"text", "empty", "heading", "bullet", "numbered",
                     "indent", "note", "table", "label_value", "signature",
                     "pagebreak", "kcup_note", "kcup_attachment",
                     "kcup_pointer", "kcup_mixed_run"}


def auto_spacing(content):
    """KCUP 블록 배열에서 간격줄을 자동 삽입한 새 배열을 반환.

    규칙 (kcup_document_style_spec_v1.1 기반):
        → box 앞:            kcup_box_spacing (14pt 160%)
        box/passthrough → mid/numbered: kcup_o_spacing (10pt 100%)
        mid → mid:           kcup_o_spacing
        mid/mid_heading → detail: kcup_o_spacing (첫 detail만)
        detail → detail:     kcup_o_spacing (= dash_spacing)
        mid_heading → mid_heading: kcup_o_heading_spacing (14pt 100%)

    이미 spacing 타입이 수동으로 있으면 중복 삽입하지 않음.
    auto_spacing 미적용 타입(text, heading, table 등)은 그대로 통과.
    """
    if not content:
        return content

    result = []
    prev_type = None

    for item in content:
        cur_type = item.get("type", "")

        # 이미 spacing 타입이면 그대로 넣고 prev_type 갱신 안 함
        if cur_type in _KCUP_SPACING_TYPES:
            result.append(item)
            continue

        # passthrough 타입은 간격줄 삽입 대상 아님
        if cur_type in _KCUP_PASSTHROUGH:
            result.append(item)
            prev_type = cur_type
            continue

        # ── KCUP 콘텐츠 블록 앞에 간격줄 삽입 판단 ──
        if cur_type in _KCUP_BOX_TYPES:
            # box 앞에는 항상 box_spacing
            result.append({"type": "kcup_box_spacing"})

        elif cur_type in _KCUP_MID_TYPES:
            if prev_type in (_KCUP_MID_HEADING_TYPES |
                             {"kcup_o_heading_spacing"}):
                # mid_heading 바로 뒤 mid → detail_spacing 아닌 o_spacing
                result.append({"type": "kcup_o_spacing"})
            else:
                result.append({"type": "kcup_o_spacing"})

        elif cur_type in _KCUP_MID_HEADING_TYPES:
            if prev_type in _KCUP_MID_HEADING_TYPES:
                # mid_heading → mid_heading: 넓은 간격 (14pt)
                result.append({"type": "kcup_o_heading_spacing"})
            elif prev_type in _KCUP_DETAIL_TYPES:
                # detail 뒤에 다음 mid_heading: 넓은 간격
                result.append({"type": "kcup_o_heading_spacing"})
            else:
                result.append({"type": "kcup_o_spacing"})

        elif cur_type in _KCUP_DETAIL_TYPES:
            result.append({"type": "kcup_o_spacing"})

        result.append(item)
        prev_type = cur_type

    return result


# ── 메인 빌더 ───────────────────────────────────────────────────

def build_section(json_data, base_section_path=None, template=None):
    """JSON 정의에서 section0.xml의 hs:sec 요소를 생성.

    template: 템플릿 이름 (kcup, report 등). body_width 결정에 사용.
    """
    idgen = IDGen()
    body_width = BODY_WIDTH_MAP.get(template, BODY_WIDTH) if template else BODY_WIDTH

    sec = etree.Element(hs("sec"), nsmap=NSMAP)

    # 첫 문단: secPr
    secpr_p = make_secpr_paragraph(idgen, base_section_path)
    sec.append(secpr_p)

    # 콘텐츠 항목 처리
    content = json_data.get("content", [])
    if not content:
        content = json_data.get("items", [])

    # auto_spacing: 기본 true, JSON에서 "auto_spacing": false로 비활성화 가능
    if json_data.get("auto_spacing", True):
        content = auto_spacing(content)

    for item in content:
        item_type = item.get("type", "text")

        if item_type == "empty":
            sec.append(make_empty(idgen))

        elif item_type == "text":
            runs = build_runs(item)
            cp = item.get("charPr", 0)
            pp = item.get("paraPr", 0)
            sec.append(make_paragraph(idgen, paraPr=pp, charPr=cp,
                                       text=item.get("text"), runs=runs))

        elif item_type == "heading":
            level = item.get("level", 1)
            style = HEADING_STYLES.get(level, HEADING_STYLES[1])
            cp = item.get("charPr", style["charPr"])
            pp = item.get("paraPr", style["paraPr"])
            sec.append(make_paragraph(idgen, paraPr=pp, charPr=cp,
                                       text=item.get("text", "")))

        elif item_type == "bullet":
            label = item.get("label", "•")
            text = item.get("text", "")
            full_text = f"{label} {text}"
            pp = item.get("paraPr", 24)
            cp = item.get("charPr", 0)
            runs = build_runs(item)
            if not runs:
                sec.append(make_paragraph(idgen, paraPr=pp, charPr=cp,
                                           text=full_text))
            else:
                sec.append(make_paragraph(idgen, paraPr=pp, runs=runs))

        elif item_type == "numbered":
            num = item.get("num", 1)
            style = item.get("style", "circle")
            text = item.get("text", "")

            if style == "roman":
                prefix = ROMAN[num - 1] if num <= len(ROMAN) else f"{num}."
            elif style == "circle":
                prefix = CIRCLE_NUMS[num - 1] if num <= len(CIRCLE_NUMS) else f"({num})"
            elif style == "dot":
                prefix = f"{num}."
            elif style == "kcup":
                prefix = f"□ {num}."
            else:
                prefix = f"{num}."

            full_text = f"{prefix} {text}"
            ns = NUMBERED_STYLES.get(style, NUMBERED_STYLES["circle"])
            pp = item.get("paraPr", ns["paraPr"])
            cp = item.get("charPr", ns["charPr"])
            runs = build_runs(item)
            if not runs:
                sec.append(make_paragraph(idgen, paraPr=pp, charPr=cp,
                                           text=full_text))
            else:
                sec.append(make_paragraph(idgen, paraPr=pp, runs=runs))

        elif item_type == "indent":
            label = item.get("label", "")
            text = item.get("text", "")
            full_text = f"{label}: {text}" if label else text
            pp = item.get("paraPr", 25)
            cp = item.get("charPr", 0)
            sec.append(make_paragraph(idgen, paraPr=pp, charPr=cp,
                                       text=full_text))

        elif item_type == "note":
            text = item.get("text", "")
            full_text = f"※ {text}"
            pp = item.get("paraPr", 0)
            cp = item.get("charPr", 11)
            sec.append(make_paragraph(idgen, paraPr=pp, charPr=cp,
                                       text=full_text))

        elif item_type == "table":
            sec.append(make_table(idgen, item, body_width=body_width))

        elif item_type == "label_value":
            sec.append(make_label_value(idgen, item, body_width=body_width))

        elif item_type == "signature":
            for p in make_signature(idgen, item):
                sec.append(p)

        elif item_type == "pagebreak":
            sec.append(make_paragraph(idgen, pageBreak="1"))

        # ── KCUP 전용 타입 ────────────────────────────────
        elif item_type == "kcup_box":
            sec.append(make_kcup_box(idgen, item))

        elif item_type == "kcup_box_spacing":
            sec.append(make_kcup_box_spacing(idgen, item))

        elif item_type == "kcup_o":
            sec.append(make_kcup_o(idgen, item))

        elif item_type == "kcup_o_plain":
            sec.append(make_kcup_o_plain(idgen, item))

        elif item_type == "kcup_o_heading":
            sec.append(make_kcup_o_heading(idgen, item))

        elif item_type == "kcup_o_spacing":
            sec.append(make_kcup_o_spacing(idgen, item))

        elif item_type == "kcup_o_heading_spacing":
            sec.append(make_kcup_o_heading_spacing(idgen, item))

        elif item_type == "kcup_dash":
            sec.append(make_kcup_dash(idgen, item))

        elif item_type == "kcup_dash_plain":
            sec.append(make_kcup_dash_plain(idgen, item))

        elif item_type == "kcup_dash_spacing":
            sec.append(make_kcup_dash_spacing(idgen, item))

        elif item_type == "kcup_numbered":
            sec.append(make_kcup_numbered(idgen, item))

        elif item_type == "kcup_note":
            sec.append(make_kcup_note(idgen, item))

        elif item_type == "kcup_attachment":
            sec.append(make_kcup_attachment(idgen, item))

        elif item_type == "kcup_pointer":
            sec.append(make_kcup_pointer(idgen, item))

        elif item_type == "kcup_mixed_run":
            sec.append(make_kcup_mixed_run(idgen, item))

        else:
            print(f"WARNING: unknown type '{item_type}', treating as text",
                  file=sys.stderr)
            sec.append(make_paragraph(idgen, text=item.get("text", "")))

    return sec


def build_xml(json_data, base_section_path=None, template=None):
    sec = build_section(json_data, base_section_path, template=template)
    tree = etree.ElementTree(sec)
    return tree


def main():
    parser = argparse.ArgumentParser(
        description="JSON → section0.xml 동적 생성")
    parser.add_argument("json_file", help="JSON 정의 파일 경로")
    parser.add_argument("--output", "-o", default="/dev/stdout",
                        help="출력 section0.xml 경로")
    parser.add_argument("--base-section",
                        help="secPr 복사용 base section0.xml 경로")
    parser.add_argument("--template", "-t",
                        help="템플릿 이름 (kcup, report 등). body_width 결정")
    args = parser.parse_args()

    with open(args.json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    base = Path(args.base_section) if args.base_section else None
    tree = build_xml(data, base, template=args.template)

    tree.write(args.output, xml_declaration=True, encoding="UTF-8",
               pretty_print=True)

    if args.output != "/dev/stdout":
        print(f"Generated: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
