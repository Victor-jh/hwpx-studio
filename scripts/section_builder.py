#!/usr/bin/env python3
"""section_builder.py — JSON → section0.xml 동적 생성기.

COWORK_CONTEXT.md 섹션 6 스펙 기반 재작성 + KCUP 팀장 대응용 스펙 v1.1.

지원 타입 (공통 12):
  text, empty, heading, bullet, numbered, indent, note,
  table (colRatios, 셀 병합, 다중 run, 셀 내 다중 문단),
  image (인라인 이미지 삽입, BinData 연동),
  signature, label_value, pagebreak

KCUP 전용 타입 (16):
  kcup_box, kcup_box_spacing,
  kcup_o, kcup_o_plain, kcup_o_heading, kcup_o_spacing, kcup_o_heading_spacing,
  kcup_dash, kcup_dash_plain, kcup_dash_spacing,
  kcup_numbered, kcup_note, kcup_attachment, kcup_pointer, kcup_mixed_run
"""

import argparse
import json
import mimetypes
import struct
import sys
from copy import deepcopy
from pathlib import Path

from lxml import etree

from property_registry import PropertyRegistry

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HS = "http://www.hancom.co.kr/hwpml/2011/section"
HC = "http://www.hancom.co.kr/hwpml/2011/core"
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


def hc(tag):
    return f"{{{HC}}}{tag}"


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


# ── 이미지 유틸리티 ─────────────────────────────────────────────

# 글로벌 이미지 레지스트리: section_builder 전체에서 수집, 나중에 사이드카 JSON 출력
_IMAGE_REGISTRY = []  # [{"id": "image1", "src": "/abs/path", "media_type": "image/png"}]


