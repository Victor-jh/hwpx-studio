#!/usr/bin/env python3
"""read_document.py — HWPX → JSON 역변환기 (Phase 2).

HWPX 문서를 파싱하여 section_builder.py 호환 JSON으로 변환.
라운드트립(HWPX → JSON → HWPX) 지원이 핵심 목표.

Usage:
    python read_document.py document.hwpx
    python read_document.py document.hwpx -o output.json
    python read_document.py document.hwpx --pretty
    python read_document.py document.hwpx --include-styles

내부 동작:
    1. HWPX ZIP 해제 → section0.xml + header.xml 추출
    2. header.xml → 스타일 레지스트리 구축 (charPr/paraPr ID → 스펙 매핑)
    3. section0.xml → 블록 타입 감지 + JSON 변환
    4. 메타데이터(template, header/footer) 추출
"""

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any, Optional

from lxml import etree

# ── 네임스페이스 ────────────────────────────────────────────────
HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HS = "http://www.hancom.co.kr/hwpml/2011/section"
HC = "http://www.hancom.co.kr/hwpml/2011/core"
HH = "http://www.hancom.co.kr/hwpml/2011/head"
HWPUNITCHAR_NS = "http://www.hancom.co.kr/hwpml/2016/HwpUnitChar"

NS = {
    "hp": HP, "hs": HS, "hc": HC, "hh": HH,
    "hp10": "http://www.hancom.co.kr/hwpml/2016/paragraph",
}


def _hp(tag: str) -> str:
    return f"{{{HP}}}{tag}"


def _hs(tag: str) -> str:
    return f"{{{HS}}}{tag}"


def _hc(tag: str) -> str:
    return f"{{{HC}}}{tag}"


def _hh(tag: str) -> str:
    return f"{{{HH}}}{tag}"


# ── HEADING_STYLES 역매핑 (paraPrIDRef → heading level) ────────
HEADING_STYLES = {
    1: {"charPr": 7, "paraPr": 20},
    2: {"charPr": 8, "paraPr": 0},
    3: {"charPr": 13, "paraPr": 27},
}

# paraPr → heading level 역매핑 (charPr도 함께 확인)
_HEADING_REVERSE = {}
for lvl, st in HEADING_STYLES.items():
    _HEADING_REVERSE[(st["paraPr"], st["charPr"])] = lvl

NUMBERED_STYLES = {
    "circle":  {"paraPr": 24, "charPr": 0},
    "dot":     {"paraPr": 25, "charPr": 0},
    "roman":   {"paraPr": 24, "charPr": 0},
    "dash":    {"paraPr": 26, "charPr": 0},
}

ROMAN = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ"]
CIRCLE_NUMS = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩",
               "⑪", "⑫", "⑬", "⑭", "⑮", "⑯", "⑰", "⑱", "⑲", "⑳"]

# KCUP 상수 (section_builder.py와 동일)
KCUP_CP = {
    "cover_title": 15, "body": 16, "bold": 17, "box": 18,
    "gap14": 19, "gap14_alt": 20, "gap10": 21, "bracket": 22,
}
KCUP_PP = {"o": 26, "box": 28, "dash": 30, "gap": 31}

# KCUP paraPr/charPr 역매핑
_KCUP_PP_REV = {v: k for k, v in KCUP_PP.items()}
_KCUP_CP_REV = {v: k for k, v in KCUP_CP.items()}


# ── 스타일 레지스트리 (header.xml 파싱) ──────────────────────────

