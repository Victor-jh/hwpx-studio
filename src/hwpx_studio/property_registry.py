#!/usr/bin/env python3
"""property_registry.py — 동적 charPr/paraPr/borderFill/font 레지스트리.

HWPX header.xml에 정적으로 고정된 스타일 ID만 사용하는 기존 방식의 한계를 극복.
LLM이 JSON에서 인라인으로 지정한 서식 스펙을 동적으로 header.xml에 등록하고,
할당된 ID를 section XML에서 참조할 수 있게 하는 시스템.

사용 흐름:
    1. PropertyRegistry 인스턴스 생성 (기존 header.xml 파싱)
    2. section_builder에서 resolve_charPr / resolve_paraPr 호출
       → 기존 ID 반환 또는 새 엔트리 등록 후 ID 반환
    3. build_hwpx에서 registry.apply(header_tree) 호출
       → 동적 생성된 엔트리들을 header.xml에 삽입 + itemCnt 갱신

인라인 스펙 예시:
    {"charPr": {"bold": true, "size": 14, "color": "#FF0000"}}
    {"paraPr": {"align": "CENTER", "lineSpacing": 200, "margin": {"left": 500}}}
    {"borderFill": {"bg": "#FFFF00", "border": "SOLID"}}
"""

from __future__ import annotations

from lxml import etree

# ── 네임스페이스 ────────────────────────────────────────────────
HH = "http://www.hancom.co.kr/hwpml/2011/head"
HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HC = "http://www.hancom.co.kr/hwpml/2011/core"
HWPUNITCHAR_NS = "http://www.hancom.co.kr/hwpml/2016/HwpUnitChar"


def _hh(tag: str) -> str:
    return f"{{{HH}}}{tag}"


def _hp(tag: str) -> str:
    return f"{{{HP}}}{tag}"


def _hc(tag: str) -> str:
    return f"{{{HC}}}{tag}"


# ── 기본 템플릿 값 (base header.xml charPr id=0 기반) ────────────

_DEFAULT_CHAR_SPEC = {
    "height": 1000,        # 10pt (HWPUNIT: pt * 100)
    "textColor": "#000000",
    "shadeColor": "none",
    "useFontSpace": "0",
    "useKerning": "0",
    "symMark": "NONE",
    "borderFillIDRef": "2",
    "fontRef": 1,          # 함초롬바탕 (id=1)
    "bold": False,
    "italic": False,
    "underline": "NONE",
    "strikeout": "NONE",
    "outline": "NONE",
    "spacing": 0,          # 자간
}

_DEFAULT_PARA_SPEC = {
    "align": "JUSTIFY",
    "vertAlign": "BASELINE",
    "lineSpacing": 160,    # PERCENT
    "lineSpacingType": "PERCENT",
    "margin": {
        "intent": 0,
        "left": 0,
        "right": 0,
        "prev": 0,
        "next": 0,
    },
    "tabPrIDRef": "0",
    "borderFillIDRef": "2",
    "snapToGrid": "1",
    "breakLatinWord": "KEEP_WORD",
    "breakNonLatinWord": "BREAK_WORD",
}

_DEFAULT_BORDERFILL_SPEC = {
    "threeD": "0",
    "shadow": "0",
    "centerLine": "NONE",
    "breakCellSeparateLine": "0",
    "leftBorder": {"type": "NONE", "width": "0.1 mm", "color": "#000000"},
    "rightBorder": {"type": "NONE", "width": "0.1 mm", "color": "#000000"},
    "topBorder": {"type": "NONE", "width": "0.1 mm", "color": "#000000"},
    "bottomBorder": {"type": "NONE", "width": "0.1 mm", "color": "#000000"},
    "bg": None,            # 배경색 (None = 투명)
}


def _spec_key(spec: dict) -> str:
    """스펙 dict를 정규화한 문자열 키로 변환 (중복 방지용)."""
    import json
    return json.dumps(spec, sort_keys=True, ensure_ascii=False)


# ── borderFill 유틸 ────────────────────────────────────────────