def _get_image_dimensions(file_path):
    """PNG/JPEG/GIF/BMP 파일에서 (width_px, height_px) 추출. Pillow 불필요."""
    p = Path(file_path)
    if not p.exists():
        return None, None
    with open(p, "rb") as f:
        header = f.read(32)
    # PNG
    if header[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", header[16:24])
        return w, h
    # JPEG
    if header[:2] == b"\xff\xd8":
        with open(p, "rb") as f:
            f.read(2)
            while True:
                marker = f.read(2)
                if len(marker) < 2:
                    break
                if marker[0] != 0xFF:
                    break
                if marker[1] in (0xC0, 0xC1, 0xC2):
                    f.read(3)  # length + precision
                    h, w = struct.unpack(">HH", f.read(4))
                    return w, h
                else:
                    length = struct.unpack(">H", f.read(2))[0]
                    f.read(length - 2)
        return None, None
    # GIF
    if header[:4] in (b"GIF8",):
        w, h = struct.unpack("<HH", header[6:10])
        return w, h
    # BMP
    if header[:2] == b"BM":
        w, h = struct.unpack("<ii", header[18:26])
        return w, abs(h)
    return None, None


def _mm_to_hwpunit(mm):
    """mm → HWPUNIT 변환 (1mm ≈ 283.46 HWPUNIT)."""
    return int(mm * 283.46)


def _px_to_hwpunit(px, dpi=96):
    """pixel → HWPUNIT 변환 (1inch = 7200 HWPUNIT)."""
    return int(px * 7200 / dpi)


def _detect_media_type(file_path):
    """파일 확장자로 MIME 타입 추정."""
    mt, _ = mimetypes.guess_type(str(file_path))
    return mt or "application/octet-stream"


def make_image_paragraph(idgen, item, body_width=None):
    """이미지 블록을 hp:p > hp:run > hp:pic XML로 변환.

    JSON 스펙:
        {
            "type": "image",
            "src": "/path/to/image.png",   (필수)
            "width_mm": 100,               (선택, 미지정 시 본문폭에 맞춤)
            "height_mm": 75,               (선택, 미지정 시 비율 자동계산)
            "align": "center",             (선택: left/center/right, 기본 center)
            "caption": "그림 설명"          (선택, 미구현 — 향후 확장)
        }

    Returns: (hp:p element, image_info dict)
        image_info: {"id": "imageN", "src": abs_path, "media_type": "image/png"}
    """
    bw = body_width or BODY_WIDTH
    src = item.get("src", "")
    src_path = Path(src).resolve()
    align = item.get("align", "center")

    # 이미지 ID 할당
    img_idx = len(_IMAGE_REGISTRY) + 1
    img_id = f"image{img_idx}"

    # 원본 크기 (px)
    orig_w_px, orig_h_px = _get_image_dimensions(src)
    if orig_w_px is None:
        # 기본값: 300x200
        orig_w_px, orig_h_px = 300, 200

    # 원본 크기 HWPUNIT (imgDim용)
    dim_w = _px_to_hwpunit(orig_w_px)
    dim_h = _px_to_hwpunit(orig_h_px)

    # 표시 크기 결정
    if "width_mm" in item:
        display_w = _mm_to_hwpunit(item["width_mm"])
        if "height_mm" in item:
            display_h = _mm_to_hwpunit(item["height_mm"])
        else:
            display_h = int(display_w * orig_h_px / orig_w_px) if orig_w_px else display_w
    else:
        # 본문폭에 맞춤 (비율 유지)
        display_w = bw
        display_h = int(bw * orig_h_px / orig_w_px) if orig_w_px else int(bw * 0.67)

    # 본문폭 초과 방지
    if display_w > bw:
        ratio = bw / display_w
        display_w = bw
        display_h = int(display_h * ratio)

    # 정렬에 따른 paraPr
    align_paraPr_map = {"left": 0, "center": 20, "right": 0}  # 20=CENTER
    pp = item.get("paraPr", align_paraPr_map.get(align, 20))

    # ── XML 생성 (한컴 Docs 실제 출력 구조 기반) ──
    p = etree.Element(hp("p"))
    p.set("id", idgen.next())
    p.set("paraPrIDRef", str(pp))
    p.set("styleIDRef", "0")
    p.set("pageBreak", "0")
    p.set("columnBreak", "0")
    p.set("merged", "0")

    run = etree.SubElement(p, hp("run"))
    run.set("charPrIDRef", str(item.get("charPr", 0)))

    pic = etree.SubElement(run, hp("pic"))
    pic_id = idgen.next()
    instid = idgen.next()
    pic.set("id", pic_id)
    pic.set("zOrder", "0")
    pic.set("numberingType", "PICTURE")
    pic.set("textWrap", "TOP_AND_BOTTOM")
    pic.set("textFlow", "BOTH_SIDES")
    pic.set("lock", "0")
    pic.set("dropcapstyle", "None")
    pic.set("href", "")
    pic.set("groupLevel", "0")
    pic.set("instid", instid)
    pic.set("reverse", "0")

    # ─── 한컴 실제 출력 순서 (reverse-engineered) ─────────
    # offset → orgSz → curSz → flip → rotationInfo → renderingInfo
    # → hc:img → imgRect → imgClip → inMargin → imgDim → effects
    # → sz → pos → outMargin

    # 1. offset
    offset = etree.SubElement(pic, hp("offset"))
    offset.set("x", "0")
    offset.set("y", "0")

    # 2. orgSz (표시 크기)
    orgSz = etree.SubElement(pic, hp("orgSz"))
    orgSz.set("width", str(display_w))
    orgSz.set("height", str(display_h))

    # 3. curSz (0,0)
    curSz = etree.SubElement(pic, hp("curSz"))
    curSz.set("width", "0")
    curSz.set("height", "0")

    # 4. flip
    flip = etree.SubElement(pic, hp("flip"))
    flip.set("horizontal", "0")
    flip.set("vertical", "0")

    # 5. rotationInfo (centerX/centerY = 0)
    rot = etree.SubElement(pic, hp("rotationInfo"))
    rot.set("angle", "0")
    rot.set("centerX", "0")
    rot.set("centerY", "0")
    rot.set("rotateimage", "1")

    # 6. renderingInfo (단위 행렬, hc 네임스페이스)
    ri = etree.SubElement(pic, hp("renderingInfo"))
    for mtx_tag in ("transMatrix", "scaMatrix", "rotMatrix"):
        mtx = etree.SubElement(ri, hc(mtx_tag))
        mtx.set("e1", "1")
        mtx.set("e2", "0")
        mtx.set("e3", "0")
        mtx.set("e4", "0")
        mtx.set("e5", "1")
        mtx.set("e6", "0")

    # 7. hc:img (★ 핵심: hp:img가 아니라 hc:img 네임스페이스!)
    img = etree.SubElement(pic, hc("img"))
    img.set("binaryItemIDRef", img_id)
    img.set("bright", "0")
    img.set("contrast", "0")
    img.set("effect", "REAL_PIC")
    img.set("alpha", "0")

    # 8. imgRect (표시 영역, hc 네임스페이스 pt)
    imgRect = etree.SubElement(pic, hp("imgRect"))
    for i, (px, py) in enumerate([(0, 0), (display_w, 0),
                                   (display_w, display_h), (0, display_h)]):
        pt = etree.SubElement(imgRect, hc(f"pt{i}"))
        pt.set("x", str(px))
        pt.set("y", str(py))

    # 9. imgClip (display 크기 사용)
    imgClip = etree.SubElement(pic, hp("imgClip"))
    imgClip.set("left", "0")
    imgClip.set("right", str(display_w))
    imgClip.set("top", "0")
    imgClip.set("bottom", str(display_h))

    # 10. inMargin
    inm = etree.SubElement(pic, hp("inMargin"))
    inm.set("left", "0")
    inm.set("right", "0")
    inm.set("top", "0")
    inm.set("bottom", "0")

    # 11. imgDim (원본 pixel→HWPUNIT)
    imgDim = etree.SubElement(pic, hp("imgDim"))
    imgDim.set("dimwidth", str(dim_w))
    imgDim.set("dimheight", str(dim_h))

    # 12. effects (빈 요소)
    etree.SubElement(pic, hp("effects"))

    # 13. sz (실제 표시 크기)
    sz = etree.SubElement(pic, hp("sz"))
    sz.set("width", str(display_w))
    sz.set("widthRelTo", "ABSOLUTE")
    sz.set("height", str(display_h))
    sz.set("heightRelTo", "ABSOLUTE")
    sz.set("protect", "0")

    # 14. pos — treatAsChar="1" (글자처럼 취급)
    pos = etree.SubElement(pic, hp("pos"))
    pos.set("treatAsChar", "1")
    pos.set("affectLSpacing", "0")
    pos.set("flowWithText", "1")
    pos.set("allowOverlap", "0")
    pos.set("holdAnchorAndSO", "0")
    pos.set("vertRelTo", "PARA")
    pos.set("horzRelTo", "PARA")
    pos.set("vertAlign", "TOP")
    pos.set("horzAlign", "LEFT")
    pos.set("vertOffset", "0")
    pos.set("horzOffset", "0")

    # 15. outMargin
    outm = etree.SubElement(pic, hp("outMargin"))
    outm.set("left", "0")
    outm.set("right", "0")
    outm.set("top", "0")
    outm.set("bottom", "0")

    # ─── hp:pic 다음에 빈 hp:t (한컴 필수) ───
    etree.SubElement(run, hp("t"))

    # 이미지 레지스트리에 등록
    media_type = _detect_media_type(src)
    img_info = {
        "id": img_id,
        "src": str(src_path),
        "media_type": media_type,
        "filename": f"{img_id}{Path(src).suffix}" if src else f"{img_id}.png",
    }
    _IMAGE_REGISTRY.append(img_info)

    return p, img_info


def get_image_registry():
    """현재까지 등록된 이미지 목록 반환."""
    return list(_IMAGE_REGISTRY)


def reset_image_registry():
    """이미지 레지스트리 초기화 (테스트/재실행용)."""
    _IMAGE_REGISTRY.clear()


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


# ── 인라인 스펙 해석 헬퍼 ──────────────────────────────────────

def _resolve_cp(item, default, registry):
    """item["charPr"]를 해석: int면 그대로, dict면 registry로 등록."""
    val = item.get("charPr", default)
    if registry and isinstance(val, dict):
        return registry.resolve_charPr(val)
    return val if isinstance(val, int) else default


def _resolve_pp(item, default, registry):
    """item["paraPr"]를 해석: int면 그대로, dict면 registry로 등록."""
    val = item.get("paraPr", default)
    if registry and isinstance(val, dict):
        return registry.resolve_paraPr(val)
    return val if isinstance(val, int) else default


def _resolve_bf(item, key, default, registry):
    """item[key] (borderFill 계열)를 해석."""
    val = item.get(key, default)
    if registry and isinstance(val, dict):
        return str(registry.resolve_borderFill(val))
    return str(val) if val is not None else str(default)


def build_runs_with_registry(item, registry=None):
    """item["runs"]에서 run 리스트 생성. 각 run의 charPr가 dict이면 registry로 등록."""
    if "runs" not in item:
        return None
    runs = []
    for r in item["runs"]:
        cp = r.get("charPr", 0)
        if registry and isinstance(cp, dict):
            cp = registry.resolve_charPr(cp)
        run = make_run(cp, r.get("text", ""))
        runs.append(run)
    return runs


# ── 메인 빌더 ───────────────────────────────────────────────────

def build_section(json_data, base_section_path=None, template=None,
                  registry=None):
    """JSON 정의에서 section0.xml의 hs:sec 요소를 생성.

    template: 템플릿 이름 (kcup, report 등). body_width 결정에 사용.
    registry: PropertyRegistry 인스턴스. 인라인 charPr/paraPr dict 해석에 사용.
    """
    idgen = IDGen()
    body_width = BODY_WIDTH_MAP.get(template, BODY_WIDTH) if template else BODY_WIDTH

    sec = etree.Element(hs("sec"), nsmap=NSMAP)

    # 첫 문단: secPr
    secpr_p = make_secpr_paragraph(idgen, base_section_path)
    sec.append(secpr_p)

    # 콘텐츠 항목 처리
    content = json_data.get("blocks", [])
    if not content:
        content = json_data.get("content", [])
    if not content:
        content = json_data.get("items", [])

    # auto_spacing: 기본 true, JSON에서 "auto_spacing": false로 비활성화 가능
    if json_data.get("auto_spacing", True):
        content = auto_spacing(content)

    for item in content:
        item_type = item.get("type", "text")

        if item_type == "empty":
            cp = _resolve_cp(item, 0, registry)
            pp = _resolve_pp(item, 0, registry)
            sec.append(make_empty(idgen, paraPr=pp, charPr=cp))

        elif item_type == "text":
            runs = build_runs_with_registry(item, registry)
            cp = _resolve_cp(item, 0, registry)
            pp = _resolve_pp(item, 0, registry)
            sec.append(make_paragraph(idgen, paraPr=pp, charPr=cp,
                                       text=item.get("text"), runs=runs))

        elif item_type == "heading":
            level = item.get("level", 1)
            style = HEADING_STYLES.get(level, HEADING_STYLES[1])
            cp = _resolve_cp(item, style["charPr"], registry)
            pp = _resolve_pp(item, style["paraPr"], registry)
            sec.append(make_paragraph(idgen, paraPr=pp, charPr=cp,
                                       text=item.get("text", "")))

        elif item_type == "bullet":
            label = item.get("label", "•")
            text = item.get("text", "")
            full_text = f"{label} {text}"
            pp = _resolve_pp(item, 24, registry)
            cp = _resolve_cp(item, 0, registry)
            runs = build_runs_with_registry(item, registry)
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
            pp = _resolve_pp(item, ns["paraPr"], registry)
            cp = _resolve_cp(item, ns["charPr"], registry)
            runs = build_runs_with_registry(item, registry)
            if not runs:
                sec.append(make_paragraph(idgen, paraPr=pp, charPr=cp,
                                           text=full_text))
            else:
                sec.append(make_paragraph(idgen, paraPr=pp, runs=runs))

        elif item_type == "indent":
            label = item.get("label", "")
            text = item.get("text", "")
            full_text = f"{label}: {text}" if label else text
            pp = _resolve_pp(item, 25, registry)
            cp = _resolve_cp(item, 0, registry)
            sec.append(make_paragraph(idgen, paraPr=pp, charPr=cp,
                                       text=full_text))

        elif item_type == "note":
            text = item.get("text", "")
            full_text = f"※ {text}"
            pp = _resolve_pp(item, 0, registry)
            cp = _resolve_cp(item, 11, registry)
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

        elif item_type == "image":
            img_p, _img_info = make_image_paragraph(idgen, item,
                                                     body_width=body_width)
            sec.append(img_p)

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


def build_xml(json_data, base_section_path=None, template=None, registry=None):
    sec = build_section(json_data, base_section_path, template=template,
                        registry=registry)
    tree = etree.ElementTree(sec)
    return tree


# ── 다중 섹션 (L2) ──────────────────────────────────────────────

def _make_custom_secpr(idgen, base_section_path, sec_opts):
    """secPr를 base에서 복사한 뒤 sec_opts로 오버라이드.

    sec_opts 지원 키:
      landscape: bool   — 용지 방향 (true=가로)
      margin: dict      — {"left":mm, "right":mm, "top":mm, "bottom":mm,
                           "header":mm, "footer":mm}
      width: int        — 용지 폭 (HWPUNIT), 기본 A4
      height: int       — 용지 높이 (HWPUNIT), 기본 A4
    """
    p = make_secpr_paragraph(idgen, base_section_path)

    secpr = p.find(f".//{{{HP}}}secPr")
    if secpr is None:
        return p

    pagePr = secpr.find(f"{{{HP}}}pagePr")
    if pagePr is None:
        return p

    # landscape: NARROWLY=가로, WIDELY=세로
    # width/height는 용지 물리 크기(A4)를 유지 — landscape 속성만 변경
    if sec_opts.get("landscape"):
        pagePr.set("landscape", "NARROWLY")
    elif sec_opts.get("landscape") is False:
        pagePr.set("landscape", "WIDELY")

    # 직접 width/height 지정
    if "width" in sec_opts:
        pagePr.set("width", str(sec_opts["width"]))
    if "height" in sec_opts:
        pagePr.set("height", str(sec_opts["height"]))

    # margin 오버라이드
    margin_opts = sec_opts.get("margin", {})
    if margin_opts:
        mg = pagePr.find(f"{{{HP}}}margin")
        if mg is None:
            mg = etree.SubElement(pagePr, hp("margin"))
        MM = 283  # 1mm ≈ 283 HWPUNIT (283.5 반올림)
        for key in ("left", "right", "top", "bottom", "header", "footer", "gutter"):
            if key in margin_opts:
                mg.set(key, str(int(margin_opts[key] * MM)))

    return p


def build_multi_sections(json_data, base_section_path=None, template=None):
    """JSON의 "sections" 배열에서 복수 section XML을 생성.

    Returns:
        list of (filename, etree.ElementTree) — [("section0.xml", tree), ...]
    """
    sections_def = json_data.get("sections", [])
    if not sections_def:
        # 단일 섹션 폴백
        tree = build_xml(json_data, base_section_path, template=template)
        return [("section0.xml", tree)]

    results = []
    for i, sec_def in enumerate(sections_def):
        idgen = IDGen()
        body_width = BODY_WIDTH_MAP.get(template, BODY_WIDTH) if template else BODY_WIDTH

        sec = etree.Element(hs("sec"), nsmap=NSMAP)

        # secPr (오버라이드 적용)
        secpr_p = _make_custom_secpr(idgen, base_section_path, sec_def)
        sec.append(secpr_p)

        # 콘텐츠
        content = sec_def.get("blocks", [])
        if not content:
            content = sec_def.get("content", [])

        if sec_def.get("auto_spacing", json_data.get("auto_spacing", True)):
            content = auto_spacing(content)

        for item in content:
            elements = _build_item(idgen, item, body_width, template)
            for el in elements:
                sec.append(el)

        tree = etree.ElementTree(sec)
        results.append((f"section{i}.xml", tree))

    return results


def _build_item(idgen, item, body_width, template):
    """단일 블록 아이템을 파싱해서 요소 리스트를 반환.
    build_section의 dispatch 로직을 재사용 가능한 함수로 분리."""
    item_type = item.get("type", "text")
    elements = []

    if item_type == "empty":
        elements.append(make_empty(idgen))

    elif item_type == "text":
        runs = build_runs(item)
        cp = item.get("charPr", 0)
        pp = item.get("paraPr", 0)
        elements.append(make_paragraph(idgen, paraPr=pp, charPr=cp,
                                        text=item.get("text"), runs=runs))

    elif item_type == "heading":
        level = item.get("level", 1)
        style = HEADING_STYLES.get(level, HEADING_STYLES[1])
        cp = item.get("charPr", style["charPr"])
        pp = item.get("paraPr", style["paraPr"])
        elements.append(make_paragraph(idgen, paraPr=pp, charPr=cp,
                                        text=item.get("text", "")))

    elif item_type == "bullet":
        label = item.get("label", "•")
        text = item.get("text", "")
        full_text = f"{label} {text}"
        pp = item.get("paraPr", 24)
        cp = item.get("charPr", 0)
        runs = build_runs(item)
        if not runs:
            elements.append(make_paragraph(idgen, paraPr=pp, charPr=cp,
                                            text=full_text))
        else:
            elements.append(make_paragraph(idgen, paraPr=pp, runs=runs))

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
            elements.append(make_paragraph(idgen, paraPr=pp, charPr=cp,
                                            text=full_text))
        else:
            elements.append(make_paragraph(idgen, paraPr=pp, runs=runs))

    elif item_type == "indent":
        label = item.get("label", "")
        text = item.get("text", "")
        full_text = f"{label}: {text}" if label else text
        pp = item.get("paraPr", 25)
        cp = item.get("charPr", 0)
        elements.append(make_paragraph(idgen, paraPr=pp, charPr=cp,
                                        text=full_text))

    elif item_type == "note":
        text = item.get("text", "")
        full_text = f"※ {text}"
        pp = item.get("paraPr", 0)
        cp = item.get("charPr", 11)
        elements.append(make_paragraph(idgen, paraPr=pp, charPr=cp,
                                        text=full_text))

    elif item_type == "table":
        elements.append(make_table(idgen, item, body_width=body_width))

    elif item_type == "label_value":
        elements.append(make_label_value(idgen, item, body_width=body_width))

    elif item_type == "signature":
        for p in make_signature(idgen, item):
            elements.append(p)

    elif item_type == "pagebreak":
        elements.append(make_paragraph(idgen, pageBreak="1"))

    elif item_type == "image":
        img_p, _img_info = make_image_paragraph(idgen, item,
                                                  body_width=body_width)
        elements.append(img_p)

    # ── KCUP 전용 타입 ────────────────────────────────
    elif item_type == "kcup_box":
        elements.append(make_kcup_box(idgen, item))
    elif item_type == "kcup_box_spacing":
        elements.append(make_kcup_box_spacing(idgen, item))
    elif item_type == "kcup_o":
        elements.append(make_kcup_o(idgen, item))
    elif item_type == "kcup_o_plain":
        elements.append(make_kcup_o_plain(idgen, item))
    elif item_type == "kcup_o_heading":
        elements.append(make_kcup_o_heading(idgen, item))
    elif item_type == "kcup_o_spacing":
        elements.append(make_kcup_o_spacing(idgen, item))
    elif item_type == "kcup_o_heading_spacing":
        elements.append(make_kcup_o_heading_spacing(idgen, item))
    elif item_type == "kcup_dash":
        elements.append(make_kcup_dash(idgen, item))
    elif item_type == "kcup_dash_plain":
        elements.append(make_kcup_dash_plain(idgen, item))
    elif item_type == "kcup_dash_spacing":
        elements.append(make_kcup_dash_spacing(idgen, item))
    elif item_type == "kcup_numbered":
        elements.append(make_kcup_numbered(idgen, item))
    elif item_type == "kcup_note":
        elements.append(make_kcup_note(idgen, item))
    elif item_type == "kcup_attachment":
        elements.append(make_kcup_attachment(idgen, item))
    elif item_type == "kcup_pointer":
        elements.append(make_kcup_pointer(idgen, item))
    elif item_type == "kcup_mixed_run":
        elements.append(make_kcup_mixed_run(idgen, item))

    return elements


def _write_images_sidecar(output_path):
    """이미지 레지스트리를 _images.json 사이드카 파일로 출력."""
    images = get_image_registry()
    if not images:
        return None
    out = Path(output_path)
    if out.is_dir():
        sidecar = out / "_images.json"
    else:
        sidecar = out.parent / f"{out.stem}_images.json"
    with open(sidecar, "w", encoding="utf-8") as f:
        json.dump(images, f, ensure_ascii=False, indent=2)
    print(f"Images manifest: {sidecar} ({len(images)} images)",
          file=sys.stderr)
    return str(sidecar)


def _resolve_header_for_registry(template=None):
    """템플릿 이름에서 header.xml 경로를 찾아 registry 초기화용으로 반환."""
    SKILL_DIR = Path(__file__).resolve().parent.parent
    TEMPLATES_DIR = SKILL_DIR / "templates"

    if template:
        candidate = TEMPLATES_DIR / template / "header.xml"
        if candidate.exists():
            return str(candidate)
    base_header = TEMPLATES_DIR / "base" / "Contents" / "header.xml"
    if base_header.exists():
        return str(base_header)
    return None


def _write_registry_sidecar(output_path, registry):
    """레지스트리를 사이드카 JSON으로 저장."""
    if not registry or not registry.has_changes():
        return
    if isinstance(output_path, str):
        output_path = Path(output_path)
    if output_path.is_dir():
        sidecar = output_path / "_registry.json"
    else:
        sidecar = output_path.parent / f"{output_path.stem}_registry.json"
    registry.save(str(sidecar))
    print(f"  Registry sidecar: {sidecar}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="JSON → section0.xml 동적 생성")
    parser.add_argument("json_file", help="JSON 정의 파일 경로")
    parser.add_argument("--output", "-o", default="/dev/stdout",
                        help="출력 경로 (단일 섹션: 파일, 다중 섹션: 디렉토리)")
    parser.add_argument("--base-section",
                        help="secPr 복사용 base section0.xml 경로")
    parser.add_argument("--template", "-t",
                        help="템플릿 이름 (kcup, report 등). body_width 결정")
    args = parser.parse_args()

    reset_image_registry()

    with open(args.json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    base = Path(args.base_section) if args.base_section else None

    # 동적 서식 레지스트리 초기화
    header_path = _resolve_header_for_registry(args.template)
    registry = PropertyRegistry(header_path) if header_path else PropertyRegistry()

    # 다중 섹션 감지
    if "sections" in data:
        results = build_multi_sections(data, base, template=args.template)
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        for fname, tree in results:
            fpath = out_dir / fname
            tree.write(str(fpath), xml_declaration=True, encoding="UTF-8",
                       pretty_print=True)
        print(f"Generated {len(results)} sections in {out_dir}",
              file=sys.stderr)
        _write_images_sidecar(out_dir)
        _write_registry_sidecar(out_dir, registry)
    else:
        tree = build_xml(data, base, template=args.template, registry=registry)
        tree.write(args.output, xml_declaration=True, encoding="UTF-8",
                   pretty_print=True)
        if args.output != "/dev/stdout":
            print(f"Generated: {args.output}", file=sys.stderr)
            _write_images_sidecar(args.output)
            _write_registry_sidecar(args.output, registry)


if __name__ == "__main__":
    main()