class StyleRegistry:
    """header.xml에서 charPr/paraPr/borderFill 스펙을 ID로 조회."""

    def __init__(self):
        self.char_props: dict[int, dict] = {}   # id → spec
        self.para_props: dict[int, dict] = {}   # id → spec
        self.border_fills: dict[int, dict] = {}  # id → spec
        self.fonts: dict[str, dict[int, str]] = {}  # lang → {id: face}

    @classmethod
    def from_xml(cls, header_xml: bytes) -> "StyleRegistry":
        """header.xml 바이트에서 스타일 레지스트리 구축."""
        reg = cls()
        root = etree.fromstring(header_xml)

        # charProperties
        for cp in root.iter(_hh("charPr")):
            cid = int(cp.get("id", "0"))
            spec = {
                "height": int(cp.get("height", "1000")),
                "textColor": cp.get("textColor", "#000000"),
                "bold": cp.find(_hh("bold")) is not None,
                "italic": cp.find(_hh("italic")) is not None,
            }
            # fontRef
            fr = cp.find(_hh("fontRef"))
            if fr is not None:
                spec["fontRef"] = int(fr.get("hangul", "0"))
            # spacing
            sp = cp.find(_hh("spacing"))
            if sp is not None:
                spec["spacing"] = int(sp.get("hangul", "0"))
            # underline
            ul = cp.find(_hh("underline"))
            if ul is not None:
                spec["underline"] = ul.get("type", "NONE")
            # strikeout
            so = cp.find(_hh("strikeout"))
            if so is not None:
                spec["strikeout"] = so.get("shape", "NONE")

            reg.char_props[cid] = spec

        # paraProperties
        for pp in root.iter(_hh("paraPr")):
            pid = int(pp.get("id", "0"))
            spec = {
                "tabPrIDRef": pp.get("tabPrIDRef", "0"),
                "snapToGrid": pp.get("snapToGrid", "1"),
            }
            # align
            align_el = pp.find(_hh("align"))
            if align_el is not None:
                spec["align"] = align_el.get("horizontal", "JUSTIFY")
                spec["vertAlign"] = align_el.get("vertical", "BASELINE")

            # margin + lineSpacing: hp:switch/hp:case 또는 직접
            # switch 패턴에서 첫 번째 case의 값을 우선 사용
            switch = pp.find(f"{_hp('switch')}")
            if switch is not None:
                case = switch.find(_hp("case"))
                target = case if case is not None else switch.find(_hp("default"))
            else:
                target = pp

            if target is not None:
                margin_el = target.find(_hh("margin"))
                if margin_el is not None:
                    margin = {}
                    for mk in ("intent", "left", "right", "prev", "next"):
                        child = margin_el.find(_hc(mk))
                        if child is not None:
                            margin[mk] = int(child.get("value", "0"))
                    spec["margin"] = margin

                ls_el = target.find(_hh("lineSpacing"))
                if ls_el is not None:
                    spec["lineSpacing"] = int(ls_el.get("value", "160"))
                    spec["lineSpacingType"] = ls_el.get("type", "PERCENT")

            # border
            border_el = pp.find(_hh("border"))
            if border_el is not None:
                spec["borderFillIDRef"] = border_el.get("borderFillIDRef", "2")

            reg.para_props[pid] = spec

        # borderFills
        for bf in root.iter(_hh("borderFill")):
            bid = int(bf.get("id", "0"))
            spec = {}
            for side in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"):
                b = bf.find(_hh(side))
                if b is not None:
                    spec[side] = {
                        "type": b.get("type", "NONE"),
                        "width": b.get("width", "0.1 mm"),
                        "color": b.get("color", "#000000"),
                    }
            # bg color
            fb = bf.find(f".//{_hc('winBrush')}")
            if fb is not None:
                spec["bg"] = fb.get("faceColor")
            reg.border_fills[bid] = spec

        # fontfaces
        for ff in root.iter(_hh("fontface")):
            lang = ff.get("lang", "")
            fonts = {}
            for font in ff.findall(_hh("font")):
                fid = int(font.get("id", "0"))
                fonts[fid] = font.get("face", "")
            reg.fonts[lang] = fonts

        return reg

    def get_charPr_spec(self, cid: int) -> dict:
        return self.char_props.get(cid, {})

    def get_paraPr_spec(self, pid: int) -> dict:
        return self.para_props.get(pid, {})

    def get_font_name(self, font_id: int, lang: str = "HANGUL") -> str:
        return self.fonts.get(lang, {}).get(font_id, "")


# ── 텍스트/run 추출 ──────────────────────────────────────────────

def _extract_run_text(run_el) -> str:
    """hp:run에서 모든 hp:t 텍스트를 결합."""
    texts = []
    for t in run_el.findall(_hp("t")):
        if t.text:
            texts.append(t.text)
    return "".join(texts)


def _extract_runs(p_el) -> list[dict]:
    """hp:p에서 모든 run의 charPrIDRef + text 추출.

    ctrl을 포함하는 run은 ctrl 정보도 포함.
    """
    runs = []
    for run in p_el.findall(_hp("run")):
        charPr = int(run.get("charPrIDRef", "0"))
        text = _extract_run_text(run)
        entry = {"charPr": charPr, "text": text}

        # ctrl 감지 (fieldBegin, footNote, endNote, autoNum 등)
        ctrl = run.find(_hp("ctrl"))
        if ctrl is not None:
            entry["_ctrl"] = ctrl

        # 인라인 객체 감지
        tbl = run.find(_hp("tbl"))
        if tbl is not None:
            entry["_tbl"] = tbl

        pic = run.find(_hp("pic"))
        if pic is not None:
            entry["_pic"] = pic

        rect = run.find(_hp("rect"))
        if rect is not None:
            entry["_rect"] = rect

        runs.append(entry)
    return runs


def _para_full_text(runs: list[dict]) -> str:
    """run 리스트에서 전체 텍스트를 결합."""
    return "".join(r.get("text", "") for r in runs)


# ── 블록 타입 감지 ────────────────────────────────────────────────

def _detect_secpr(p_el) -> bool:
    """secPr를 포함하는 첫 문단인지 확인."""
    return p_el.find(f".//{_hp('secPr')}") is not None


