---
name: hwpx
description: "한글(HWPX) 문서 생성·읽기·편집 스킬. .hwpx 파일 생성, 분석, 수정, 텍스트 추출, 공문서·보고서 자동 작성 요청 시 사용. Hancom/OWPML/한컴 관련 작업 포함."
---

# HWPX 문서 스킬 — 생성 · 읽기 · 편집 (XML-first)

한글(Hancom Office)의 HWPX 파일을 **XML 직접 작성** 중심으로 생성, 읽기, 편집.
HWPX = ZIP 기반 XML 컨테이너(OWPML 표준). lxml + zipfile 직접 조작.

### 핵심 기능
1. **생성** — JSON 블록 정의 → HWPX 자동 생성 (35개 블록 타입, 6개 템플릿)
2. **읽기** — HWPX → JSON 역변환 (블록 타입 자동 감지, 스타일 추출)
3. **편집** — 기존 HWPX 텍스트 교체, 블록 삽입/삭제, 머리말·꼬리말 변경

---

## 워크플로우 선택 (최우선)

```python
if 사용자가_hwpx_첨부:
    if 의도 == "읽기":   → read_document.py  (또는 text_extract.py)
    elif 의도 == "편집": → edit_document.py  (불가 시 unpack→edit→pack)
    elif 의도 == "생성": → analyze_template.py → build_hwpx.py + page_guard.py
    elif 의도 == "검증": → validate.py 단독
    else:               → read_document.py  (기본: 분석 우선)
else:
    → create_document.py (새 문서)
```

### 편집 vs 생성

| 편집 (edit_document.py) | 생성 (레퍼런스 모드) |
|------------------------|----------------------|
| 텍스트 찾아바꾸기 | 내용 완전 재작성 |
| 특정 블록 삭제/수정 | 같은 양식, 다른 데이터 |
| 머리말·꼬리말 변경 | 블록 5개+ 대량 추가 |

---

## 레퍼런스 기반 생성 (HWPX 첨부 시 기본)

**흐름**: `analyze_template.py` → header/section 추출 → 새 section0.xml 작성 → `build_hwpx.py` → `validate.py` → `page_guard.py`

**99% 복원 기준**: charPrIDRef/paraPrIDRef 체계 동일, 표 구조(colCnt/rowCnt/span/cellSz/cellMargin) 동일, 문단 순서·수·여백 동일, secPr 동일

**쪽수 100% 필수**: 레퍼런스와 결과 쪽수 반드시 일치. page_guard.py 실패 시 재수정 후 재빌드.

```bash
source "$VENV"
python3 "$SKILL_DIR/src/hwpx_studio/analyze_template.py" ref.hwpx \
  --extract-header /tmp/ref_header.xml --extract-section /tmp/ref_section.xml
# → 새 section0.xml 작성 →
python3 "$SKILL_DIR/src/hwpx_studio/build_hwpx.py" \
  --header /tmp/ref_header.xml --section new_section.xml --output result.hwpx
python3 "$SKILL_DIR/src/hwpx_studio/validate.py" result.hwpx
python3 "$SKILL_DIR/src/hwpx_studio/page_guard.py" --reference ref.hwpx --output result.hwpx
```

---

## JSON→HWPX 파이프라인 (create_document.py)

```bash
source "$VENV"
python3 "$SKILL_DIR/src/hwpx_studio/create_document.py" input.json -o result.hwpx
python3 "$SKILL_DIR/src/hwpx_studio/create_document.py" input.json --style kcup -o result.hwpx
python3 "$SKILL_DIR/src/hwpx_studio/create_document.py" input.json --template gonmun -o result.hwpx
```

### 스타일↔템플릿 매핑

| --style | 템플릿 | 본문폭 |
|---------|--------|--------|
| kcup | kcup | 48190 (170mm, 20mm 여백) |
| gonmun | gonmun | 42520 (150mm, 30mm 여백) |
| report | report | 42520 |
| minutes | minutes | 42520 |
| proposal | proposal | 42520 |
| (미지정) | base | 42520 |

### JSON 기본 구조

```json
{
  "template": "report",
  "auto_spacing": true,
  "header": {"text": "- {{page}} -", "align": "center"},
  "footer": {"text": "{{page}} / {{total_pages}}", "align": "right"},
  "blocks": [
    {"type": "heading", "text": "제목", "level": 1},
    {"type": "text", "text": "본문"},
    {"type": "kcup_box", "text": "□ 항목"},
    {"type": "kcup_o", "keyword": "키워드", "text": "내용"},
    {"type": "table", "rows": [["A","B"],["C","D"]]}
  ]
}
```

### 블록 타입 목록

**기본 19개**: text, empty, heading, bullet, numbered, indent, note, table, image, label_value, signature, pagebreak, hyperlink, text_footnote, text_endnote, textbox, caption, bookmark, field

**KCUP 전용 16개**: kcup_box, kcup_o, kcup_o_plain, kcup_o_heading, kcup_dash, kcup_dash_plain, kcup_numbered, kcup_note, kcup_attachment, kcup_pointer, kcup_mixed_run, kcup_box_spacing, kcup_o_spacing, kcup_o_heading_spacing, kcup_dash_spacing

→ 상세 스펙: `references/block-types.md`

### 동적 서식 (PropertyRegistry)

charPr/paraPr를 정수 ID 대신 dict로 지정하면 자동 등록:

```json
{"type": "text", "text": "예시",
 "charPr": {"bold": true, "size": 14, "color": "#FF0000"},
 "paraPr": {"align": "CENTER", "lineSpacing": 200}}
```