_BORDER_TYPES = {
    "NONE", "SOLID", "DASH", "DOT", "DASH_DOT", "DASH_DOT_DOT",
    "LONG_DASH", "CIRCLE", "DOUBLE_SLIM", "SLIM_THICK",
    "THICK_SLIM", "SLIM_THICK_SLIM", "WAVE", "DOUBLE_WAVE",
    "THICK_3D", "THICK_3D_REVERSE", "3D", "3D_REVERSE",
}


class PropertyRegistry:
    """동적 charPr/paraPr/borderFill 레지스트리.

    기존 header.xml의 마지막 ID를 추적하면서,
    새로운 스펙이 요청될 때 다음 ID를 할당하고 XML 엔트리를 생성.
    """

    def __init__(self, header_path: str | None = None):
        """기존 header.xml을 파싱하여 현재 ID 상태를 로드.

        header_path가 None이면 기본값 (base template 기준) 사용.
        """
        self._charpr_next_id: int = 0
        self._parapr_next_id: int = 0
        self._borderfill_next_id: int = 0
        self._font_next_id: dict[str, int] = {}  # lang → next_id

        # 동적으로 생성된 엔트리들
        self._new_charprs: list[tuple[int, dict]] = []   # (id, spec)
        self._new_paraprs: list[tuple[int, dict]] = []   # (id, spec)
        self._new_borderfills: list[tuple[int, dict]] = []  # (id, spec)
        self._new_fonts: list[tuple[str, int, str]] = []  # (lang, id, face)

        # 스펙 → ID 캐시 (동일 스펙 중복 방지)
        self._charpr_cache: dict[str, int] = {}
        self._parapr_cache: dict[str, int] = {}
        self._borderfill_cache: dict[str, int] = {}

        if header_path:
            self._load_header(header_path)

    def _load_header(self, path: str) -> None:
        """기존 header.xml에서 현재 최대 ID를 파악."""
        tree = etree.parse(path)
        root = tree.getroot()

        # charProperties
        char_props = root.find(f".//{_hh('charProperties')}")
        if char_props is not None:
            max_id = -1
            for cp in char_props.findall(_hh("charPr")):
                cid = int(cp.get("id", "0"))
                if cid > max_id:
                    max_id = cid
            self._charpr_next_id = max_id + 1

        # paraProperties
        para_props = root.find(f".//{_hh('paraProperties')}")
        if para_props is not None:
            max_id = -1
            for pp in para_props.findall(_hh("paraPr")):
                pid = int(pp.get("id", "0"))
                if pid > max_id:
                    max_id = pid
            self._parapr_next_id = max_id + 1

        # borderFills
        border_fills = root.find(f".//{_hh('borderFills')}")
        if border_fills is not None:
            max_id = -1
            for bf in border_fills.findall(_hh("borderFill")):
                bid = int(bf.get("id", "0"))
                if bid > max_id:
                    max_id = bid
            self._borderfill_next_id = max_id + 1

        # fontfaces (각 lang별 최대 ID)
        fontfaces = root.find(f".//{_hh('fontfaces')}")
        if fontfaces is not None:
            for ff in fontfaces.findall(_hh("fontface")):
                lang = ff.get("lang", "")
                max_id = -1
                for font in ff.findall(_hh("font")):
                    fid = int(font.get("id", "0"))
                    if fid > max_id:
                        max_id = fid
                self._font_next_id[lang] = max_id + 1

    # ── charPr 등록 ──────────────────────────────────────────────

    def resolve_charPr(self, spec: dict | int) -> int:
        """charPr 스펙을 받아 ID를 반환.

        - int: 기존 ID 그대로 반환
        - dict: 캐시 확인 → 없으면 새 ID 할당

        지원 스펙 키:
            size: float (pt) → height = size * 100
            bold: bool
            italic: bool
            color: str (#RRGGBB)
            fontRef: int (폰트 ID)
            spacing: int (자간, HWPUNIT)
            underline: str (NONE/BOTTOM/...)
            strikeout: str (NONE/...)
            shadeColor: str
            borderFillIDRef: int
        """
        if isinstance(spec, int):
            return spec

        # 정규화
        normalized = dict(_DEFAULT_CHAR_SPEC)
        if "size" in spec:
            normalized["height"] = int(spec["size"] * 100)
        if "bold" in spec:
            normalized["bold"] = spec["bold"]
        if "italic" in spec:
            normalized["italic"] = spec["italic"]
        if "color" in spec:
            normalized["textColor"] = spec["color"]
        if "fontRef" in spec:
            normalized["fontRef"] = spec["fontRef"]
        if "spacing" in spec:
            normalized["spacing"] = spec["spacing"]
        if "underline" in spec:
            normalized["underline"] = spec["underline"]
        if "strikeout" in spec:
            normalized["strikeout"] = spec["strikeout"]
        if "shadeColor" in spec:
            normalized["shadeColor"] = spec["shadeColor"]
        if "borderFillIDRef" in spec:
            normalized["borderFillIDRef"] = str(spec["borderFillIDRef"])
        if "height" in spec:
            normalized["height"] = spec["height"]

        key = _spec_key(normalized)
        if key in self._charpr_cache:
            return self._charpr_cache[key]

        new_id = self._charpr_next_id
        self._charpr_next_id += 1
        self._charpr_cache[key] = new_id
        self._new_charprs.append((new_id, normalized))
        return new_id

    # ── paraPr 등록 ──────────────────────────────────────────────

    def resolve_paraPr(self, spec: dict | int) -> int:
        """paraPr 스펙을 받아 ID를 반환.

        지원 스펙 키:
            align: str (JUSTIFY/LEFT/CENTER/RIGHT)
            lineSpacing: int (PERCENT 값)
            lineSpacingType: str (PERCENT/FIXED/...)
            margin: dict {intent, left, right, prev, next} (HWPUNIT)
            tabPrIDRef: int
            borderFillIDRef: int
            snapToGrid: str
            indent: int → margin.intent 단축키
            left: int → margin.left 단축키
        """
        if isinstance(spec, int):
            return spec

        normalized = {}
        for k, v in _DEFAULT_PARA_SPEC.items():
            if isinstance(v, dict):
                normalized[k] = dict(v)
            else:
                normalized[k] = v

        if "align" in spec:
            normalized["align"] = spec["align"]
        if "lineSpacing" in spec:
            normalized["lineSpacing"] = spec["lineSpacing"]
        if "lineSpacingType" in spec:
            normalized["lineSpacingType"] = spec["lineSpacingType"]
        if "tabPrIDRef" in spec:
            normalized["tabPrIDRef"] = str(spec["tabPrIDRef"])
        if "borderFillIDRef" in spec:
            normalized["borderFillIDRef"] = str(spec["borderFillIDRef"])
        # borderFill dict → resolve_borderFill → ID 자동 할당
        if "borderFill" in spec and isinstance(spec["borderFill"], dict):
            bf_id = self.resolve_borderFill(spec["borderFill"])
            normalized["borderFillIDRef"] = str(bf_id)
        if "snapToGrid" in spec:
            normalized["snapToGrid"] = str(spec["snapToGrid"])
        if "breakLatinWord" in spec:
            normalized["breakLatinWord"] = spec["breakLatinWord"]
        if "breakNonLatinWord" in spec:
            normalized["breakNonLatinWord"] = spec["breakNonLatinWord"]

        # margin 병합
        if "margin" in spec:
            for mk in ("intent", "left", "right", "prev", "next"):
                if mk in spec["margin"]:
                    normalized["margin"][mk] = spec["margin"][mk]
        # 단축키
        if "indent" in spec:
            normalized["margin"]["intent"] = spec["indent"]
        if "left" in spec:
            normalized["margin"]["left"] = spec["left"]
        if "right" in spec:
            normalized["margin"]["right"] = spec["right"]
        if "prev" in spec:
            normalized["margin"]["prev"] = spec["prev"]
        if "next" in spec:
            normalized["margin"]["next"] = spec["next"]

        key = _spec_key(normalized)
        if key in self._parapr_cache:
            return self._parapr_cache[key]

        new_id = self._parapr_next_id
        self._parapr_next_id += 1
        self._parapr_cache[key] = new_id
        self._new_paraprs.append((new_id, normalized))
        return new_id

    # ── borderFill 등록 ──────────────────────────────────────────

    def resolve_borderFill(self, spec: dict | int) -> int:
        """borderFill 스펙을 받아 ID를 반환.

        지원 스펙 키:
            bg: str (#RRGGBB 배경색)
            border: str (SOLID/NONE 등 — 4변 동일 적용)
            borderWidth: str ("0.1 mm" 등)
            borderColor: str (#RRGGBB)
            leftBorder/rightBorder/topBorder/bottomBorder: dict (개별 지정)
        """
        if isinstance(spec, int):
            return spec

        normalized = {}
        for k, v in _DEFAULT_BORDERFILL_SPEC.items():
            if isinstance(v, dict):
                normalized[k] = dict(v)
            else:
                normalized[k] = v

        # 4변 동일 border 적용
        if "border" in spec:
            btype = spec["border"]
            bwidth = spec.get("borderWidth", "0.1 mm")
            bcolor = spec.get("borderColor", "#000000")
            for side in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"):
                normalized[side] = {"type": btype, "width": bwidth, "color": bcolor}

        # 개별 border 오버라이드
        for side in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"):
            if side in spec:
                normalized[side] = dict(spec[side])

        if "bg" in spec:
            normalized["bg"] = spec["bg"]

        key = _spec_key(normalized)
        if key in self._borderfill_cache:
            return self._borderfill_cache[key]

        new_id = self._borderfill_next_id
        self._borderfill_next_id += 1
        self._borderfill_cache[key] = new_id
        self._new_borderfills.append((new_id, normalized))
        return new_id

    # ── font 등록 ────────────────────────────────────────────────

    def resolve_font(self, face: str, target_langs: list[str] | None = None) -> int:
        """폰트 이름을 받아 모든 lang에 등록하고 할당된 font ID를 반환.

        target_langs: 등록 대상 언어 목록. None이면 7개 전체.
        반환값은 HANGUL lang 기준 ID.
        """
        all_langs = ["HANGUL", "LATIN", "HANJA", "JAPANESE",
                     "OTHER", "SYMBOL", "USER"]
        langs = target_langs or all_langs

        font_id = None
        for lang in langs:
            next_id = self._font_next_id.get(lang, 0)
            if lang == "HANGUL" or font_id is None:
                font_id = next_id
            self._new_fonts.append((lang, next_id, face))
            self._font_next_id[lang] = next_id + 1

        return font_id

    # ── header.xml에 적용 ────────────────────────────────────────

    def has_changes(self) -> bool:
        """동적으로 추가된 엔트리가 있는지 확인."""
        return bool(self._new_charprs or self._new_paraprs or
                     self._new_borderfills or self._new_fonts)

    def apply(self, header_path: str) -> None:
        """동적 엔트리들을 header.xml에 삽입하고 itemCnt 갱신."""
        if not self.has_changes():
            return

        tree = etree.parse(header_path)
        root = tree.getroot()

        # ── borderFills 삽입 ──
        if self._new_borderfills:
            bf_container = root.find(f".//{_hh('borderFills')}")
            if bf_container is not None:
                for bf_id, spec in self._new_borderfills:
                    bf_el = self._build_borderfill_element(bf_id, spec)
                    bf_container.append(bf_el)
                bf_container.set("itemCnt",
                                  str(len(bf_container.findall(_hh("borderFill")))))

        # ── charProperties 삽입 ──
        if self._new_charprs:
            cp_container = root.find(f".//{_hh('charProperties')}")
            if cp_container is not None:
                for cp_id, spec in self._new_charprs:
                    cp_el = self._build_charpr_element(cp_id, spec)
                    cp_container.append(cp_el)
                cp_container.set("itemCnt",
                                  str(len(cp_container.findall(_hh("charPr")))))

        # ── paraProperties 삽입 ──
        if self._new_paraprs:
            pp_container = root.find(f".//{_hh('paraProperties')}")
            if pp_container is not None:
                for pp_id, spec in self._new_paraprs:
                    pp_el = self._build_parapr_element(pp_id, spec)
                    pp_container.append(pp_el)
                pp_container.set("itemCnt",
                                  str(len(pp_container.findall(_hh("paraPr")))))

        # ── fontfaces 삽입 ──
        if self._new_fonts:
            fontfaces = root.find(f".//{_hh('fontfaces')}")
            if fontfaces is not None:
                for lang, font_id, face in self._new_fonts:
                    ff = fontfaces.find(
                        f"{_hh('fontface')}[@lang='{lang}']")
                    if ff is not None:
                        font_el = etree.SubElement(ff, _hh("font"))
                        font_el.set("id", str(font_id))
                        font_el.set("face", face)
                        font_el.set("type", "TTF")
                        font_el.set("isEmbedded", "0")
                        typeinfo = etree.SubElement(font_el, _hh("typeInfo"))
                        typeinfo.set("familyType", "FCAT_GOTHIC")
                        typeinfo.set("weight", "6")
                        typeinfo.set("proportion", "4")
                        for attr in ("contrast", "strokeVariation", "armStyle",
                                     "letterform", "midline", "xHeight"):
                            typeinfo.set(attr, "1" if attr != "contrast" else "0")
                        # fontCnt 갱신
                        ff.set("fontCnt",
                               str(len(ff.findall(_hh("font")))))

        # 파일 저장
        etree.indent(root, space="  ")
        tree.write(header_path, pretty_print=True,
                   xml_declaration=True, encoding="UTF-8")

    # ── XML 엘리먼트 빌더들 (private) ────────────────────────────

    def _build_charpr_element(self, cp_id: int, spec: dict) -> etree._Element:
        """charPr XML 엘리먼트 생성."""
        el = etree.Element(_hh("charPr"))
        el.set("id", str(cp_id))
        el.set("height", str(spec.get("height", 1000)))
        el.set("textColor", spec.get("textColor", "#000000"))
        el.set("shadeColor", spec.get("shadeColor", "none"))
        el.set("useFontSpace", str(spec.get("useFontSpace", "0")))
        el.set("useKerning", str(spec.get("useKerning", "0")))
        el.set("symMark", spec.get("symMark", "NONE"))
        el.set("borderFillIDRef", str(spec.get("borderFillIDRef", "2")))

        # fontRef — 모든 lang 동일 값
        font_ref = str(spec.get("fontRef", 1))
        fr = etree.SubElement(el, _hh("fontRef"))
        for lang in ("hangul", "latin", "hanja", "japanese",
                      "other", "symbol", "user"):
            fr.set(lang, font_ref)

        # ratio — 100%
        ratio = etree.SubElement(el, _hh("ratio"))
        for lang in ("hangul", "latin", "hanja", "japanese",
                      "other", "symbol", "user"):
            ratio.set(lang, "100")

        # spacing
        spacing_val = str(spec.get("spacing", 0))
        sp = etree.SubElement(el, _hh("spacing"))
        for lang in ("hangul", "latin", "hanja", "japanese",
                      "other", "symbol", "user"):
            sp.set(lang, spacing_val)

        # relSz — 100%
        rsz = etree.SubElement(el, _hh("relSz"))
        for lang in ("hangul", "latin", "hanja", "japanese",
                      "other", "symbol", "user"):
            rsz.set(lang, "100")

        # offset — 0
        off = etree.SubElement(el, _hh("offset"))
        for lang in ("hangul", "latin", "hanja", "japanese",
                      "other", "symbol", "user"):
            off.set(lang, "0")

        # bold/italic — OWPML에서는 자식 요소 (<hh:bold/>, <hh:italic/>)
        if spec.get("bold", False):
            etree.SubElement(el, _hh("bold"))
        if spec.get("italic", False):
            etree.SubElement(el, _hh("italic"))

        # underline
        ul = etree.SubElement(el, _hh("underline"))
        ul_type = spec.get("underline", "NONE")
        ul.set("type", ul_type)
        ul.set("shape", "SOLID")
        ul.set("color", "#000000")

        # strikeout
        so = etree.SubElement(el, _hh("strikeout"))
        so.set("shape", spec.get("strikeout", "NONE"))
        so.set("color", "#000000")

        # outline
        ol = etree.SubElement(el, _hh("outline"))
        ol.set("type", spec.get("outline", "NONE"))

        # shadow
        sh = etree.SubElement(el, _hh("shadow"))
        sh.set("type", "NONE")
        sh.set("color", "#C0C0C0")
        sh.set("offsetX", "10")
        sh.set("offsetY", "10")

        return el

    def _build_parapr_element(self, pp_id: int, spec: dict) -> etree._Element:
        """paraPr XML 엘리먼트 생성 (hp:switch/case/default 패턴 포함)."""
        el = etree.Element(_hh("paraPr"))
        el.set("id", str(pp_id))
        el.set("tabPrIDRef", str(spec.get("tabPrIDRef", "0")))
        el.set("condense", "0")
        el.set("fontLineHeight", "0")
        el.set("snapToGrid", str(spec.get("snapToGrid", "1")))
        el.set("suppressLineNumbers", "0")
        el.set("checked", "0")
        el.set("textDir", "LTR")

        # align
        align_el = etree.SubElement(el, _hh("align"))
        align_el.set("horizontal", spec.get("align", "JUSTIFY"))
        align_el.set("vertical", spec.get("vertAlign", "BASELINE"))

        # heading
        heading = etree.SubElement(el, _hh("heading"))
        heading.set("type", "NONE")
        heading.set("idRef", "0")
        heading.set("level", "0")

        # breakSetting
        brk = etree.SubElement(el, _hh("breakSetting"))
        brk.set("breakLatinWord", spec.get("breakLatinWord", "KEEP_WORD"))
        brk.set("breakNonLatinWord", spec.get("breakNonLatinWord", "BREAK_WORD"))
        brk.set("widowOrphan", "0")
        brk.set("keepWithNext", "0")
        brk.set("keepLines", "0")
        brk.set("pageBreakBefore", "0")
        brk.set("lineWrap", "BREAK")

        # autoSpacing
        auto = etree.SubElement(el, _hh("autoSpacing"))
        auto.set("eAsianEng", "0")
        auto.set("eAsianNum", "0")

        # ── hp:switch/case/default 패턴 (한컴 호환) ──
        margin = spec.get("margin", {})
        ls_val = str(spec.get("lineSpacing", 160))
        ls_type = spec.get("lineSpacingType", "PERCENT")

        switch = etree.SubElement(el, _hp("switch"))

        # case: HwpUnitChar namespace (값 그대로)
        case = etree.SubElement(switch, _hp("case"))
        case.set(f"{{{HP}}}required-namespace", HWPUNITCHAR_NS)
        self._add_margin_and_linespacing(case, margin, ls_val, ls_type)

        # default: 값 2배 (HwpUnitChar 미지원 클라이언트용 폴백)
        default = etree.SubElement(switch, _hp("default"))
        margin_doubled = {}
        for mk in ("intent", "left", "right", "prev", "next"):
            v = margin.get(mk, 0)
            margin_doubled[mk] = v * 2 if mk not in ("prev", "next") else v * 2
        self._add_margin_and_linespacing(default, margin_doubled, ls_val, ls_type)

        # border
        border = etree.SubElement(el, _hh("border"))
        border.set("borderFillIDRef", str(spec.get("borderFillIDRef", "2")))
        for attr in ("offsetLeft", "offsetRight", "offsetTop", "offsetBottom"):
            border.set(attr, "0")
        border.set("connect", "0")
        border.set("ignoreMargin", "0")

        return el

    def _add_margin_and_linespacing(
        self,
        parent: etree._Element,
        margin: dict,
        ls_val: str,
        ls_type: str,
    ) -> None:
        """margin + lineSpacing 엘리먼트를 parent(case/default)에 추가."""
        m = etree.SubElement(parent, _hh("margin"))
        for mk in ("intent", "left", "right", "prev", "next"):
            child = etree.SubElement(m, _hc(mk))
            child.set("value", str(margin.get(mk, 0)))
            child.set("unit", "HWPUNIT")

        ls = etree.SubElement(parent, _hh("lineSpacing"))
        ls.set("type", ls_type)
        ls.set("value", ls_val)
        ls.set("unit", "HWPUNIT")

    def _build_borderfill_element(self, bf_id: int, spec: dict) -> etree._Element:
        """borderFill XML 엘리먼트 생성."""
        el = etree.Element(_hh("borderFill"))
        el.set("id", str(bf_id))
        el.set("threeD", spec.get("threeD", "0"))
        el.set("shadow", spec.get("shadow", "0"))
        el.set("centerLine", spec.get("centerLine", "NONE"))
        el.set("breakCellSeparateLine", spec.get("breakCellSeparateLine", "0"))

        # slash / backSlash
        for tag in ("slash", "backSlash"):
            s = etree.SubElement(el, _hh(tag))
            s.set("type", "NONE")
            s.set("Crooked", "0")
            s.set("isCounter", "0")

        # borders
        for side in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"):
            b_spec = spec.get(side, {})
            b = etree.SubElement(el, _hh(side))
            b.set("type", b_spec.get("type", "NONE"))
            b.set("width", b_spec.get("width", "0.1 mm"))
            b.set("color", b_spec.get("color", "#000000"))

        # diagonal
        diag = etree.SubElement(el, _hh("diagonal"))
        diag.set("type", "SOLID")
        diag.set("width", "0.1 mm")
        diag.set("color", "#000000")

        # fillBrush (배경색이 있으면)
        bg = spec.get("bg")
        if bg:
            fb = etree.SubElement(el, _hc("fillBrush"))
            wb = etree.SubElement(fb, _hc("winBrush"))
            wb.set("faceColor", bg)
            wb.set("hatchColor", "#999999")
            wb.set("alpha", "0")

        return el

    # ── 직렬화/역직렬화 (subprocess 파이프라인용) ────────────────

    def export_json(self) -> dict:
        """동적으로 생성된 엔트리들을 JSON 직렬화 가능한 dict로 내보내기."""
        return {
            "new_charprs": [(cid, spec) for cid, spec in self._new_charprs],
            "new_paraprs": [(pid, spec) for pid, spec in self._new_paraprs],
            "new_borderfills": [(bid, spec) for bid, spec in self._new_borderfills],
            "new_fonts": [(lang, fid, face) for lang, fid, face in self._new_fonts],
        }

    def save(self, path: str) -> None:
        """동적 엔트리를 JSON 파일로 저장."""
        import json
        data = self.export_json()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "PropertyRegistry":
        """JSON 파일에서 동적 엔트리를 로드하여 새 인스턴스 생성."""
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        reg = cls()
        reg._new_charprs = [(e[0], e[1]) for e in data.get("new_charprs", [])]
        reg._new_paraprs = [(e[0], e[1]) for e in data.get("new_paraprs", [])]
        reg._new_borderfills = [(e[0], e[1]) for e in data.get("new_borderfills", [])]
        reg._new_fonts = [(e[0], e[1], e[2]) for e in data.get("new_fonts", [])]
        return reg

    # ── 유틸리티 ─────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """디버깅/로깅용 통계 반환."""
        return {
            "new_charPr": len(self._new_charprs),
            "new_paraPr": len(self._new_paraprs),
            "new_borderFill": len(self._new_borderfills),
            "new_fonts": len(self._new_fonts),
            "next_charPr_id": self._charpr_next_id,
            "next_paraPr_id": self._parapr_next_id,
            "next_borderFill_id": self._borderfill_next_id,
        }