def _detect_header_footer(p_el) -> Optional[dict]:
    """머리말/꼬리말 ctrl을 포함하는 문단인지 확인."""
    header = p_el.find(f".//{_hp('header')}")
    footer = p_el.find(f".//{_hp('footer')}")
    if header is None and footer is None:
        return None

    result = {}
    for hf_el, hf_type in [(header, "header"), (footer, "footer")]:
        if hf_el is None:
            continue
        hf_info = {
            "applyPageType": hf_el.get("applyPageType", "BOTH"),
        }
        # subList → p → run → t (텍스트 추출)
        sublist = hf_el.find(_hp("subList"))
        if sublist is not None:
            inner_p = sublist.find(_hp("p"))
            if inner_p is not None:
                hf_info["paraPr"] = int(inner_p.get("paraPrIDRef", "0"))
                hf_info["styleIDRef"] = inner_p.get("styleIDRef", "0")
                # run들에서 텍스트 + autoNum 추출
                text_parts = []
                for run in inner_p.findall(_hp("run")):
                    hf_info["charPr"] = int(run.get("charPrIDRef", "0"))
                    for child in run:
                        tag = etree.QName(child.tag).localname
                        if tag == "t" and child.text:
                            text_parts.append(child.text)
                        elif tag == "ctrl":
                            autonum = child.find(_hp("autoNum"))
                            if autonum is not None:
                                num_type = autonum.get("numType", "")
                                if num_type == "PAGE":
                                    text_parts.append("{{page}}")
                                elif num_type == "TOTAL_PAGE":
                                    text_parts.append("{{total_pages}}")
                hf_info["text"] = "".join(text_parts)

                # align 추정
                pp_id = hf_info.get("paraPr", 0)
                # align은 paraPr에서 가져와야 하지만 여기서는 단순 추정
                align = "center" if hf_type == "header" else "right"
                hf_info["align"] = align

        result[hf_type] = hf_info
    return result


def _detect_table(runs: list[dict]) -> Optional[dict]:
    """hp:tbl을 포함하는 문단 → table 블록."""
    for r in runs:
        tbl = r.get("_tbl")
        if tbl is not None:
            return _parse_table(tbl)
    return None


def _detect_image(runs: list[dict]) -> Optional[dict]:
    """hp:pic을 포함하는 문단 → image 블록."""
    for r in runs:
        pic = r.get("_pic")
        if pic is not None:
            return _parse_image(pic)
    return None


def _detect_textbox(runs: list[dict]) -> Optional[dict]:
    """hp:rect을 포함하는 문단 → textbox 블록."""
    for r in runs:
        rect = r.get("_rect")
        if rect is not None:
            return _parse_textbox(rect)
    return None


def _detect_field(runs: list[dict]) -> Optional[dict]:
    """fieldBegin(HYPERLINK/BOOKMARK/DATE) 또는 autoNum → 해당 블록 타입."""
    for r in runs:
        ctrl = r.get("_ctrl")
        if ctrl is None:
            continue

        # fieldBegin
        fb = ctrl.find(_hp("fieldBegin"))
        if fb is not None:
            ftype = fb.get("type", "")
            if ftype == "HYPERLINK":
                return _parse_hyperlink(runs)
            elif ftype == "BOOKMARK":
                return _parse_bookmark(runs, fb)
            elif ftype == "DATE":
                return _parse_date_field(runs, fb)

        # footNote / endNote
        fn = ctrl.find(_hp("footNote"))
        if fn is not None:
            return _parse_footnote(runs, fn, "footNote")
        en = ctrl.find(_hp("endNote"))
        if en is not None:
            return _parse_footnote(runs, en, "endNote")

        # autoNum (쪽 번호 등)
        autonum = ctrl.find(_hp("autoNum"))
        if autonum is not None:
            num_type = autonum.get("numType", "")
            if num_type == "PAGE":
                return {"type": "field", "field_type": "page_number"}
            elif num_type == "TOTAL_PAGE":
                return {"type": "field", "field_type": "total_pages"}

    return None


# ── 복합 블록 파서 ────────────────────────────────────────────────

def _parse_table(tbl) -> dict:
    """hp:tbl → table JSON."""
    result: dict[str, Any] = {"type": "table"}

    # 기본 속성
    col_count = int(tbl.get("colCnt", "1"))
    row_count = int(tbl.get("rowCnt", "1"))
    result["colCount"] = col_count

    bf_ref = tbl.get("borderFillIDRef", "3")
    result["tableBorderFill"] = bf_ref

    has_repeat_header = tbl.get("repeatHeader", "0") == "1"

    # 행/셀 파싱
    headers = []
    rows = []
    merge_map = []

    for row_idx, tr in enumerate(tbl.findall(_hp("tr"))):
        row_cells = []
        for tc in tr.findall(_hp("tc")):
            is_header = tc.get("header", "0") == "1"
            bf = tc.get("borderFillIDRef", "3")

            # 셀 주소
            addr = tc.find(_hp("cellAddr"))
            col_addr = int(addr.get("colAddr", "0")) if addr is not None else 0
            row_addr = int(addr.get("rowAddr", "0")) if addr is not None else 0

            # 셀 병합
            span = tc.find(_hp("cellSpan"))
            col_span = int(span.get("colSpan", "1")) if span is not None else 1
            row_span = int(span.get("rowSpan", "1")) if span is not None else 1

            if col_span > 1 or row_span > 1:
                merge_map.append({
                    "row": row_addr, "col": col_addr,
                    "colSpan": col_span, "rowSpan": row_span,
                })

            # 셀 텍스트 추출 (subList → p)
            cell_text = _extract_cell_content(tc)
            row_cells.append(cell_text)

        if is_header and has_repeat_header and row_idx == 0:
            headers = row_cells
        else:
            rows.append(row_cells)

    if headers:
        result["headers"] = headers
    result["rows"] = rows
    if merge_map:
        result["merge"] = merge_map

    return result