- `charPr` dict 키: `size`(pt), `bold`, `italic`, `color`(#RRGGBB), `fontRef`, `spacing`, `underline`, `strikeout`, `shadeColor`
- `paraPr` dict 키: `align`(JUSTIFY/LEFT/CENTER/RIGHT), `lineSpacing`, `left`, `right`, `prev`, `next`, `indent`, `borderFill`
- HEADING_DEFAULTS / NUMBERED_DEFAULTS도 dict 기반 → registry 자동 할당

---

## 읽기 (read_document.py)

```bash
python3 "$SKILL_DIR/src/hwpx_studio/read_document.py" doc.hwpx --pretty -o out.json
python3 "$SKILL_DIR/src/hwpx_studio/read_document.py" doc.hwpx --pretty --include-styles -o out.json
python3 "$SKILL_DIR/src/hwpx_studio/text_extract.py" doc.hwpx --format markdown
```

---

## 편집 (edit_document.py)

```bash
python3 "$SKILL_DIR/src/hwpx_studio/edit_document.py" doc.hwpx \
  --replace "원본" "새것" -o edited.hwpx
python3 "$SKILL_DIR/src/hwpx_studio/edit_document.py" doc.hwpx \
  --edit-json ops.json -o edited.hwpx
```

→ 편집 작업 JSON 상세: `references/edit-commands.md`

---

## 수동 XML 편집 (edit_document.py 불가 시)

```bash
python3 "$SKILL_DIR/src/hwpx_studio/office/unpack.py" doc.hwpx ./unpacked/
# Read/Edit 도구로 ./unpacked/Contents/section0.xml 수정
python3 "$SKILL_DIR/src/hwpx_studio/office/pack.py" ./unpacked/ edited.hwpx
python3 "$SKILL_DIR/src/hwpx_studio/validate.py" edited.hwpx
```

---

## 검증

```bash
python3 "$SKILL_DIR/src/hwpx_studio/validate.py" doc.hwpx
python3 "$SKILL_DIR/src/hwpx_studio/page_guard.py" --reference ref.hwpx --output result.hwpx
```

---

## 스크립트 요약

| 스크립트 | 용도 |
|----------|------|
| create_document.py | JSON → HWPX 원커맨드 파이프라인 |
| read_document.py | HWPX → JSON 역변환 (35개 블록 타입) |
| edit_document.py | HWPX 인플레이스 편집 |
| section_builder.py | JSON → section0.xml (35개 블록 타입) |
| build_hwpx.py | 템플릿 + XML → HWPX 조립 |
| analyze_template.py | HWPX 심층 분석 (레퍼런스 기반 청사진) |
| office/unpack.py | HWPX → 디렉토리 (XML pretty-print) |
| office/pack.py | 디렉토리 → HWPX (mimetype first) |
| property_registry.py | 동적 charPr/paraPr/borderFill ID 할당 |
| validate.py | HWPX 구조 검증 |
| page_guard.py | 레퍼런스 대비 페이지 드리프트 검사 |
| text_extract.py | 텍스트 추출 |
| diff_docs.py | 텍스트 diff + 구조 비교 |

---

## 단위 변환

| 값 | HWPUNIT |
|----|---------|
| 1pt | 100 |
| 1mm | 283.5 |
| A4 폭 | 59528 |
| A4 높이 | 84186 |
| 본문폭(기본) | 42520 |
| 본문폭(kcup) | 48190 |

---

## 환경

```bash
SKILL_DIR="<이 SKILL.md가 위치한 디렉토리의 상위>"
source "$SKILL_DIR/.venv/bin/activate"   # lxml 필요
```

---

## Critical Rules

1. `.hwpx`만 지원 — `.hwp` 바이너리 불가. 사용자가 제공하면 "다른 이름으로 저장 → HWPX"로 안내
2. **secPr 필수** — section0.xml 첫 문단 첫 run에 secPr + colPr 포함
3. **mimetype 순서** — ZIP 첫 번째 엔트리, ZIP_STORED
4. **네임스페이스 보존** — `hp:`, `hs:`, `hh:`, `hc:` 접두사 유지
5. **itemCnt 정합성** — header.xml의 charProperties/paraProperties/borderFills itemCnt = 실제 자식 수
6. **ID 참조 정합성** — section0.xml charPrIDRef/paraPrIDRef가 header.xml 정의와 일치
7. **venv 사용** — 프로젝트 `.venv/bin/python3` (lxml 필요)
8. **validate 필수** — 생성/편집 후 반드시 validate.py 통과
9. **레퍼런스 우선** — HWPX 첨부 시 반드시 analyze_template.py 기반 복원/재작성
10. **쪽수 동일 필수** — 레퍼런스 작업 결과 쪽수 = 레퍼런스 쪽수. page_guard.py 필수 통과
11. **무단 페이지 증가 금지** — 사용자 명시 없이 쪽수 증가 유발 구조 변경 금지
12. **구조 변경 제한** — 요청 없는 문단/표 추가·삭제·분할 금지 (치환 중심)
13. **빈 줄** — `<hp:t/>` 사용 (self-closing tag)
14. **build_hwpx.py 우선** — 새 문서는 build_hwpx.py 사용

---

## 참조 파일 인덱스

| 파일 | 내용 |
|------|------|
| `references/block-types.md` | 35개 블록 타입 상세 스펙 |
| `references/xml-structure.md` | section0.xml 구조, OWPML 태그 |
| `references/style-guide.md` | HEADING_DEFAULTS/NUMBERED_DEFAULTS, charPr/paraPr dict 속성, 6개 템플릿 스타일 맵 |
| `references/edit-commands.md` | 편집 작업 JSON 상세 |
| `references/hwpx-format.md` | OWPML XML 요소 레퍼런스 |
