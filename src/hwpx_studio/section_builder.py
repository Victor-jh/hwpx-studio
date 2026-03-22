#!/usr/bin/env python3
"""section_builder.py — JSON → section0.xml 동적 생성기.

COWORK_CONTEXT.md 섹션 6 스펙 기반 재작성 + KCUP 팀장 대응용 스펙 v1.1.

지원 타입 (공통 19):
  text, empty, heading, bullet, numbered, indent, note,
  table (colRatios, 셀 병합, 다중 run, 셀 내 다중 문단),
  image (인라인 이미지 삽입, BinData 연동),
  hyperlink, text_footnote, text_endnote, footnote,
  textbox (글상자, hp:rect 기반 인라인 배치),
  caption (캡션, styleIDRef=22 기반),
  bookmark (책갈피, fieldBegin/fieldEnd type=BOOKMARK),
  field (날짜/쪽번호/전체쪽수 필드),
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
from pathlib import Path

from lxml import etree

try:
    from hwpx_studio.property_registry import PropertyRegistry
except ImportError:
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


def cell_text_to_paragraphs(cell_data, idgen, default_charPr=0, default_paraPr=22,
                            registry=None):
    """셀 데이터를 문단 리스트로 변환.

    cell_data 형태:
      - str: 단일 문단
      - {"text": "...", "charPr": N 또는 dict}
      - {"lines": [...]}  → 셀 내 다중 문단
      - {"runs": [...]}   → 다중 run

    registry: PropertyRegistry — charPr/paraPr dict를 ID로 해석
    """
    def _rc(spec, default):
        """charPr dict → registry resolve."""
        if registry and isinstance(spec, dict):
            return registry.resolve_charPr(spec)
        return spec if not isinstance(spec, dict) else default

    def _rp(spec, default):
        """paraPr dict → registry resolve."""
        if registry and isinstance(spec, dict):
            return registry.resolve_paraPr(spec)
        return spec if not isinstance(spec, dict) else default

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
                    cp = _rc(line.get("charPr", default_charPr), default_charPr)
                    pp = _rp(line.get("paraPr", default_paraPr), default_paraPr)
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
            pp = _rp(cell_data.get("paraPr", default_paraPr), default_paraPr)
            paragraphs.append(make_paragraph(idgen, paraPr=pp, runs=runs))
        else:
            cp = _rc(cell_data.get("charPr", default_charPr), default_charPr)
            pp = _rp(cell_data.get("paraPr", default_paraPr), default_paraPr)
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
              cell_margin=None, registry=None):
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
                                     default_paraPr=default_paraPr,
                                     registry=registry)
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


def make_table(idgen, item, body_width=None, registry=None):
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
                cell_margin=cell_margin, registry=registry)
            tr.append(tc)

    return p


# ── label_value 표 ──────────────────────────────────────────────

def make_label_value(idgen, item, body_width=None, registry=None):
    """라벨:값 형태의 2열 표 생성.

    JSON 입력 형식 2가지 지원:
      - pairs: [["라벨", "값"], ...]          ← 간편 형식
      - items: [{"label": "라벨", "value": "값"}, ...]  ← 상세 형식
    """
    pairs = item.get("pairs")
    items = item.get("items", [])
    if pairs:
        rows = [[p[0], p[1]] for p in pairs]
    else:
        rows = [[i.get("label", ""), i.get("value", "")] for i in items]
    label_ratio = item.get("labelRatio", 1)
    value_ratio = item.get("valueRatio", 3)
    row_height = item.get("rowHeight", DEFAULT_ROW_HEIGHT)

    table_item = {
        "colCount": 2,
        "colRatios": [label_ratio, value_ratio],
        "rows": rows,
        "rowHeight": row_height,
        "headerCharPr": item.get("labelCharPr", 9),
        "cellCharPr": item.get("valueCharPr", 0),
        "headerBorderFill": item.get("labelBorderFill", "4"),
        "cellBorderFill": item.get("valueBorderFill", "3"),
        "headerParaPr": item.get("labelParaPr", 21),
        "cellParaPr": item.get("valueParaPr", 22),
    }
    return make_table(idgen, table_item, body_width=body_width,
                      registry=registry)


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

def make_secpr_paragraph(idgen, base_section_path=None, columns=None):
    """section0.xml의 필수 첫 문단 (secPr + colPr).

    columns: dict 또는 int. 다단 설정.
      - int: 단 수 (예: 2)
      - dict: {"count": 2, "gap": 1134, "layout": "LEFT", "same_width": True}
    """
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
            # 다단 오버라이드 (columns 지정 시)
            if columns is not None:
                colpr = first_p.find(f".//{{{HP}}}colPr")
                if colpr is not None:
                    if isinstance(columns, int):
                        colpr.set("colCount", str(columns))
                        colpr.set("sameGap", "1134")
                    elif isinstance(columns, dict):
                        colpr.set("colCount", str(columns.get("count", 1)))
                        colpr.set("sameGap", str(columns.get("gap", 1134)))
                        colpr.set("layout", columns.get("layout", "LEFT"))
                        colpr.set("sameSz", "1" if columns.get("same_width", True) else "0")
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

    # 다단 설정 반영
    col_count = 1
    col_gap = 0
    col_layout = "LEFT"
    col_same_sz = "1"
    if columns is not None:
        if isinstance(columns, int):
            col_count = columns
            col_gap = 1134  # 기본 4mm 간격
        elif isinstance(columns, dict):
            col_count = columns.get("count", 1)
            col_gap = columns.get("gap", 1134)
            col_layout = columns.get("layout", "LEFT")
            col_same_sz = "1" if columns.get("same_width", True) else "0"

    colpr.set("layout", col_layout)
    colpr.set("colCount", str(col_count))
    colpr.set("sameSz", col_same_sz)
    colpr.set("sameGap", str(col_gap))

    return p


# ── 글상자 (TextBox / rect) ────────────────────────────────────────

_TEXTBOX_INSTID = 1042200000


def _next_textbox_instid():
    global _TEXTBOX_INSTID
    _TEXTBOX_INSTID += 1
    return str(_TEXTBOX_INSTID)


def _mm_to_hwp(mm):
    """mm → HWPUNIT (1mm ≈ 283.46 HWPUNIT)."""
    return int(round(mm * 283.46))


def make_textbox_paragraph(idgen, item, body_width=None, registry=None):
    """글상자(TextBox) 블록.

    JSON:
      {"type": "textbox", "text": "내용",
       "width": 100, "height": 30,         # mm (생략 시 본문폭×30mm)
       "border_color": "#000000",           # 테두리 색 (생략 시 검정)
       "border_width": "0.12 mm",           # 테두리 두께
       "bg_color": "#FFFFFF",               # 배경색 (생략 시 흰색)
       "text_align": "center",              # 글상자 내 수직정렬: top/center/bottom
       "charPr": ..., "paraPr": ...         # 내부 텍스트 서식 (옵션)
      }

    treatAsChar=1 (인라인 배치) 방식.
    """
    bw = body_width or BODY_WIDTH

    # 크기 결정 (mm → HWPUNIT)
    w_mm = item.get("width", round(bw / 283.46))  # 기본: 본문폭
    h_mm = item.get("height", 30)                  # 기본: 30mm
    w = _mm_to_hwp(w_mm)
    h = _mm_to_hwp(h_mm)

    border_color = item.get("border_color", "#000000")
    border_width = item.get("border_width", "0.12 mm")
    bg_color = item.get("bg_color", "#FFFFFF")
    vert_align = item.get("text_align", "CENTER").upper()
    if vert_align not in ("TOP", "CENTER", "BOTTOM"):
        vert_align = "CENTER"

    p = make_paragraph(idgen)
    run = p.find(f".//{{{HP}}}run")

    # hp:rect
    rect = etree.SubElement(run, hp("rect"))
    rect.set("id", idgen.next())
    rect.set("zOrder", "0")
    rect.set("numberingType", "PICTURE")
    rect.set("textWrap", "TOP_AND_BOTTOM")
    rect.set("textFlow", "BOTH_SIDES")
    rect.set("lock", "0")
    rect.set("dropcapstyle", "None")
    rect.set("href", "")
    rect.set("groupLevel", "0")
    rect.set("instid", _next_textbox_instid())
    rect.set("ratio", "0")

    etree.SubElement(rect, hp("offset"), x="0", y="0")
    etree.SubElement(rect, hp("orgSz"), width=str(w), height=str(h))
    etree.SubElement(rect, hp("curSz"), width="0", height="0")
    etree.SubElement(rect, hp("flip"), horizontal="0", vertical="0")

    rot = etree.SubElement(rect, hp("rotationInfo"))
    rot.set("angle", "0")
    rot.set("centerX", "0")
    rot.set("centerY", "0")
    rot.set("rotateimage", "1")

    ri = etree.SubElement(rect, hp("renderingInfo"))
    for mat_tag in ("transMatrix", "scaMatrix", "rotMatrix"):
        mat = etree.SubElement(ri, hc(mat_tag))
        mat.set("e1", "1")
        mat.set("e2", "0")
        mat.set("e3", "0")
        mat.set("e4", "0")
        mat.set("e5", "1")
        mat.set("e6", "0")

    # lineShape (테두리)
    ls = etree.SubElement(rect, hp("lineShape"))
    ls.set("color", border_color)
    ls.set("width", border_width)
    ls.set("style", "SOLID")
    ls.set("endCap", "FLAT")
    ls.set("headStyle", "NORMAL")
    ls.set("tailStyle", "NORMAL")
    ls.set("headfill", "1")
    ls.set("tailfill", "1")
    ls.set("headSz", "SMALL_SMALL")
    ls.set("tailSz", "SMALL_SMALL")
    ls.set("outlineStyle", "NORMAL")
    ls.set("alpha", "0")

    # fillBrush (배경)
    fb = etree.SubElement(rect, hc("fillBrush"))
    wb = etree.SubElement(fb, hc("winBrush"))
    wb.set("faceColor", bg_color)
    wb.set("hatchColor", "#000000")
    wb.set("alpha", "0")

    # shadow
    shd = etree.SubElement(rect, hp("shadow"))
    shd.set("type", "NONE")
    shd.set("color", "#B2B2B2")
    shd.set("offsetX", "0")
    shd.set("offsetY", "0")
    shd.set("alpha", "0")

    # drawText (텍스트 내용)
    dt = etree.SubElement(rect, hp("drawText"))
    dt.set("lastWidth", "4294967295")
    dt.set("name", "")
    dt.set("editable", "0")

    sl = etree.SubElement(dt, hp("subList"))
    sl.set("id", "")
    sl.set("textDirection", "HORIZONTAL")
    sl.set("lineWrap", "BREAK")
    sl.set("vertAlign", vert_align)
    sl.set("linkListIDRef", "0")
    sl.set("linkListNextIDRef", "0")
    sl.set("textWidth", "0")
    sl.set("textHeight", "0")
    sl.set("hasTextRef", "0")
    sl.set("hasNumRef", "0")

    # 내부 텍스트 (여러 줄 지원: lines 또는 단일 text)
    lines = item.get("lines", [item.get("text", "")])
    if isinstance(lines, str):
        lines = [lines]

    inner_cp = _resolve_cp(item, 0, registry) if registry else 0
    inner_pp = _resolve_pp(item, 0, registry) if registry else 0

    for line in lines:
        tp = etree.SubElement(sl, hp("p"))
        tp.set("id", "0")
        tp.set("paraPrIDRef", str(inner_pp))
        tp.set("styleIDRef", "0")
        tp.set("pageBreak", "0")
        tp.set("columnBreak", "0")
        tp.set("merged", "0")
        tr = etree.SubElement(tp, hp("run"))
        tr.set("charPrIDRef", str(inner_cp))
        t_elem = etree.SubElement(tr, hp("t"))
        t_elem.text = str(line)

    tm = etree.SubElement(dt, hp("textMargin"))
    tm.set("left", "283")
    tm.set("right", "283")
    tm.set("top", "283")
    tm.set("bottom", "283")

    # 4 corner points
    etree.SubElement(rect, hc("pt0"), x="0", y="0")
    etree.SubElement(rect, hc("pt1"), x=str(w), y="0")
    etree.SubElement(rect, hc("pt2"), x=str(w), y=str(h))
    etree.SubElement(rect, hc("pt3"), x="0", y=str(h))

    # sz (크기)
    sz = etree.SubElement(rect, hp("sz"))
    sz.set("width", str(w))
    sz.set("widthRelTo", "ABSOLUTE")
    sz.set("height", str(h))
    sz.set("heightRelTo", "ABSOLUTE")
    sz.set("protect", "0")

    # pos (인라인 배치: treatAsChar=1)
    pos = etree.SubElement(rect, hp("pos"))
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

    etree.SubElement(rect, hp("outMargin"), left="0", right="0", top="0", bottom="0")

    sc = etree.SubElement(rect, hp("shapeComment"))
    sc.text = "글상자"

    # 빈 t (rect 뒤)
    etree.SubElement(run, hp("t"))

    return p


# ── 캡션 (Caption) ──────────────────────────────────────────────

def make_caption_paragraph(idgen, item, registry=None):
    """캡션 블록: 이미지·표 아래에 붙는 설명 문단.

    JSON 스펙:
        {
            "type": "caption",
            "label": "그림",        (선택: 그림/표/수식, 기본 "그림")
            "num": 1,               (선택: 번호, 생략 시 자동 증가)
            "text": "설명 텍스트",   (필수)
            "charPr": {...},        (선택)
            "paraPr": {...}         (선택)
        }

    styleIDRef=22 ("캡션" 스타일, 모든 한글 템플릿에 기본 내장).
    paraPr=19 (캡션 기본 문단 속성).
    """
    label = item.get("label", "그림")
    num = item.get("num")
    text = item.get("text", "")

    # 캡션 번호 자동 증가
    if num is None:
        num = _next_caption_num(label)

    # "그림 1. 설명" 형태로 조합
    full_text = f"{label} {num}. {text}" if text else f"{label} {num}."

    cp = _resolve_cp(item, 0, registry)
    pp = _resolve_pp(item, 19, registry)  # paraPr=19 (캡션 기본)

    return make_paragraph(idgen, paraPr=pp, charPr=cp,
                          text=full_text, styleIDRef="22")


# 캡션 번호 자동 카운터 (레이블별)
_CAPTION_COUNTERS = {}


def _next_caption_num(label="그림"):
    """캡션 레이블별 자동 번호 증가."""
    global _CAPTION_COUNTERS
    _CAPTION_COUNTERS[label] = _CAPTION_COUNTERS.get(label, 0) + 1
    return _CAPTION_COUNTERS[label]


# ── 책갈피 (Bookmark) ──────────────────────────────────────────

def make_bookmark_runs(idgen, name, display_text=None, charPr=0):
    """책갈피용 hp:run 3개를 생성 (fieldBegin/fieldEnd 패턴).

    JSON 스펙 (블록 또는 runs 내부에서 사용):
        {
            "type": "bookmark",
            "name": "bookmark_name",   (필수: 책갈피 이름)
            "text": "표시 텍스트",      (선택: 생략 시 빈 책갈피)
            "charPr": 0
        }

    Returns: [run_begin, run_text, run_end] — 3개의 hp:run elements
    """
    text = display_text or ""
    begin_id = idgen.next()
    field_id = _next_field_id()

    # 1) fieldBegin run — type="BOOKMARK"
    run_begin = etree.Element(hp("run"))
    run_begin.set("charPrIDRef", "0")
    ctrl_begin = etree.SubElement(run_begin, hp("ctrl"))
    fb = etree.SubElement(ctrl_begin, hp("fieldBegin"))
    fb.set("id", begin_id)
    fb.set("type", "BOOKMARK")
    fb.set("name", name)
    fb.set("editable", "0")
    fb.set("dirty", "0")
    fb.set("zorder", "-1")
    fb.set("fieldid", field_id)
    fb.set("metaTag", "")

    params = etree.SubElement(fb, hp("parameters"))
    params.set("cnt", "1")
    params.set("name", "")
    _add_param(params, "stringParam", "BookmarkName", name)

    # 2) 표시 텍스트 run (빈 텍스트도 가능 — 포인트 책갈피)
    run_text = etree.Element(hp("run"))
    run_text.set("charPrIDRef", str(charPr))
    t = etree.SubElement(run_text, hp("t"))
    if text:
        t.text = text

    # 3) fieldEnd run
    run_end = etree.Element(hp("run"))
    run_end.set("charPrIDRef", "0")
    ctrl_end = etree.SubElement(run_end, hp("ctrl"))
    fe = etree.SubElement(ctrl_end, hp("fieldEnd"))
    fe.set("beginIDRef", begin_id)
    fe.set("fieldid", field_id)
    etree.SubElement(run_end, hp("t"))

    return [run_begin, run_text, run_end]


def make_bookmark_paragraph(idgen, item, registry=None):
    """책갈피 블록을 hp:p로 생성.

    JSON 스펙:
        {
            "type": "bookmark",
            "name": "my_bookmark",
            "text": "책갈피된 텍스트",  (선택)
            "prefix": "참조: ",         (선택)
            "suffix": "",               (선택)
            "charPr": 0,
            "paraPr": 0
        }
    """
    name = item.get("name", "bookmark")
    text = item.get("text", "")
    prefix = item.get("prefix", "")
    suffix = item.get("suffix", "")

    cp = _resolve_cp(item, 0, registry)
    pp = _resolve_pp(item, 0, registry)

    runs = []

    # prefix run
    if prefix:
        runs.append(make_run(cp, prefix))

    # 책갈피 runs
    bm_runs = make_bookmark_runs(idgen, name, display_text=text, charPr=cp)
    runs.extend(bm_runs)

    # suffix run
    if suffix:
        runs.append(make_run(cp, suffix))

    return make_paragraph(idgen, paraPr=pp, runs=runs)


# ── 필드: 날짜/쪽번호 (Field: Date/PageNumber) ──────────────────

def _build_date_field_runs(idgen, fmt="yyyy-MM-dd", display=None):
    """날짜 필드용 hp:run 3개 생성 (fieldBegin type=DATE).

    fmt: 날짜 형식 문자열 (한컴 DATE 필드 포맷)
         - "yyyy-MM-dd"  → 2026-03-22
         - "yyyy년 M월 d일" → 2026년 3월 22일
         - "yyyy.MM.dd"  → 2026.03.22
    display: 표시 텍스트 (생략 시 현재 날짜로 자동 생성)

    Returns: [run_begin, run_text, run_end]
    """
    from datetime import date
    if display is None:
        today = date.today()
        # 포맷 문자열에서 간단한 치환
        display = fmt.replace("yyyy", str(today.year))
        display = display.replace("MM", f"{today.month:02d}")
        display = display.replace("M", str(today.month))
        display = display.replace("dd", f"{today.day:02d}")
        display = display.replace("d", str(today.day))

    begin_id = idgen.next()
    field_id = _next_field_id()

    # 1) fieldBegin
    run_begin = etree.Element(hp("run"))
    run_begin.set("charPrIDRef", "0")
    ctrl = etree.SubElement(run_begin, hp("ctrl"))
    fb = etree.SubElement(ctrl, hp("fieldBegin"))
    fb.set("id", begin_id)
    fb.set("type", "DATE")
    fb.set("name", "")
    fb.set("editable", "0")
    fb.set("dirty", "0")
    fb.set("zorder", "-1")
    fb.set("fieldid", field_id)
    fb.set("metaTag", "")

    params = etree.SubElement(fb, hp("parameters"))
    params.set("cnt", "2")
    params.set("name", "")
    _add_param(params, "stringParam", "Format", fmt)
    _add_param(params, "integerParam", "DateType", "0")  # 0=작성일

    # 2) 표시 텍스트
    run_text = etree.Element(hp("run"))
    run_text.set("charPrIDRef", "0")
    t = etree.SubElement(run_text, hp("t"))
    t.text = display

    # 3) fieldEnd
    run_end = etree.Element(hp("run"))
    run_end.set("charPrIDRef", "0")
    ctrl_end = etree.SubElement(run_end, hp("ctrl"))
    fe = etree.SubElement(ctrl_end, hp("fieldEnd"))
    fe.set("beginIDRef", begin_id)
    fe.set("fieldid", field_id)
    etree.SubElement(run_end, hp("t"))

    return [run_begin, run_text, run_end]


def _build_page_number_runs(idgen, num_type="PAGE", display="1"):
    """쪽 번호 필드용 hp:run (autoNum 기반).

    num_type: PAGE (현재 쪽), TOTAL_PAGE (전체 쪽수)
    display: 기본 표시 텍스트 (렌더링 시 실제 페이지로 대체됨)

    Returns: [run] — autoNum ctrl + 빈 t를 포함하는 단일 run
    """
    run = etree.Element(hp("run"))
    run.set("charPrIDRef", "0")

    ctrl = _build_autonum_element(num_type)
    run.append(ctrl)
    etree.SubElement(run, hp("t"))

    return [run]


def make_field_paragraph(idgen, item, registry=None):
    """필드 블록을 hp:p로 생성.

    JSON 스펙:
        {
            "type": "field",
            "field_type": "date",          (필수: date/page_number/total_pages)
            "format": "yyyy-MM-dd",        (date 전용: 날짜 형식)
            "display": "2026-03-22",       (선택: 기본 표시 텍스트)
            "prefix": "작성일: ",           (선택)
            "suffix": "",                  (선택)
            "charPr": 0,
            "paraPr": 0
        }
    """
    field_type = item.get("field_type", "date")
    prefix = item.get("prefix", "")
    suffix = item.get("suffix", "")

    cp = _resolve_cp(item, 0, registry)
    pp = _resolve_pp(item, 0, registry)

    runs = []

    if prefix:
        runs.append(make_run(cp, prefix))

    if field_type == "date":
        fmt = item.get("format", "yyyy-MM-dd")
        display = item.get("display")
        runs.extend(_build_date_field_runs(idgen, fmt=fmt, display=display))
    elif field_type == "page_number":
        runs.extend(_build_page_number_runs(idgen, "PAGE"))
    elif field_type == "total_pages":
        runs.extend(_build_page_number_runs(idgen, "TOTAL_PAGE"))

    if suffix:
        runs.append(make_run(cp, suffix))

    return make_paragraph(idgen, paraPr=pp, runs=runs)


# ── 하이퍼링크 ──────────────────────────────────────────────────

_FIELD_ID_COUNTER = 627600000  # fieldBegin/fieldEnd 공유 ID 시작값


def _next_field_id():
    """하이퍼링크 fieldid를 순차 할당."""
    global _FIELD_ID_COUNTER
    _FIELD_ID_COUNTER += 1
    return str(_FIELD_ID_COUNTER)


def make_hyperlink_runs(idgen, url, display_text=None, charPr=0):
    """하이퍼링크용 hp:run 3개를 생성.

    JSON 스펙:
        {
            "type": "hyperlink",       (또는 블록 내부 runs에서 사용)
            "url": "https://...",
            "text": "표시 텍스트",     (생략 시 url 자체가 표시됨)
            "charPr": 0               (표시 텍스트의 charPr, 기본 0)
        }

    Returns: [run_begin, run_text, run_end] — 3개의 hp:run elements
    """
    text = display_text or url
    begin_id = idgen.next()
    field_id = _next_field_id()

    # 1) fieldBegin run
    run_begin = etree.Element(hp("run"))
    run_begin.set("charPrIDRef", "0")
    ctrl_begin = etree.SubElement(run_begin, hp("ctrl"))
    fb = etree.SubElement(ctrl_begin, hp("fieldBegin"))
    fb.set("id", begin_id)
    fb.set("type", "HYPERLINK")
    fb.set("name", "")
    fb.set("editable", "0")
    fb.set("dirty", "0")
    fb.set("zorder", "-1")
    fb.set("fieldid", field_id)
    fb.set("metaTag", "")

    params = etree.SubElement(fb, hp("parameters"))
    params.set("cnt", "6")
    params.set("name", "")

    # Command: URL 내 콜론을 이스케이프 (\:)
    escaped_url = url.replace(":", "\\:")
    _add_param(params, "integerParam", "Prop", "0")
    _add_param(params, "stringParam", "Command", f"{escaped_url};1;0;0;")
    _add_param(params, "stringParam", "Path", url)
    _add_param(params, "stringParam", "Category", "HWPHYPERLINK_TYPE_URL")
    _add_param(params, "stringParam", "TargetType", "HWPHYPERLINK_TARGET_BOOKMARK")
    _add_param(params, "stringParam", "DocOpenType", "HWPHYPERLINK_JUMP_CURRENTTAB")

    # 2) 표시 텍스트 run
    run_text = etree.Element(hp("run"))
    run_text.set("charPrIDRef", str(charPr))
    t = etree.SubElement(run_text, hp("t"))
    t.text = text

    # 3) fieldEnd run
    run_end = etree.Element(hp("run"))
    run_end.set("charPrIDRef", "0")
    ctrl_end = etree.SubElement(run_end, hp("ctrl"))
    fe = etree.SubElement(ctrl_end, hp("fieldEnd"))
    fe.set("beginIDRef", begin_id)
    fe.set("fieldid", field_id)
    etree.SubElement(run_end, hp("t"))

    return [run_begin, run_text, run_end]


def _add_param(parent, tag_type, name, value):
    """hp:parameters에 integerParam/stringParam 추가."""
    elem = etree.SubElement(parent, hp(tag_type))
    elem.set("name", name)
    elem.text = value


def make_hyperlink_paragraph(idgen, item, registry=None):
    """하이퍼링크 블록을 hp:p로 생성.

    JSON 스펙:
        {
            "type": "hyperlink",
            "url": "https://...",
            "text": "표시 텍스트",
            "prefix": "방문: ",     (선택: 링크 앞 텍스트)
            "suffix": " 참조",      (선택: 링크 뒤 텍스트)
            "charPr": 0,
            "paraPr": 0
        }
    """
    url = item.get("url", "")
    display_text = item.get("text", url)
    prefix = item.get("prefix", "")
    suffix = item.get("suffix", "")
    cp = _resolve_cp(item, 0, registry)
    pp = _resolve_pp(item, 0, registry)

    runs = []
    if prefix:
        runs.append(make_run(cp, prefix))

    link_runs = make_hyperlink_runs(idgen, url, display_text, charPr=cp)
    runs.extend(link_runs)

    if suffix:
        runs.append(make_run(cp, suffix))

    return make_paragraph(idgen, paraPr=pp, runs=runs)


# ── 각주/미주 (footnote/endnote) ──────────────────────────────────

_FOOTNOTE_COUNTER = 0  # 각주 번호 자동 증가


def _next_footnote_num():
    global _FOOTNOTE_COUNTER
    _FOOTNOTE_COUNTER += 1
    return _FOOTNOTE_COUNTER


def make_footnote_ctrl(idgen, note_text, note_type="footNote"):
    """각주 또는 미주 hp:ctrl 요소를 생성.

    note_type: "footNote" | "endNote"

    Returns: hp:ctrl element (to be appended to a hp:run)
    """
    num = _next_footnote_num()
    inst_id = idgen.next()

    ctrl = etree.Element(hp("ctrl"))
    note = etree.SubElement(ctrl, hp(note_type))
    note.set("number", str(num))
    note.set("suffixChar", "41")  # ASCII ')' = 0x29 = 41
    note.set("instId", inst_id)

    sublist = etree.SubElement(note, hp("subList"))
    sublist.set("id", "")
    sublist.set("textDirection", "HORIZONTAL")
    sublist.set("lineWrap", "BREAK")
    sublist.set("vertAlign", "TOP")
    sublist.set("linkListIDRef", "0")
    sublist.set("linkListNextIDRef", "0")
    sublist.set("textWidth", "0")
    sublist.set("textHeight", "0")
    sublist.set("hasTextRef", "0")
    sublist.set("hasNumRef", "0")

    # 각주 스타일: paraPr=12 (style 기본), styleIDRef=14 (각주), charPr=2
    style_id = "14" if note_type == "footNote" else "15"
    inner_p = etree.SubElement(sublist, hp("p"))
    inner_p.set("id", "0")
    inner_p.set("paraPrIDRef", "12")
    inner_p.set("styleIDRef", style_id)
    inner_p.set("pageBreak", "0")
    inner_p.set("columnBreak", "0")
    inner_p.set("merged", "0")

    run = etree.SubElement(inner_p, hp("run"))
    run.set("charPrIDRef", "2")

    # autoNum (각주 번호)
    num_ctrl = etree.SubElement(run, hp("ctrl"))
    autonum = etree.SubElement(num_ctrl, hp("autoNum"))
    autonum.set("num", str(num))
    autonum.set("numType", "FOOTNOTE" if note_type == "footNote" else "ENDNOTE")
    fmt = etree.SubElement(autonum, hp("autoNumFormat"))
    fmt.set("type", "DIGIT")
    fmt.set("userChar", "")
    fmt.set("prefixChar", "")
    fmt.set("suffixChar", ")")
    fmt.set("supscript", "0")

    # 각주 텍스트
    t = etree.SubElement(run, hp("t"))
    t.text = f" {note_text}"

    return ctrl


def make_text_with_footnote(idgen, item, registry=None):
    """텍스트와 각주를 포함하는 문단 생성.

    JSON 스펙:
        {
            "type": "text_footnote",
            "text": "본문 텍스트",
            "footnote": "각주 내용",
            "note_type": "footNote"    (선택: footNote/endNote, 기본 footNote)
        }

    각주 마커(위첨자 번호)가 텍스트 끝에 자동 삽입됨.
    """
    text = item.get("text", "")
    note_text = item.get("footnote", item.get("endnote", ""))
    note_type = item.get("note_type", "footNote")
    if item.get("endnote"):
        note_type = "endNote"
    cp = _resolve_cp(item, 0, registry)
    pp = _resolve_pp(item, 0, registry)

    runs = []
    # 본문 텍스트 run
    text_run = make_run(cp, text)
    runs.append(text_run)

    # 각주 ctrl을 포함하는 run
    if note_text:
        fn_run = etree.Element(hp("run"))
        fn_run.set("charPrIDRef", str(cp))
        fn_ctrl = make_footnote_ctrl(idgen, note_text, note_type=note_type)
        fn_run.append(fn_ctrl)
        etree.SubElement(fn_run, hp("t"))
        runs.append(fn_run)

    return make_paragraph(idgen, paraPr=pp, runs=runs)


# ── 머리말/꼬리말 (header/footer) ──────────────────────────────────

# 정렬 → paraPr 매핑 (base 템플릿 기본 paraPr)
# center alignment는 별도 paraPr 필요 — 동적 레지스트리로 해결하거나 fallback
_HF_ALIGN_MAP = {
    "left": "LEFT",
    "center": "CENTER",
    "right": "RIGHT",
    "justify": "JUSTIFY",
}


def _parse_hf_content(text_template):
    """머리말/꼬리말 텍스트에서 {{page}}, {{total_pages}} 등의 플레이스홀더를 파싱.

    Returns: list of segments
        [{"type": "text", "value": "- "},
         {"type": "page_number"},
         {"type": "text", "value": " -"}]
    """
    import re
    segments = []
    pattern = r'\{\{(page|total_pages|page_count)\}\}'
    last_end = 0
    for m in re.finditer(pattern, text_template):
        if m.start() > last_end:
            segments.append({"type": "text", "value": text_template[last_end:m.start()]})
        placeholder = m.group(1)
        if placeholder == "page":
            segments.append({"type": "page_number"})
        elif placeholder in ("total_pages", "page_count"):
            segments.append({"type": "total_pages"})
        last_end = m.end()
    if last_end < len(text_template):
        segments.append({"type": "text", "value": text_template[last_end:]})
    return segments


def _build_autonum_element(num_type="PAGE"):
    """hp:autoNum 요소 생성.

    num_type: PAGE (쪽 번호), TOTAL_PAGE (전체 쪽수)
    """
    ctrl = etree.Element(hp("ctrl"))
    autonum = etree.SubElement(ctrl, hp("autoNum"))
    autonum.set("num", "1")
    autonum.set("numType", num_type)
    fmt = etree.SubElement(autonum, hp("autoNumFormat"))
    fmt.set("type", "DIGIT")
    fmt.set("userChar", "")
    fmt.set("prefixChar", "")
    fmt.set("suffixChar", "")
    fmt.set("supscript", "0")
    return ctrl


def make_header_footer_paragraph(idgen, hf_def, hf_type="header",
                                  body_width=None, registry=None):
    """머리말 또는 꼬리말 ctrl을 포함하는 hp:p 요소 생성.

    hf_def (dict):
        text: str — 콘텐츠 텍스트. {{page}} / {{total_pages}} 플레이스홀더 지원.
        align: str — left/center/right (기본: center for header, right for footer)
        applyPageType: str — BOTH/EVEN/ODD (기본: BOTH)
        charPr: int/dict — 문자 속성 (기본: 1, 9pt 헤더/푸터 스타일)
        paraPr: int/dict — 문단 속성 (기본: 자동 — align 기반)

    hf_type: "header" | "footer"

    Returns: hp:ctrl element (to be placed inside a hp:run)
    """
    bw = body_width or BODY_WIDTH
    text_template = hf_def.get("text", "{{page}}")
    align = hf_def.get("align", "center" if hf_type == "header" else "right")
    apply_page = hf_def.get("applyPageType", "BOTH")

    # charPr/paraPr 해석
    cp = hf_def.get("charPr", 1)  # 기본: 9pt 머리말 스타일
    pp = hf_def.get("paraPr", 0)

    # 동적 레지스트리로 paraPr 해석
    if registry and isinstance(pp, dict):
        pp = registry.resolve_paraPr(pp)
    elif isinstance(pp, dict):
        pp = 0  # fallback

    if registry and isinstance(cp, dict):
        cp = registry.resolve_charPr(cp)
    elif isinstance(cp, dict):
        cp = 1  # fallback

    # 정렬을 위한 동적 paraPr 생성 (align이 지정되었고 pp가 기본값일 때)
    if align != "justify" and pp == 0 and registry:
        align_val = _HF_ALIGN_MAP.get(align, "CENTER")
        pp = registry.resolve_paraPr({"align": align_val, "lineSpacing": 150})
    elif align != "justify" and pp == 0:
        # 레지스트리 없이도 paraPr 0은 JUSTIFY인데 center/right 필요
        # → 하드코딩 대안은 없으므로 registry 사용 권장
        pass

    # ctrl element 생성
    ctrl_wrap = etree.Element(hp("ctrl"))
    hf_elem = etree.SubElement(ctrl_wrap, hp(hf_type))
    # header/footer id: header=1, footer=2 (convention)
    hf_id = "1" if hf_type == "header" else "2"
    hf_elem.set("id", hf_id)
    hf_elem.set("applyPageType", apply_page)

    # subList
    sublist = etree.SubElement(hf_elem, hp("subList"))
    sublist.set("id", "")
    sublist.set("textDirection", "HORIZONTAL")
    sublist.set("lineWrap", "BREAK")
    sublist.set("vertAlign", "TOP" if hf_type == "header" else "BOTTOM")
    sublist.set("linkListIDRef", "0")
    sublist.set("linkListNextIDRef", "0")
    sublist.set("textWidth", str(bw))
    sublist.set("textHeight", "4252")  # 기본 머리말/꼬리말 높이 (≈15mm)
    sublist.set("hasTextRef", "0")
    sublist.set("hasNumRef", "0")

    # 내부 paragraph
    inner_p = etree.SubElement(sublist, hp("p"))
    inner_p.set("id", "0")
    inner_p.set("paraPrIDRef", str(pp))
    inner_p.set("styleIDRef", "13")  # "머리말" 스타일 (대부분 템플릿에 존재)
    inner_p.set("pageBreak", "0")
    inner_p.set("columnBreak", "0")
    inner_p.set("merged", "0")

    # 콘텐츠 run 생성
    segments = _parse_hf_content(text_template)

    run = etree.SubElement(inner_p, hp("run"))
    run.set("charPrIDRef", str(cp))

    for seg in segments:
        if seg["type"] == "text":
            t = etree.SubElement(run, hp("t"))
            t.text = seg["value"]
        elif seg["type"] == "page_number":
            autonum_ctrl = _build_autonum_element("PAGE")
            run.append(autonum_ctrl)
            etree.SubElement(run, hp("t"))  # 빈 t 요소 (한컴 관례)
        elif seg["type"] == "total_pages":
            autonum_ctrl = _build_autonum_element("TOTAL_PAGE")
            run.append(autonum_ctrl)
            etree.SubElement(run, hp("t"))

    # 세그먼트가 없으면 빈 t
    if not segments:
        etree.SubElement(run, hp("t"))

    return ctrl_wrap


def _inject_header_footer(sec, idgen, json_data, body_width=None, registry=None):
    """build_section에서 호출: JSON의 header/footer 정의를 sec에 삽입.

    머리말/꼬리말 ctrl은 secPr 다음 문단의 run에 배치.
    """
    header_def = json_data.get("header")
    footer_def = json_data.get("footer")

    if not header_def and not footer_def:
        return

    # 머리말/꼬리말 전용 빈 문단 삽입 (secPr 문단 바로 뒤)
    hf_p = etree.Element(hp("p"))
    hf_p.set("id", idgen.next())
    hf_p.set("paraPrIDRef", "0")
    hf_p.set("styleIDRef", "0")
    hf_p.set("pageBreak", "0")
    hf_p.set("columnBreak", "0")
    hf_p.set("merged", "0")

    run = etree.SubElement(hf_p, hp("run"))
    run.set("charPrIDRef", "0")

    if header_def:
        hf_ctrl = make_header_footer_paragraph(
            idgen, header_def, hf_type="header",
            body_width=body_width, registry=registry)
        run.append(hf_ctrl)

    if footer_def:
        hf_ctrl = make_header_footer_paragraph(
            idgen, footer_def, hf_type="footer",
            body_width=body_width, registry=registry)
        run.append(hf_ctrl)

    # 빈 t 마무리
    etree.SubElement(run, hp("t"))

    # secPr 문단(index 0) 바로 뒤에 삽입
    sec.insert(1, hf_p)


# ── KCUP 표지 생성 함수 ──────────────────────────────────────────

def make_kcup_cover(idgen, item):
    """KCUP 표지 블록: 빈줄 + 제목(19pt HY헤드라인M) + 빈줄 + 날짜 + 빈줄×2.

    JSON DSL:
        {"type": "kcup_cover", "title": "문서 제목", "date": "2026. 3. 22.",
         "author": "OO팀"}
    author는 선택. 생략 시 날짜만 표시.
    """
    title = item.get("title", item.get("text", ""))
    date = item.get("date", "")
    author = item.get("author", "")

    elements = []

    # 상단 빈줄 3개 (표지 여백)
    for _ in range(3):
        elements.append(make_empty(idgen, paraPr=KCUP_PP["box"], charPr=KCUP_CP["gap14"]))

    # 제목 (charPr=15: 19pt HY헤드라인M 볼드, paraPr=20: CENTER)
    cp_title = item.get("charPr", KCUP_CP["cover_title"])
    pp_center = 20  # CENTER 정렬
    elements.append(make_paragraph(idgen, paraPr=pp_center, charPr=cp_title, text=title))

    # 빈줄 2개
    for _ in range(2):
        elements.append(make_empty(idgen, paraPr=pp_center, charPr=KCUP_CP["body"]))

    # 날짜
    if date:
        elements.append(make_paragraph(idgen, paraPr=pp_center, charPr=KCUP_CP["body"], text=date))

    # 작성자/소속
    if author:
        elements.append(make_empty(idgen, paraPr=pp_center, charPr=KCUP_CP["body"]))
        elements.append(make_paragraph(idgen, paraPr=pp_center, charPr=KCUP_CP["body"], text=author))

    # 하단 빈줄 2개 (본문과 분리)
    for _ in range(2):
        elements.append(make_empty(idgen, paraPr=KCUP_PP["box"], charPr=KCUP_CP["gap14"]))

    return elements


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
_KCUP_PASSTHROUGH = {"text", "empty", "heading", "bullet", "numbered", "kcup_cover",
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

    # 첫 문단: secPr (다단 설정 포함)
    columns = json_data.get("columns")
    secpr_p = make_secpr_paragraph(idgen, base_section_path, columns=columns)
    sec.append(secpr_p)

    # 머리말/꼬리말 삽입 (secPr 문단 바로 뒤)
    _inject_header_footer(sec, idgen, json_data,
                          body_width=body_width, registry=registry)

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

        elif item_type in ("text", "paragraph"):
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
            sec.append(make_table(idgen, item, body_width=body_width,
                                   registry=registry))

        elif item_type == "label_value":
            sec.append(make_label_value(idgen, item, body_width=body_width,
                                         registry=registry))

        elif item_type == "signature":
            for p in make_signature(idgen, item):
                sec.append(p)

        elif item_type == "pagebreak":
            sec.append(make_paragraph(idgen, pageBreak="1"))

        elif item_type == "image":
            img_p, _img_info = make_image_paragraph(idgen, item,
                                                     body_width=body_width)
            sec.append(img_p)

        elif item_type == "textbox":
            sec.append(make_textbox_paragraph(idgen, item,
                                               body_width=body_width,
                                               registry=registry))

        elif item_type == "hyperlink":
            sec.append(make_hyperlink_paragraph(idgen, item, registry=registry))

        elif item_type in ("text_footnote", "text_endnote", "footnote"):
            sec.append(make_text_with_footnote(idgen, item, registry=registry))

        elif item_type == "caption":
            sec.append(make_caption_paragraph(idgen, item, registry=registry))

        elif item_type == "bookmark":
            sec.append(make_bookmark_paragraph(idgen, item, registry=registry))

        elif item_type == "field":
            sec.append(make_field_paragraph(idgen, item, registry=registry))

        # ── KCUP 전용 타입 ────────────────────────────────
        elif item_type == "kcup_cover":
            for el in make_kcup_cover(idgen, item):
                sec.append(el)

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


def build_multi_sections(json_data, base_section_path=None, template=None, registry=None):
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

        # 머리말/꼬리말 (섹션별 또는 전역 header/footer)
        hf_data = {}
        if "header" in sec_def or "header" in json_data:
            hf_data["header"] = sec_def.get("header", json_data.get("header"))
        if "footer" in sec_def or "footer" in json_data:
            hf_data["footer"] = sec_def.get("footer", json_data.get("footer"))
        if hf_data:
            _inject_header_footer(sec, idgen, hf_data, body_width=body_width)

        # 콘텐츠
        content = sec_def.get("blocks", [])
        if not content:
            content = sec_def.get("content", [])

        if sec_def.get("auto_spacing", json_data.get("auto_spacing", True)):
            content = auto_spacing(content)

        for item in content:
            elements = _build_item(idgen, item, body_width, template, registry=registry)
            for el in elements:
                sec.append(el)

        tree = etree.ElementTree(sec)
        results.append((f"section{i}.xml", tree))

    return results


def _build_item(idgen, item, body_width, template, registry=None):
    """단일 블록 아이템을 파싱해서 요소 리스트를 반환.
    build_section의 dispatch 로직을 재사용 가능한 함수로 분리."""
    item_type = item.get("type", "text")
    elements = []

    if item_type == "empty":
        elements.append(make_empty(idgen))

    elif item_type in ("text", "paragraph"):
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
        elements.append(make_table(idgen, item, body_width=body_width,
                                    registry=registry))

    elif item_type == "label_value":
        elements.append(make_label_value(idgen, item, body_width=body_width,
                                          registry=registry))

    elif item_type == "signature":
        for p in make_signature(idgen, item):
            elements.append(p)

    elif item_type == "pagebreak":
        elements.append(make_paragraph(idgen, pageBreak="1"))

    elif item_type == "image":
        img_p, _img_info = make_image_paragraph(idgen, item,
                                                  body_width=body_width)
        elements.append(img_p)

    elif item_type == "hyperlink":
        elements.append(make_hyperlink_paragraph(idgen, item))

    elif item_type in ("text_footnote", "text_endnote", "footnote"):
        elements.append(make_text_with_footnote(idgen, item))

    # ── KCUP 전용 타입 ────────────────────────────────
    elif item_type == "kcup_cover":
        elements.extend(make_kcup_cover(idgen, item))
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
        results = build_multi_sections(data, base, template=args.template, registry=registry)
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