def _extract_cell_content(tc) -> Any:
    """hp:tc 셀에서 콘텐츠 추출.

    단일 문단+단일 run → str
    단일 문단+다중 run → {"runs": [...]}
    다중 문단 → {"lines": [...]}
    """
    sublist = tc.find(_hp("subList"))
    if sublist is None:
        return ""

    paragraphs = sublist.findall(_hp("p"))
    if not paragraphs:
        return ""

    if len(paragraphs) == 1:
        p = paragraphs[0]
        runs = _extract_runs(p)
        if len(runs) == 0:
            return ""
        if len(runs) == 1:
            return runs[0].get("text", "")
        # 다중 run
        return {
            "runs": [{"charPr": r["charPr"], "text": r["text"]} for r in runs
                     if r.get("text")]
        }

    # 다중 문단
    lines = []
    for p in paragraphs:
        runs = _extract_runs(p)
        if len(runs) == 0:
            lines.append("")
        elif len(runs) == 1:
            text = runs[0].get("text", "")
            cp = runs[0].get("charPr", 0)
            if cp != 0:
                lines.append({"text": text, "charPr": cp})
            else:
                lines.append(text)
        else:
            lines.append({
                "runs": [{"charPr": r["charPr"], "text": r["text"]}
                         for r in runs if r.get("text")]
            })
    return {"lines": lines}


def _parse_image(pic) -> dict:
    """hp:pic → image JSON."""
    result: dict[str, Any] = {"type": "image"}

    # binaryItemIDRef (이미지 소스)
    img = pic.find(_hc("img"))
    if img is not None:
        result["binaryItemIDRef"] = img.get("binaryItemIDRef", "")

    # 크기 (orgSz)
    orgSz = pic.find(_hp("orgSz"))
    if orgSz is not None:
        w = int(orgSz.get("width", "0"))
        h = int(orgSz.get("height", "0"))
        if w > 0:
            result["width_mm"] = round(w / 283.46, 1)
        if h > 0:
            result["height_mm"] = round(h / 283.46, 1)

    return result


def _parse_textbox(rect) -> dict:
    """hp:rect → textbox JSON."""
    result: dict[str, Any] = {"type": "textbox"}

    # 크기
    sz = rect.find(_hp("sz"))
    if sz is not None:
        w = int(sz.get("width", "0"))
        h = int(sz.get("height", "0"))
        if w > 0:
            result["width"] = round(w / 283.46, 1)
        if h > 0:
            result["height"] = round(h / 283.46, 1)

    # 테두리
    ls = rect.find(_hp("lineShape"))
    if ls is not None:
        result["border_color"] = ls.get("color", "#000000")
        result["border_width"] = ls.get("width", "0.12 mm")

    # 배경색
    wb = rect.find(f".//{_hc('winBrush')}")
    if wb is not None:
        result["bg_color"] = wb.get("faceColor", "#FFFFFF")

    # 텍스트 내용
    dt = rect.find(_hp("drawText"))
    if dt is not None:
        sl = dt.find(_hp("subList"))
        if sl is not None:
            result["text_align"] = sl.get("vertAlign", "CENTER")
            lines = []
            for p in sl.findall(_hp("p")):
                runs = _extract_runs(p)
                text = _para_full_text(runs)
                if text:
                    lines.append(text)
            if len(lines) == 1:
                result["text"] = lines[0]
            elif len(lines) > 1:
                result["lines"] = lines

    return result


def _parse_hyperlink(runs: list[dict]) -> dict:
    """fieldBegin(HYPERLINK) → hyperlink JSON."""
    result: dict[str, Any] = {"type": "hyperlink"}

    # runs[0]의 ctrl에서 URL 추출
    for r in runs:
        ctrl = r.get("_ctrl")
        if ctrl is None:
            continue
        fb = ctrl.find(_hp("fieldBegin"))
        if fb is not None and fb.get("type") == "HYPERLINK":
            params = fb.find(_hp("parameters"))
            if params is not None:
                for param in params:
                    if param.get("name") == "Path" and param.text:
                        result["url"] = param.text
                    elif param.get("name") == "Command" and param.text:
                        # fallback: Command에서 URL 추출
                        if "url" not in result:
                            cmd = param.text.replace("\\:", ":")
                            result["url"] = cmd.split(";")[0]

    # 표시 텍스트: fieldBegin/fieldEnd 사이의 run들
    display_texts = []
    in_field = False
    for r in runs:
        ctrl = r.get("_ctrl")
        if ctrl is not None:
            fb = ctrl.find(_hp("fieldBegin"))
            if fb is not None and fb.get("type") == "HYPERLINK":
                in_field = True
                continue
            fe = ctrl.find(_hp("fieldEnd"))
            if fe is not None:
                in_field = False
                continue
        if in_field and r.get("text"):
            display_texts.append(r["text"])

    if display_texts:
        result["text"] = "".join(display_texts)

    # prefix/suffix: fieldBegin 앞과 fieldEnd 뒤의 텍스트
    prefix_parts = []
    suffix_parts = []
    state = "before"  # before → in_field → after
    for r in runs:
        ctrl = r.get("_ctrl")
        if ctrl is not None:
            fb = ctrl.find(_hp("fieldBegin"))
            if fb is not None and fb.get("type") == "HYPERLINK":
                state = "in_field"
                continue
            fe = ctrl.find(_hp("fieldEnd"))
            if fe is not None:
                state = "after"
                continue
        text = r.get("text", "")
        if state == "before" and text:
            prefix_parts.append(text)
        elif state == "after" and text:
            suffix_parts.append(text)

    if prefix_parts:
        result["prefix"] = "".join(prefix_parts)
    if suffix_parts:
        result["suffix"] = "".join(suffix_parts)

    return result


def _parse_bookmark(runs: list[dict], fb_el) -> dict:
    """fieldBegin(BOOKMARK) → bookmark JSON."""
    result: dict[str, Any] = {"type": "bookmark"}
    result["name"] = fb_el.get("name", "")

    # parameters에서 BookmarkName 추출
    params = fb_el.find(_hp("parameters"))
    if params is not None:
        for param in params:
            if param.get("name") == "BookmarkName" and param.text:
                result["name"] = param.text

    # 표시 텍스트
    display_texts = []
    in_field = False
    for r in runs:
        ctrl = r.get("_ctrl")
        if ctrl is not None:
            fb = ctrl.find(_hp("fieldBegin"))
            if fb is not None and fb.get("type") == "BOOKMARK":
                in_field = True
                continue
            fe = ctrl.find(_hp("fieldEnd"))
            if fe is not None:
                in_field = False
                continue
        if in_field and r.get("text"):
            display_texts.append(r["text"])

    if display_texts:
        result["text"] = "".join(display_texts)

    return result


def _parse_date_field(runs: list[dict], fb_el) -> dict:
    """fieldBegin(DATE) → field JSON."""
    result: dict[str, Any] = {"type": "field", "field_type": "date"}

    params = fb_el.find(_hp("parameters"))
    if params is not None:
        for param in params:
            if param.get("name") == "Format" and param.text:
                result["format"] = param.text

    # 표시 텍스트 추출
    display_texts = []
    in_field = False
    for r in runs:
        ctrl = r.get("_ctrl")
        if ctrl is not None:
            fb = ctrl.find(_hp("fieldBegin"))
            if fb is not None and fb.get("type") == "DATE":
                in_field = True
                continue
            fe = ctrl.find(_hp("fieldEnd"))
            if fe is not None:
                in_field = False
                continue
        if in_field and r.get("text"):
            display_texts.append(r["text"])
    if display_texts:
        result["display"] = "".join(display_texts)

    return result


def _parse_footnote(runs: list[dict], fn_el, note_type: str) -> dict:
    """footNote/endNote ctrl → text_footnote/text_endnote JSON."""
    is_endnote = note_type == "endNote"
    result: dict[str, Any] = {
        "type": "text_endnote" if is_endnote else "text_footnote",
    }

    # 본문 텍스트 (각주 ctrl이 없는 run들의 텍스트)
    body_texts = []
    for r in runs:
        if r.get("_ctrl") is None and r.get("text"):
            body_texts.append(r["text"])
    result["text"] = "".join(body_texts)

    # 각주 내용 (subList 내부)
    sublist = fn_el.find(_hp("subList"))
    if sublist is not None:
        note_texts = []
        for p in sublist.findall(_hp("p")):
            p_runs = _extract_runs(p)
            for r in p_runs:
                text = r.get("text", "")
                if text:
                    note_texts.append(text.lstrip())
        note_key = "endnote" if is_endnote else "footnote"
        result[note_key] = "".join(note_texts)

    return result


# ── 텍스트 기반 블록 타입 감지 ────────────────────────────────────

def _detect_text_block_type(p_el, runs: list[dict], full_text: str,
                             paraPr: int, charPr: int) -> dict:
    """paraPr/charPr + 텍스트 패턴으로 블록 타입 감지."""

    styleIDRef = p_el.get("styleIDRef", "0")

    # caption (styleIDRef=22)
    if styleIDRef == "22":
        return _parse_caption(full_text)

    # pagebreak
    if p_el.get("pageBreak", "0") == "1":
        return {"type": "pagebreak"}

    # empty
    if not full_text.strip():
        result: dict[str, Any] = {"type": "empty"}
        if charPr != 0:
            result["charPr"] = charPr
        if paraPr != 0:
            result["paraPr"] = paraPr
        return result

    # ── heading 감지 ──
    heading_level = _HEADING_REVERSE.get((paraPr, charPr))
    if heading_level:
        return {"type": "heading", "level": heading_level, "text": full_text}

    # heading by charPr only (level 2: charPr=8, paraPr=0)
    if charPr == 8 and paraPr == 0:
        return {"type": "heading", "level": 2, "text": full_text}

    # ── KCUP 블록 감지 ──
    kcup_block = _detect_kcup_block(runs, full_text, paraPr, charPr)
    if kcup_block:
        return kcup_block

    # ── note (※) ──
    if full_text.strip().startswith("※"):
        text_content = full_text.strip()[1:].strip()
        result = {"type": "note", "text": text_content}
        if charPr != 11:
            result["charPr"] = charPr
        return result

    # ── bullet (• 시작) ──
    bullet_match = re.match(r'^([•●○◆◇▶▷★☆■□◎※➤➜]) (.+)', full_text)
    if bullet_match and paraPr in (24, 25):
        return {
            "type": "bullet",
            "label": bullet_match.group(1),
            "text": bullet_match.group(2),
        }

    # ── numbered (번호 패턴) ──
    numbered = _detect_numbered(full_text, paraPr)
    if numbered:
        return numbered

    # ── indent (paraPr=25, 라벨: 패턴) ──
    if paraPr == 25:
        indent_match = re.match(r'^(.+?):\s+(.+)', full_text)
        if indent_match:
            return {
                "type": "indent",
                "label": indent_match.group(1),
                "text": indent_match.group(2),
            }
        return {"type": "indent", "text": full_text}

    # ── 기본 text ──
    result = {"type": "text", "text": full_text}

    # 다중 run이면 runs 배열로 보존
    if len(runs) > 1:
        meaningful_runs = [r for r in runs if r.get("text")]
        if len(meaningful_runs) > 1:
            has_different_charPr = len(set(r["charPr"] for r in meaningful_runs)) > 1
            if has_different_charPr:
                result["runs"] = [
                    {"charPr": r["charPr"], "text": r["text"]}
                    for r in meaningful_runs
                ]
                result.pop("text", None)

    if charPr != 0:
        result["charPr"] = charPr
    if paraPr != 0:
        result["paraPr"] = paraPr

    return result


def _parse_caption(full_text: str) -> dict:
    """캡션 텍스트 파싱: "그림 1. 설명" → {"type": "caption", ...}"""
    result: dict[str, Any] = {"type": "caption"}
    m = re.match(r'^(그림|표|수식)\s+(\d+)\.\s*(.*)', full_text)
    if m:
        result["label"] = m.group(1)
        result["num"] = int(m.group(2))
        result["text"] = m.group(3)
    else:
        result["text"] = full_text
    return result


def _detect_numbered(full_text: str, paraPr: int) -> Optional[dict]:
    """번호 매기기 패턴 감지."""
    text = full_text.strip()

    # circle: ① ② ...
    for i, cn in enumerate(CIRCLE_NUMS):
        if text.startswith(cn):
            rest = text[len(cn):].strip()
            return {"type": "numbered", "num": i + 1, "style": "circle",
                    "text": rest}

    # roman: Ⅰ, Ⅱ ...
    for i, rm in enumerate(ROMAN):
        if text.startswith(f"{rm}.") or text.startswith(f"{rm} "):
            rest = text[len(rm):].lstrip(". ")
            return {"type": "numbered", "num": i + 1, "style": "roman",
                    "text": rest}

    # dot: 1. 2. ...
    dot_match = re.match(r'^(\d+)\.\s+(.+)', text)
    if dot_match and paraPr in (24, 25, 26):
        return {"type": "numbered", "num": int(dot_match.group(1)),
                "style": "dot", "text": dot_match.group(2)}

    return None


def _detect_kcup_block(runs: list[dict], full_text: str,
                        paraPr: int, charPr: int) -> Optional[dict]:
    """KCUP 전용 블록 타입 감지."""
    text = full_text.strip()

    # kcup_box: □ 로 시작, paraPr=28
    if text.startswith("□ ") and paraPr == KCUP_PP.get("box", 28):
        title = text[2:].strip()
        # 역변환: 공백 삽입된 2글자 제목 복원
        if len(title) == 3 and title[1] == " ":
            title = title[0] + title[2]
        return {"type": "kcup_box", "title": title}

    # kcup_box_spacing: 빈 텍스트, paraPr=28, charPr=19
    if not text and paraPr == KCUP_PP.get("box", 28) and charPr == KCUP_CP.get("gap14", 19):
        return {"type": "kcup_box_spacing"}

    # kcup_o_spacing: 빈 텍스트, paraPr=31, charPr=21
    if not text and paraPr == KCUP_PP.get("gap", 31) and charPr == KCUP_CP.get("gap10", 21):
        return {"type": "kcup_o_spacing"}

    # kcup_o_heading_spacing: 빈 텍스트, paraPr=31, charPr=19
    if not text and paraPr == KCUP_PP.get("gap", 31) and charPr == KCUP_CP.get("gap14", 19):
        return {"type": "kcup_o_heading_spacing"}

    # kcup_o: "o " 패턴 with 4-run (키워드)
    if paraPr == KCUP_PP.get("o", 26) and len(runs) >= 4:
        run_texts = [r.get("text", "") for r in runs]
        if len(run_texts) >= 2 and "o " in run_texts[1]:
            # 4-run: " " + "o " + "(키워드)" + " 설명"
            keyword_text = run_texts[2] if len(run_texts) > 2 else ""
            kw_match = re.match(r'^\((.+?)\)$', keyword_text)
            if kw_match:
                desc_text = run_texts[3].strip() if len(run_texts) > 3 else ""
                return {"type": "kcup_o", "keyword": kw_match.group(1),
                        "text": desc_text}

    # kcup_o_plain: "o " 패턴 with 2-run
    if paraPr == KCUP_PP.get("o", 26) and len(runs) == 2:
        run_texts = [r.get("text", "") for r in runs]
        if len(run_texts) >= 2 and run_texts[1].startswith("o "):
            desc = run_texts[1][2:].strip()
            return {"type": "kcup_o_plain", "text": desc}

    # kcup_o_heading: " o " + 소제목
    if paraPr == KCUP_PP.get("o", 26) and len(runs) == 2:
        run_texts = [r.get("text", "") for r in runs]
        run_cps = [r.get("charPr", 0) for r in runs]
        if (run_texts[0].strip() == "o" and
                run_cps[1] == KCUP_CP.get("box", 18)):
            return {"type": "kcup_o_heading", "title": run_texts[1].strip()}

    # kcup_dash: "- " 패턴 with 키워드
    if paraPr == KCUP_PP.get("dash", 30) and len(runs) >= 2:
        run_texts = [r.get("text", "") for r in runs]
        kw_match = re.match(r'^\s*-\s*\((.+?)\)$', run_texts[0]) if run_texts else None
        if kw_match:
            desc_text = run_texts[1].strip() if len(run_texts) > 1 else ""
            return {"type": "kcup_dash", "keyword": kw_match.group(1),
                    "text": desc_text}

    # kcup_dash_plain: "- " 패턴 without 키워드
    if paraPr == KCUP_PP.get("dash", 30) and len(runs) == 2:
        run_texts = [r.get("text", "") for r in runs]
        if run_texts[0].strip() == "-":
            return {"type": "kcup_dash_plain", "text": run_texts[1].strip()}

    # kcup_numbered: ① 패턴 with KCUP paraPr/charPr
    if paraPr == KCUP_PP.get("o", 26) and charPr == KCUP_CP.get("bold", 17):
        for i, cn in enumerate(CIRCLE_NUMS):
            if text.lstrip().startswith(cn):
                rest = text.lstrip()[len(cn):].strip()
                return {"type": "kcup_numbered", "num": i + 1, "text": rest}

    # kcup_note: ※ with KCUP paraPr
    if text.startswith("※") and paraPr == KCUP_PP.get("o", 26):
        note_text = text[1:].strip()
        if charPr == KCUP_CP.get("bracket", 22):
            return {"type": "kcup_note", "text": note_text, "mode": "line"}
        return {"type": "kcup_note", "text": note_text, "mode": "inline"}

    # kcup_attachment: [붙임]
    if text.startswith("[붙임]") and paraPr == KCUP_PP.get("o", 26):
        title = text[4:].strip()
        return {"type": "kcup_attachment", "title": title}

    # kcup_pointer: ☞
    if "☞" in text and paraPr == KCUP_PP.get("o", 26):
        idx = text.index("☞")
        pointer_text = text[idx + 1:].strip()
        return {"type": "kcup_pointer", "text": pointer_text}

    return None


# ── 섹션 메타데이터 추출 ──────────────────────────────────────────

def _extract_section_metadata(p_el) -> dict:
    """secPr 문단에서 용지/여백 메타데이터 추출."""
    meta: dict[str, Any] = {}

    secpr = p_el.find(f".//{_hp('secPr')}")
    if secpr is None:
        return meta

    pagePr = secpr.find(_hp("pagePr"))
    if pagePr is not None:
        meta["landscape"] = pagePr.get("landscape", "WIDELY")
        meta["page_width"] = int(pagePr.get("width", "59528"))
        meta["page_height"] = int(pagePr.get("height", "84186"))

        margin = pagePr.find(_hp("margin"))
        if margin is not None:
            meta["margin"] = {
                k: int(margin.get(k, "0"))
                for k in ("left", "right", "top", "bottom", "header", "footer", "gutter")
            }

    # colPr (다단)
    colpr = p_el.find(f".//{_hp('colPr')}")
    if colpr is not None:
        col_count = int(colpr.get("colCount", "1"))
        if col_count > 1:
            meta["columns"] = {
                "count": col_count,
                "gap": int(colpr.get("sameGap", "1134")),
                "layout": colpr.get("layout", "LEFT"),
            }

    return meta


# ── 메인 파서 ────────────────────────────────────────────────────

class HWPXReader:
    """HWPX 문서 리더."""

    def __init__(self, hwpx_path: str):
        self.path = Path(hwpx_path)
        self.style_registry: Optional[StyleRegistry] = None
        self._section_xmls: list[tuple[str, bytes]] = []
        self._header_xml: Optional[bytes] = None
        self._meta: dict[str, Any] = {}

    def load(self) -> "HWPXReader":
        """HWPX ZIP에서 필요한 파일들을 추출."""
        with zipfile.ZipFile(self.path, "r") as zf:
            names = zf.namelist()

            # header.xml
            header_candidates = [
                n for n in names
                if n.endswith("header.xml") and "Contents" in n
            ]
            if header_candidates:
                self._header_xml = zf.read(header_candidates[0])
                self.style_registry = StyleRegistry.from_xml(self._header_xml)

            # section*.xml
            section_names = sorted([
                n for n in names
                if re.search(r'section\d+\.xml$', n) and "Contents" in n
            ])
            for sn in section_names:
                self._section_xmls.append((sn, zf.read(sn)))

            # 메타데이터 (content.hpf 또는 META-INF)
            for n in names:
                if n.endswith("content.hpf"):
                    try:
                        hpf = etree.fromstring(zf.read(n))
                        title_el = hpf.find(".//{http://purl.org/dc/elements/1.1/}title")
                        if title_el is not None and title_el.text:
                            self._meta["title"] = title_el.text
                        creator_el = hpf.find(
                            ".//{http://purl.org/dc/elements/1.1/}creator")
                        if creator_el is not None and creator_el.text:
                            self._meta["creator"] = creator_el.text
                    except Exception:
                        pass

        return self

    def to_json(self, include_styles: bool = False) -> dict:
        """전체 문서를 JSON dict로 변환."""
        result: dict[str, Any] = {}

        if self._meta:
            result.update(self._meta)

        if len(self._section_xmls) == 1:
            # 단일 섹션
            sec_json = self._parse_section(self._section_xmls[0][1])
            result.update(sec_json)
        elif len(self._section_xmls) > 1:
            # 다중 섹션
            sections = []
            for name, xml_bytes in self._section_xmls:
                sec_json = self._parse_section(xml_bytes)
                sections.append(sec_json)
            result["sections"] = sections

        if include_styles and self.style_registry:
            result["_styles"] = {
                "charProperties": {
                    str(k): v for k, v in self.style_registry.char_props.items()
                },
                "paraProperties": {
                    str(k): v for k, v in self.style_registry.para_props.items()
                },
            }

        return result

    def _parse_section(self, xml_bytes: bytes) -> dict:
        """단일 section XML → JSON dict."""
        root = etree.fromstring(xml_bytes)
        result: dict[str, Any] = {}
        blocks: list[dict] = []

        paragraphs = root.findall(_hp("p"))

        header_footer_info = None

        for p_el in paragraphs:
            # secPr 문단 → 메타데이터 추출, 블록에는 포함 안 함
            if _detect_secpr(p_el):
                sec_meta = _extract_section_metadata(p_el)
                result.update(sec_meta)
                continue

            # 머리말/꼬리말 문단 감지
            hf = _detect_header_footer(p_el)
            if hf is not None:
                header_footer_info = hf
                continue

            # run 추출
            runs = _extract_runs(p_el)
            full_text = _para_full_text(runs)
            paraPr = int(p_el.get("paraPrIDRef", "0"))
            charPr = int(runs[0]["charPr"]) if runs else 0

            # 복합 블록 감지 (우선순위: table > image > textbox > field)
            table_block = _detect_table(runs)
            if table_block:
                blocks.append(table_block)
                continue

            image_block = _detect_image(runs)
            if image_block:
                blocks.append(image_block)
                continue

            textbox_block = _detect_textbox(runs)
            if textbox_block:
                blocks.append(textbox_block)
                continue

            field_block = _detect_field(runs)
            if field_block:
                blocks.append(field_block)
                continue

            # 텍스트 기반 블록 타입 감지
            block = _detect_text_block_type(p_el, runs, full_text,
                                             paraPr, charPr)
            blocks.append(block)

        result["blocks"] = blocks

        if header_footer_info:
            result.update(header_footer_info)

        return result


# ── CLI ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="HWPX → JSON 역변환기")
    parser.add_argument("input", help="HWPX 파일 경로")
    parser.add_argument("--output", "-o", help="출력 JSON 파일 경로 (기본: stdout)")
    parser.add_argument("--pretty", action="store_true",
                        help="JSON pretty-print (indent=2)")
    parser.add_argument("--include-styles", action="store_true",
                        help="charPr/paraPr 스펙을 _styles에 포함")
    args = parser.parse_args()

    if not Path(args.input).is_file():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    reader = HWPXReader(args.input)
    reader.load()
    result = reader.to_json(include_styles=args.include_styles)

    indent = 2 if args.pretty else None
    json_str = json.dumps(result, ensure_ascii=False, indent=indent)

    if args.output:
        Path(args.output).write_text(json_str, encoding="utf-8")
        print(f"Extracted to: {args.output}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
