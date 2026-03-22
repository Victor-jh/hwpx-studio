---
name: hwpx
description: "한글(HWPX) 문서 생성/읽기/편집/분석 스킬. .hwpx 파일, 한글 문서, Hancom, OWPML, 한컴, 한글 문서 읽기, 문서 수정, 텍스트 교체, 블록 삽입/삭제, 머리말 꼬리말 변경 관련 요청 시 사용."
---

# HWPX 문서 스킬 — 생성 · 읽기 · 편집 (XML-first)

한글(Hancom Office)의 HWPX 파일을 **XML 직접 작성** 중심으로 생성, 읽기, 편집할 수 있는 스킬.
HWPX는 ZIP 기반 XML 컨테이너(OWPML 표준)이다. python-hwpx API의 서식 버그를 완전히 우회하며, 세밀한 서식 제어가 가능하다.

### 핵심 기능 3가지
1. **생성** — JSON 블록 정의 → HWPX 문서 자동 생성 (35개 블록 타입, 6개 템플릿)
2. **읽기** — HWPX → JSON 역변환 (블록 타입 자동 감지, 머리말/꼬리말, 스타일 추출)
3. **편집** — 기존 HWPX의 텍스트 교체, 블록 삽입/삭제/수정, 머리말·꼬리말 변경 (서식 보존)

## 기본 동작 모드 (필수): 첨부 HWPX 분석 → 고유 XML 복원(99% 근접) → 요청 반영 재작성

사용자가 `.hwpx`를 첨부한 경우, 이 스킬은 아래 순서를 **기본값**으로 따른다.

1. **레퍼런스 확보**: 첨부된 HWPX를 기준 문서로 사용
2. **심층 분석/추출**: `analyze_template.py`로 `header.xml`, `section0.xml` 추출
3. **구조 복원**: header 스타일 ID/표 구조/셀 병합/여백/문단 흐름을 최대한 동일하게 유지
4. **요청 반영 재작성**: 사용자가 요구한 텍스트/데이터만 교체하고 구조는 보존
5. **빌드/검증**: `build_hwpx.py` + `validate.py`로 결과 산출 및 무결성 확인
6. **쪽수 가드(필수)**: `page_guard.py`로 레퍼런스 대비 페이지 드리프트 위험 검사

### 99% 근접 복원 기준 (실무 체크리스트)

- `charPrIDRef`, `paraPrIDRef`, `borderFillIDRef` 참조 체계 동일
- 표의 `rowCnt`, `colCnt`, `colSpan`, `rowSpan`, `cellSz`, `cellMargin` 동일
- 문단 순서, 문단 수, 주요 빈 줄/구획 위치 동일
- 페이지/여백/섹션(secPr) 동일
- 변경은 사용자 요청 범위(본문 텍스트, 값, 항목명 등)로 제한

### 쪽수 동일(100%) 필수 기준

- 사용자가 레퍼런스를 제공한 경우 **결과 문서의 최종 쪽수는 레퍼런스와 동일해야 한다**
- 쪽수가 늘어날 가능성이 보이면 먼저 텍스트를 압축/요약해서 기존 레이아웃에 맞춘다
- 사용자 명시 요청 없이 `hp:p`, `hp:tbl`, `rowCnt`, `colCnt`, `pageBreak`, `secPr`를 변경하지 않는다
- `validate.py` 통과만으로 완료 처리하지 않는다. 반드시 `page_guard.py`도 통과해야 한다
- `page_guard.py` 실패 시 결과를 완료로 제출하지 않고, 원인(길이 과다/구조 변경)을 수정 후 재빌드한다
- 가능하면 한글(또는 사용자의 확인) 기준 최종 쪽수 값을 확인하고 레퍼런스와 일치 여부를 재확인한다

### 기본 실행 명령 (첨부 레퍼런스가 있을 때)

```bash
source "$VENV"

# 1) 레퍼런스 분석 + XML 추출
python3 "$SKILL_DIR/scripts/analyze_template.py" reference.hwpx \
  --extract-header /tmp/ref_header.xml \
  --extract-section /tmp/ref_section.xml

# 2) /tmp/ref_section.xml을 복제해 /tmp/new_section0.xml 작성
#    (구조 유지, 텍스트/데이터만 요청에 맞게 수정)

# 3) 복원 빌드
python3 "$SKILL_DIR/scripts/build_hwpx.py" \
  --header /tmp/ref_header.xml \
  --section /tmp/new_section0.xml \
  --output result.hwpx

# 4) 검증
python3 "$SKILL_DIR/scripts/validate.py" result.hwpx

# 5) 쪽수 드리프트 가드 (필수)
python3 "$SKILL_DIR/scripts/page_guard.py" \
  --reference reference.hwpx \
  --output result.hwpx
```

## 환경

```
# SKILL_DIR는 이 SKILL.md가 위치한 디렉토리의 절대 경로로 설정
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"   # 스크립트 내에서
# 또는 Claude Code가 자동으로 주입하는 base directory 경로를 사용

# Python 가상환경 (프로젝트에 맞게 설정)
VENV="<프로젝트>/.venv/bin/activate"
```

모든 Python 실행 시:
```bash
# 프로젝트의 .venv를 활성화 (pip install lxml 필요)
source "$VENV"
```

## 디렉토리 구조

```
.claude/skills/hwpx/
├── SKILL.md                              # 이 파일
├── scripts/
│   ├── office/
│   │   ├── unpack.py                     # HWPX → 디렉토리 (XML pretty-print)
│   │   └── pack.py                       # 디렉토리 → HWPX
│   ├── build_hwpx.py                     # 템플릿 + XML → .hwpx 조립 (핵심, 이미지/다중섹션 지원)
│   ├── section_builder.py                # JSON → section0.xml 동적 생성 (35개 블록 타입)
│   ├── create_document.py                # JSON→HWPX 원커맨드 파이프라인 (단일/다중 섹션)
│   ├── read_document.py                  # ★ HWPX→JSON 역변환 (블록 타입 자동 감지, 스타일 추출)
│   ├── edit_document.py                  # ★ HWPX in-place 편집 (텍스트 교체, 블록 삽입/삭제, H/F 수정)
│   ├── property_registry.py              # 동적 charPr/paraPr/borderFill 레지스트리
│   ├── analyze_template.py               # HWPX 심층 분석 (레퍼런스 기반 생성용)
│   ├── validate.py                       # HWPX 구조 검증
│   ├── page_guard.py                     # 레퍼런스 대비 페이지 드리프트 위험 검사
│   ├── diff_docs.py                      # 텍스트 diff + 구조 비교
│   └── text_extract.py                   # 텍스트 추출
├── templates/
│   ├── base/                             # 베이스 템플릿 (Skeleton 기반)
│   │   ├── mimetype, META-INF/*, version.xml, settings.xml, Preview/*
│   │   └── Contents/ (header.xml, section0.xml, content.hpf)
│   ├── gonmun/                           # 공문 오버레이 (header.xml, section0.xml)
│   ├── report/                           # 보고서 오버레이
│   ├── minutes/                          # 회의록 오버레이
│   ├── proposal/                         # 제안서/사업개요 오버레이 (색상 헤더바, 번호 배지)
│   └── kcup/                             # KCUP 팀장 대응용 보고서 (20mm 여백, 전용 스타일)
└── references/
    └── hwpx-format.md                    # OWPML XML 요소 레퍼런스
```

---

## 워크플로우 1: XML-first 문서 생성 (보조 워크플로우, 레퍼런스 파일이 없을 때만)

### 흐름

1. **템플릿 선택** (base/gonmun/report/minutes/proposal)
2. **section0.xml 작성** (본문 내용)
3. **(선택) header.xml 수정** (새 스타일 추가 필요 시)
4. **build_hwpx.py로 빌드**
5. **validate.py로 검증**

> 원칙: 사용자가 레퍼런스 HWPX를 제공한 경우에는 이 워크플로우 대신 상단의 "기본 동작 모드(레퍼런스 복원 우선)"를 사용한다.

### 기본 사용법

```bash
source "$VENV"

# 빈 문서 (base 템플릿)
python3 "$SKILL_DIR/scripts/build_hwpx.py" --output result.hwpx

# 템플릿 사용
python3 "$SKILL_DIR/scripts/build_hwpx.py" --template gonmun --output result.hwpx

# 커스텀 section0.xml 오버라이드
python3 "$SKILL_DIR/scripts/build_hwpx.py" --template gonmun --section my_section0.xml --output result.hwpx

# header도 오버라이드
python3 "$SKILL_DIR/scripts/build_hwpx.py" --header my_header.xml --section my_section0.xml --output result.hwpx

# 메타데이터 설정
python3 "$SKILL_DIR/scripts/build_hwpx.py" --template report --section my.xml \
  --title "제목" --creator "작성자" --output result.hwpx
```

### 실전 패턴: section0.xml을 인라인 작성 → 빌드

```bash
# 1. section0.xml을 임시파일로 작성
SECTION=$(mktemp /tmp/section0_XXXX.xml)
cat > "$SECTION" << 'XMLEOF'
<?xml version='1.0' encoding='UTF-8'?>
<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"
        xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">
  <!-- secPr 포함 첫 문단 (base/section0.xml에서 복사) -->
  <!-- ... -->
  <hp:p id="1000000002" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
    <hp:run charPrIDRef="0">
      <hp:t>본문 내용</hp:t>
    </hp:run>
  </hp:p>
</hs:sec>
XMLEOF

# 2. 빌드
python3 "$SKILL_DIR/scripts/build_hwpx.py" --section "$SECTION" --output result.hwpx

# 3. 정리
rm -f "$SECTION"
```

---

## 워크플로우 1.5: JSON→HWPX 원커맨드 파이프라인 (레퍼런스 없이 새 문서 생성)

레퍼런스 파일 없이 새 문서를 빠르게 생성할 때 사용. JSON으로 블록을 정의하면 section_builder → build_hwpx → validate를 한 번에 실행한다.

### 기본 사용법

```bash
source "$VENV"

# 원커맨드: JSON → HWPX (기본 템플릿)
python3 "$SKILL_DIR/scripts/create_document.py" input.json -o result.hwpx

# 스타일 지정 (스타일→템플릿 자동 매핑)
python3 "$SKILL_DIR/scripts/create_document.py" input.json --style kcup -o result.hwpx

# 템플릿 직접 지정
python3 "$SKILL_DIR/scripts/create_document.py" input.json --template gonmun -o result.hwpx
```

### 스타일↔템플릿 매핑

| --style | --template | 용도 |
|---------|------------|------|
| kcup | kcup | KCUP 팀장 대응용 보고서 (20mm 여백, 48190 본문폭) |
| (미지정) | report | 기본 보고서 |

### JSON 입력 형식

```json
{
  "auto_spacing": true,
  "blocks": [
    {"type": "kcup_box", "text": "□ 항목 제목"},
    {"type": "kcup_o", "keyword": "키워드", "text": "본문 내용"},
    {"type": "kcup_dash", "text": "세부 내용"},
    {"type": "table", "rows": [["A", "B"], ["C", "D"]]}
  ]
}
```

### JSON 블록 타입 (전체 35개)

#### 기본 타입 (19개) — 모든 템플릿에서 사용 가능

| type | 필수 필드 | 설명 |
|------|-----------|------|
| text | text | 일반 문단 (charPr, paraPr 옵션) |
| empty | — | 빈 줄 (charPr 옵션) |
| heading | text, level(1-3) | 제목 문단 |
| bullet | text | 불릿 항목 (•) |
| numbered | text, number | 번호 항목 |
| indent | text, level(1-3) | 들여쓰기 문단 |
| note | text | ※ 주석 문단 |
| table | rows | 표 (colRatios, headerRows, charPr, paraPr, colSpan/rowSpan 옵션) |
| image | src | 인라인 이미지 (width/height mm옵션, align옵션) |
| label_value | pairs | 라벨-값 2열 표 ([["라벨","값"], ...]) |
| signature | lines | 서명 블록 (우측 정렬) |
| pagebreak | — | 페이지 나누기 |
| hyperlink | url | 하이퍼링크 (text, prefix, suffix 옵션) |
| text_footnote | text, footnote | 본문 텍스트 + 각주 (페이지 하단) |
| text_endnote | text, endnote | 본문 텍스트 + 미주 (문서 끝) |
| textbox | text | 글상자 (width/height mm, bg_color, border_color, lines 옵션) |
| caption | text | 캡션 (label, num 옵션 — 그림/표/수식 자동번호) |
| bookmark | name | 책갈피 (text, prefix, suffix 옵션) |
| field | field_type | 필드: date, page_number, total_pages (format, prefix, suffix 옵션) |

#### KCUP 전용 타입 (16개) — template=kcup에서 사용

| type | 필수 필드 | 설명 | 런 구조 |
|------|-----------|------|---------|
| kcup_box | text | □항목 제목 (14pt 볼드 휴먼명조) | 2-run: "□ " + 제목 |
| kcup_o | keyword, text | o항목 키워드+본문 | 4-run: "o " + 키워드 + " " + 본문 |
| kcup_o_plain | text | o항목 본문만 | 2-run: "o " + 본문 |
| kcup_o_heading | text | o항목 소제목 (볼드) | 2-run: "o " + 소제목(볼드) |
| kcup_dash | text | -항목 세부 | 2-run: "- " + 세부내용 |
| kcup_dash_plain | text | -항목 (일반 글자) | 2-run: "- " + 내용(일반) |
| kcup_numbered | number, text | 번호항목 (①②③) | 2-run: "번호 " + 내용 |
| kcup_note | text | ※주석 (9pt) | 1-run |
| kcup_attachment | text | 붙임 문단 | 2-run: "붙임 " + 내용 |
| kcup_pointer | text | ▶가리킴 | 2-run: "▶ " + 내용 |
| kcup_mixed_run | runs | 다중 run 직접 지정 | runs 배열대로 |
| kcup_box_spacing | — | □항목 전 간격줄 (14pt 160%) | auto_spacing시 자동 |
| kcup_o_spacing | — | o항목 전 간격줄 (10pt 100%) | auto_spacing시 자동 |
| kcup_o_heading_spacing | — | 소제목 전 간격줄 (14pt 100%) | auto_spacing시 자동 |
| kcup_dash_spacing | — | -항목 전 간격줄 (10pt 100%) | auto_spacing시 자동 |

#### auto_spacing 규칙

`"auto_spacing": true`를 JSON 최상위에 설정하면 블록 타입 전이 시 자동으로 간격줄 삽입:

| 이전 블록 | 다음 블록 | 삽입되는 간격줄 |
|-----------|-----------|----------------|
| box | 아무 항목 | kcup_box_spacing (14pt, 160%) |
| o/numbered | 다음 항목 | kcup_o_spacing (10pt, 100%) |
| dash | 다음 항목 | kcup_o_spacing (10pt, 100%) |
| o_heading | o_heading | kcup_o_heading_spacing (14pt, 100%) |
| note/signature | — | passthrough (간격 삽입 안 함) |

auto_spacing을 사용하면 수동 spacing 타입을 JSON에 넣지 않아도 됨 (53% JSON 감소 효과).

#### 동적 서식 (PropertyRegistry) — charPr/paraPr를 JSON dict로 인라인 지정

정적 ID 대신 dict 스펙을 넣으면 PropertyRegistry가 자동으로 header.xml에 새 엔트리를 할당한다.
동일 스펙은 같은 ID로 캐싱되어 중복 생성 없음.

```json
{
  "blocks": [
    {"type": "text", "text": "빨간 볼드 14pt",
     "charPr": {"bold": true, "size": 14, "color": "#FF0000"}},
    {"type": "text", "text": "가운데 정렬 + 줄간격 200%",
     "paraPr": {"align": "CENTER", "lineSpacing": 200}},
    {"type": "text", "text": "혼합 서식",
     "runs": [
       {"text": "일반 ", "charPr": 0},
       {"text": "빨간볼드", "charPr": {"bold": true, "color": "#FF0000"}},
       {"text": " 파란이탤릭", "charPr": {"italic": true, "color": "#0000FF"}}
     ]}
  ]
}
```

charPr dict 키: `size`(pt), `bold`, `italic`, `color`(#RRGGBB), `fontRef`, `spacing`, `underline`, `strikeout`, `shadeColor`, `height`(HWPUNIT)
paraPr dict 키: `align`(JUSTIFY/LEFT/CENTER/RIGHT), `lineSpacing`, `lineSpacingType`, `margin`(dict), `indent`, `left`, `right`, `prev`, `next`
borderFill dict 키: `bg`(#RRGGBB), `border`(all sides), `borderWidth`, `borderColor`

#### image 블록 사용법

```json
{"type": "image", "src": "/path/to/photo.png", "width": 80, "height": 60, "align": "center"}
```

- `src`: 이미지 절대 경로 (PNG/JPEG/GIF/BMP)
- `width`/`height`: mm 단위 (생략 시 원본 비율로 본문 폭에 맞춤)
- `align`: `left`(기본)/`center`/`right`
- BinData/ 복사 및 content.hpf manifest 등록 자동 처리

#### 다중 섹션

```json
{
  "sections": [
    {"blocks": [{"type": "heading", "text": "1장", "level": 1}]},
    {"blocks": [{"type": "heading", "text": "2장", "level": 1}]}
  ]
}
```

각 섹션이 별도 section0.xml, section1.xml로 생성되고 content.hpf에 자동 등록.

#### 머리말/꼬리말 (header/footer)

JSON 최상위에 `"header"` / `"footer"` 키로 정의. 페이지 머리말·꼬리말을 자동 생성한다.

```json
{
  "header": {
    "text": "- {{page}} -",
    "align": "center"
  },
  "footer": {
    "text": "{{page}} / {{total_pages}}",
    "align": "right"
  },
  "blocks": [...]
}
```

- `text`: 표시 텍스트. `{{page}}`→현재 쪽 번호, `{{total_pages}}`→전체 쪽수 (autoNum 자동 변환)
- `align`: `left`/`center`/`right` (기본 `left`)
- `applyPageType`: `BOTH`/`EVEN`/`ODD` (기본 `BOTH`)
- 다중 섹션에서는 각 섹션별 또는 전역 header/footer 모두 지원
- XML 구조: `hp:ctrl > hp:header/footer > hp:subList > hp:p` (hp 네임스페이스)

#### 하이퍼링크 (hyperlink) 블록

```json
{"type": "hyperlink", "url": "https://example.com", "text": "표시 텍스트", "prefix": "앞 텍스트: ", "suffix": " 참조"}
```

- `url`: 대상 URL (필수)
- `text`: 링크 표시 텍스트 (생략 시 URL 그대로 표시)
- `prefix`: 링크 앞에 붙는 일반 텍스트 (옵션)
- `suffix`: 링크 뒤에 붙는 일반 텍스트 (옵션)
- XML 구조: `hp:fieldBegin type="HYPERLINK"` + `hp:parameters` + display run + `hp:fieldEnd`

#### 각주/미주 (footnote/endnote) 블록

```json
{"type": "text_footnote", "text": "본문 텍스트", "footnote": "각주 내용"}
{"type": "text_endnote", "text": "본문 텍스트", "endnote": "미주 내용"}
```

- `text`: 본문에 표시되는 텍스트 (각주/미주 마커가 끝에 자동 부착)
- `footnote`/`endnote`: 주석 내용
- 번호 자동 증가 (문서 내 순차 매김)
- 각주는 해당 페이지 하단, 미주는 문서 끝에 표시
- XML 구조: `hp:ctrl > hp:footNote/endNote > hp:subList > hp:p` (autoNum FOOTNOTE/ENDNOTE)

#### 글상자 (textbox) 블록

```json
{"type": "textbox", "text": "글상자 내용", "width": 100, "height": 30,
 "bg_color": "#E8F0FE", "border_color": "#1A73E8", "text_align": "center"}
```

- `text`: 단일 텍스트 (필수), 또는 `lines`: 여러줄 배열
- `width`/`height`: mm 단위 (생략 시 본문폭 × 30mm)
- `bg_color`: 배경색 #RRGGBB (기본 #FFFFFF)
- `border_color`: 테두리색 (기본 #000000), `border_width`: 두께 (기본 "0.12 mm")
- `text_align`: 글상자 내 수직정렬 top/center/bottom (기본 center)
- `charPr`/`paraPr`: 내부 텍스트 서식 (옵션, PropertyRegistry 지원)
- XML 구조: `hp:rect > hp:drawText > hp:subList > hp:p`

#### 다단 레이아웃 (columns)

JSON 최상위에 `"columns"` 키로 다단 설정. secPr의 colPr을 오버라이드한다.

```json
{
  "columns": 2,
  "blocks": [...]
}
```

- `columns`: int (단 수) 또는 dict `{"count": 2, "gap": 1134, "layout": "LEFT", "same_width": true}`
- `gap`: 단 사이 간격 (HWPUNIT, 기본 1134 ≈ 4mm)
- 다중 섹션에서 섹션별 다단 설정 가능

#### 문단 배경색 (paraPr borderFill)

기존 `paraPr` dict에 `borderFill` 키를 넣으면 자동으로 문단 배경색이 적용된다.

```json
{"type": "text", "text": "노란 배경", "paraPr": {"borderFill": {"bg": "#FFF3CD"}}}
```

- `borderFill.bg`: 배경색 #RRGGBB
- PropertyRegistry가 자동으로 borderFill 엔트리를 생성/캐싱하고 paraPr에 연결

#### 캡션 (caption) 블록

```json
{"type": "caption", "label": "그림", "num": 1, "text": "도형 설명 텍스트"}
```

- `label`: 캡션 접두어 — "그림", "표", "수식" (기본 "그림")
- `num`: 번호 (생략 시 레이블별 자동 증가)
- `text`: 설명 텍스트 (필수)
- `charPr`/`paraPr`: 서식 옵션 (기본: styleIDRef=22 "캡션" 스타일, paraPr=19)
- 출력 형식: "그림 1. 설명 텍스트"
- 모든 한글 템플릿에 기본 내장된 캡션 스타일(id=22)을 사용

#### 책갈피 (bookmark) 블록

```json
{"type": "bookmark", "name": "section_intro", "text": "책갈피된 텍스트"}
```

- `name`: 책갈피 이름 (필수, 영문/숫자 권장)
- `text`: 표시 텍스트 (선택, 생략 시 빈 포인트 책갈피)
- `prefix`/`suffix`: 앞뒤 텍스트 (선택)
- `charPr`/`paraPr`: 서식 옵션
- XML 구조: `hp:fieldBegin type="BOOKMARK"` + 텍스트 + `hp:fieldEnd` (하이퍼링크와 동일 패턴)

#### 필드 (field) 블록

```json
{"type": "field", "field_type": "date", "format": "yyyy-MM-dd", "prefix": "작성일: "}
```

- `field_type` (필수): `date` | `page_number` | `total_pages`
- `format`: 날짜 형식 (date 전용) — "yyyy-MM-dd", "yyyy년 M월 d일", "yyyy.MM.dd" 등
- `display`: 기본 표시 텍스트 (date 전용, 생략 시 현재 날짜로 자동 생성)
- `prefix`/`suffix`: 앞뒤 텍스트 (선택)
- `charPr`/`paraPr`: 서식 옵션
- date: `hp:fieldBegin type="DATE"` + 표시텍스트 + `hp:fieldEnd`
- page_number/total_pages: `hp:autoNum numType="PAGE"/"TOTAL_PAGE"` (머리말/꼬리말과 동일 메커니즘)

---

## section0.xml 작성 가이드

### 필수 구조

section0.xml의 첫 문단(`<hp:p>`)의 첫 런(`<hp:run>`)에 반드시 `<hp:secPr>`과 `<hp:colPr>` 포함:

```xml
<hp:p id="1000000001" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
  <hp:run charPrIDRef="0">
    <hp:secPr ...>
      <!-- 페이지 크기, 여백, 각주/미주 설정 등 -->
    </hp:secPr>
    <hp:ctrl>
      <hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="1" sameSz="1" sameGap="0"/>
    </hp:ctrl>
  </hp:run>
  <hp:run charPrIDRef="0"><hp:t/></hp:run>
</hp:p>
```

**Tip**: `templates/base/Contents/section0.xml` 의 첫 문단을 그대로 복사하면 된다.

### 문단

```xml
<hp:p id="고유ID" paraPrIDRef="문단스타일ID" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
  <hp:run charPrIDRef="글자스타일ID">
    <hp:t>텍스트 내용</hp:t>
  </hp:run>
</hp:p>
```

### 빈 줄

```xml
<hp:p id="고유ID" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
  <hp:run charPrIDRef="0"><hp:t/></hp:run>
</hp:p>
```

### 서식 혼합 런 (한 문단에 여러 스타일)

```xml
<hp:p id="고유ID" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
  <hp:run charPrIDRef="0"><hp:t>일반 텍스트 </hp:t></hp:run>
  <hp:run charPrIDRef="7"><hp:t>볼드 텍스트</hp:t></hp:run>
  <hp:run charPrIDRef="0"><hp:t> 다시 일반</hp:t></hp:run>
</hp:p>
```

### 표 작성법

```xml
<hp:p id="고유ID" paraPrIDRef="0" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">
  <hp:run charPrIDRef="0">
    <hp:tbl id="고유ID" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM"
            textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL"
            repeatHeader="0" rowCnt="행수" colCnt="열수" cellSpacing="0"
            borderFillIDRef="3" noAdjust="0">
      <hp:sz width="42520" widthRelTo="ABSOLUTE" height="전체높이" heightRelTo="ABSOLUTE" protect="0"/>
      <hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0"
              holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP"
              horzAlign="LEFT" vertOffset="0" horzOffset="0"/>
      <hp:outMargin left="0" right="0" top="0" bottom="0"/>
      <hp:inMargin left="0" right="0" top="0" bottom="0"/>
      <hp:tr>
        <hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="1" borderFillIDRef="4">
          <hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER"
                     linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0"
                     hasTextRef="0" hasNumRef="0">
            <hp:p paraPrIDRef="21" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0" id="고유ID">
              <hp:run charPrIDRef="9"><hp:t>헤더 셀</hp:t></hp:run>
            </hp:p>
          </hp:subList>
          <hp:cellAddr colAddr="0" rowAddr="0"/>
          <hp:cellSpan colSpan="1" rowSpan="1"/>
          <hp:cellSz width="열너비" height="행높이"/>
          <hp:cellMargin left="0" right="0" top="0" bottom="0"/>
        </hp:tc>
        <!-- 나머지 셀... -->
      </hp:tr>
    </hp:tbl>
  </hp:run>
</hp:p>
```

### 표 크기 계산

- **A4 본문폭**: 42520 HWPUNIT = 59528(용지) - 8504×2(좌우여백, 30mm)
- **KCUP 본문폭**: 48190 HWPUNIT = 59528(용지) - 5669×2(좌우여백, 20mm)
- **열 너비 합 = 본문폭** (42520 또는 kcup은 48190)
- 예: 3열 균등 → 14173 + 14173 + 14174 = 42520
- 예: 2열 (라벨:내용 = 1:4) → 8504 + 34016 = 42520
- **행 높이**: 셀당 보통 2400~3600 HWPUNIT

### ID 규칙

- 문단 id: `1000000001`부터 순차 증가
- 표 id: `1000000099` 등 별도 범위 사용 권장
- 모든 id는 문서 내 고유해야 함

---

## header.xml 수정 가이드

### 커스텀 스타일 추가 방법

1. `templates/base/Contents/header.xml` 복사
2. 필요한 charPr/paraPr/borderFill 추가
3. 각 그룹의 `itemCnt` 속성 업데이트

### charPr 추가 예시 (볼드 14pt)

```xml
<hh:charPr id="8" height="1400" textColor="#000000" shadeColor="none"
           useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="2">
  <hh:fontRef hangul="1" latin="1" hanja="1" japanese="1" other="1" symbol="1" user="1"/>
  <hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>
  <hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>
  <hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>
  <hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>
  <hh:bold/>
  <hh:underline type="NONE" shape="SOLID" color="#000000"/>
  <hh:strikeout shape="NONE" color="#000000"/>
  <hh:outline type="NONE"/>
  <hh:shadow type="NONE" color="#C0C0C0" offsetX="10" offsetY="10"/>
</hh:charPr>
```

### 폰트 참조 체계

- `fontRef` 값은 `fontfaces`에 정의된 font id
- `hangul="0"` → 함초롬돋움 (고딕)
- `hangul="1"` → 함초롬바탕 (명조)
- 7개 언어 모두 동일하게 설정

### paraPr 추가 시 주의

- 반드시 `hp:switch` 구조 포함 (`hp:case` + `hp:default`)
- `hp:case`와 `hp:default`의 값은 보통 동일 (또는 default가 2배)
- `borderFillIDRef="2"` 유지

---

## 템플릿별 스타일 ID 맵

### base (기본)

| ID | 유형 | 설명 |
|----|------|------|
| charPr 0 | 글자 | 10pt 함초롬바탕, 기본 |
| charPr 1 | 글자 | 10pt 함초롬돋움 |
| charPr 2~6 | 글자 | Skeleton 기본 스타일 |
| paraPr 0 | 문단 | JUSTIFY, 160% 줄간격 |
| paraPr 1~19 | 문단 | Skeleton 기본 (개요, 각주 등) |
| borderFill 1 | 테두리 | 없음 (페이지 보더) |
| borderFill 2 | 테두리 | 없음 + 투명배경 (참조용) |

### gonmun (공문) — base + 추가

| ID | 유형 | 설명 |
|----|------|------|
| charPr 7 | 글자 | 22pt 볼드 함초롬바탕 (기관명/제목) |
| charPr 8 | 글자 | 16pt 볼드 함초롬바탕 (서명자) |
| charPr 9 | 글자 | 8pt 함초롬바탕 (하단 연락처) |
| charPr 10 | 글자 | 10pt 볼드 함초롬바탕 (표 헤더) |
| paraPr 20 | 문단 | CENTER, 160% 줄간격 |
| paraPr 21 | 문단 | CENTER, 130% (표 셀) |
| paraPr 22 | 문단 | JUSTIFY, 130% (표 셀) |
| borderFill 3 | 테두리 | SOLID 0.12mm 4면 |
| borderFill 4 | 테두리 | SOLID 0.12mm + #D6DCE4 배경 |

### report (보고서) — base + 추가

| ID | 유형 | 설명 |
|----|------|------|
| charPr 7 | 글자 | 20pt 볼드 (문서 제목) |
| charPr 8 | 글자 | 14pt 볼드 (소제목) |
| charPr 9 | 글자 | 10pt 볼드 (표 헤더) |
| charPr 10 | 글자 | 10pt 볼드+밑줄 (강조 텍스트) |
| charPr 11 | 글자 | 9pt 함초롬바탕 (소형/각주) |
| charPr 12 | 글자 | 16pt 볼드 함초롬바탕 (1줄 제목) |
| charPr 13 | 글자 | 12pt 볼드 함초롬돋움 (섹션 헤더) |
| paraPr 20~22 | 문단 | CENTER/JUSTIFY 변형 |
| paraPr 23 | 문단 | RIGHT 정렬, 160% 줄간격 |
| paraPr 24 | 문단 | JUSTIFY, left 600 (□ 체크항목 들여쓰기) |
| paraPr 25 | 문단 | JUSTIFY, left 1200 (하위항목 ①②③ 들여쓰기) |
| paraPr 26 | 문단 | JUSTIFY, left 1800 (깊은 하위항목 - 들여쓰기) |
| paraPr 27 | 문단 | LEFT, 상하단 테두리선 (섹션 헤더용), prev 400 |
| borderFill 3 | 테두리 | SOLID 0.12mm 4면 |
| borderFill 4 | 테두리 | SOLID 0.12mm + #DAEEF3 배경 |
| borderFill 5 | 테두리 | 상단 0.4mm 굵은선 + 하단 0.12mm 얇은선 (섹션 헤더) |

**들여쓰기 규칙**: 공백 문자가 아닌 반드시 paraPr의 left margin 사용. □ 항목은 paraPr 24, 하위 ①②③ 는 paraPr 25, 깊은 - 항목은 paraPr 26.

**섹션 헤더 규칙**: paraPr 27 + charPr 13 조합. 문단 테두리(borderFillIDRef="5")로 상단 굵은선 + 하단 얇은선 자동 표시.

### minutes (회의록) — base + 추가

| ID | 유형 | 설명 |
|----|------|------|
| charPr 7 | 글자 | 18pt 볼드 (제목) |
| charPr 8 | 글자 | 12pt 볼드 (섹션 라벨) |
| charPr 9 | 글자 | 10pt 볼드 (표 헤더) |
| paraPr 20~22 | 문단 | CENTER/JUSTIFY 변형 |
| borderFill 3 | 테두리 | SOLID 0.12mm 4면 |
| borderFill 4 | 테두리 | SOLID 0.12mm + #E2EFDA 배경 |

### proposal (제안서/사업개요) — base + 추가

시각적 구분이 필요한 공식 문서용. 색상 배경 헤더바와 번호 배지를 표(table) 기반 레이아웃으로 구현.

| ID | 유형 | 설명 |
|----|------|------|
| charPr 7 | 글자 | 20pt 볼드 함초롬바탕 (문서 제목) |
| charPr 8 | 글자 | 14pt 볼드 함초롬바탕 (소제목) |
| charPr 9 | 글자 | 10pt 볼드 함초롬바탕 (표 헤더) |
| charPr 10 | 글자 | 14pt 볼드 흰색 함초롬돋움 (대항목 번호, 녹색 배경) |
| charPr 11 | 글자 | 11pt 볼드 흰색 함초롬돋움 (소항목 번호, 파란 배경) |
| paraPr 20 | 문단 | CENTER, 160% 줄간격 |
| paraPr 21 | 문단 | CENTER, 130% (표 셀) |
| paraPr 22 | 문단 | JUSTIFY, 130% (표 셀) |
| borderFill 3 | 테두리 | SOLID 0.12mm 4면 |
| borderFill 4 | 테두리 | SOLID 0.12mm + #DAEEF3 배경 |
| borderFill 5 | 테두리 | 올리브녹색 배경 #7B8B3D (대항목 번호 셀) |
| borderFill 6 | 테두리 | 연한 회색 배경 #F2F2F2 + 회색 테두리 (대항목 제목 셀) |
| borderFill 7 | 테두리 | 파란색 배경 #4472C4 (소항목 번호 배지) |
| borderFill 8 | 테두리 | 하단 테두리만 #D0D0D0 (소항목 제목 영역) |

#### proposal 레이아웃 패턴

**대항목 헤더** (2셀 표: 번호 + 제목):
```xml
<!-- borderFillIDRef="5" + charPrIDRef="10" → 녹색배경 흰색 로마숫자 -->
<!-- borderFillIDRef="6" + charPrIDRef="8"  → 회색배경 검정 볼드 제목 -->
```

**소항목 헤더** (2셀 표: 번호배지 + 제목):
```xml
<!-- borderFillIDRef="7" + charPrIDRef="11" → 파란배경 흰색 아라비아숫자 -->
<!-- borderFillIDRef="8" + charPrIDRef="8"  → 하단선만 검정 볼드 제목 -->
```

### kcup (KCUP 팀장 대응용 보고서) — 독립 헤더

**페이지**: A4, 20mm 여백 (본문폭 48190 HWPUNIT, 기본 42520과 다름)
**폰트**: 함초롬돋움(0), 함초롬바탕(1), HY헤드라인M(2), 휴먼명조(3), 고도M(4)

| ID | 유형 | 설명 |
|----|------|------|
| charPr 15 | 글자 | 19pt 볼드 HY헤드라인M (표지 제목) |
| charPr 16 | 글자 | 14pt 휴먼명조 (본문) |
| charPr 17 | 글자 | 14pt 볼드 휴먼명조 (키워드) |
| charPr 18 | 글자 | 14pt 볼드 휴먼명조 (□항목 제목) |
| charPr 19 | 글자 | 14pt 휴먼명조 (간격줄, 160% 참조) |
| charPr 20 | 글자 | 14pt 휴먼명조 (간격줄 alt) |
| charPr 21 | 글자 | 10pt 휴먼명조 (간격줄, 100%) |
| charPr 22 | 글자 | 14pt 휴먼명조 (대괄호/기호) |
| charPr 25 | 글자 | 12pt 고도M (sp_n4_12) |
| charPr 27 | 글자 | 고도M (sp_n3) |
| charPr 28 | 글자 | 12pt 고도M (sp_n1_12) |
| charPr 29 | 글자 | 고도M (sp_n1) |
| charPr 34 | 글자 | 고도M (sp_n4) |
| charPr 35 | 글자 | 고도M (sp_n5) |
| charPr 37 | 글자 | 고도M (sp_p3) |
| paraPr 26 | 문단 | JUSTIFY, intent=-2319 (o항목 hanging indent) |
| paraPr 28 | 문단 | JUSTIFY, left=252 (□항목) |
| paraPr 30 | 문단 | JUSTIFY, intent=-3103 (-항목 hanging indent) |
| paraPr 31 | 문단 | JUSTIFY, 100% 줄간격 (간격줄) |
| borderFill 3 | 테두리 | SOLID 테두리 |

**KCUP_CP 상수맵** (section_builder.py):
```python
KCUP_CP = {
    "cover_title": 15, "body": 16, "bold": 17, "box": 18,
    "gap14": 19, "gap14_alt": 20, "gap10": 21, "bracket": 22,
    "sp_n4_12": 25, "sp_n3": 27, "sp_n1_12": 28, "sp_n1": 29,
    "sp_n4": 34, "sp_n5": 35, "sp_p3": 37,
}
KCUP_PP = {"o": 26, "box": 28, "dash": 30, "gap": 31}
```

**KCUP 런 분리 규칙**:
- □항목: `[box체 "□ "] + [box체 제목]` (2-run, paraPr=box)
- o키워드: `[body "o "] + [bold 키워드] + [body " "] + [body 본문]` (4-run, paraPr=o)
- o소제목: `[body "o "] + [bold 소제목]` (2-run, paraPr=o)
- -항목: `[body "- "] + [body 내용]` (2-run, paraPr=dash)

---

## 워크플로우 2: 기존 문서 편집 (unpack → Edit → pack)

```bash
source "$VENV"

# 1. HWPX → 디렉토리 (XML pretty-print)
python3 "$SKILL_DIR/scripts/office/unpack.py" document.hwpx ./unpacked/

# 2. XML 직접 편집 (Claude가 Read/Edit 도구로)
#    본문: ./unpacked/Contents/section0.xml
#    스타일: ./unpacked/Contents/header.xml

# 3. 다시 HWPX로 패키징
python3 "$SKILL_DIR/scripts/office/pack.py" ./unpacked/ edited.hwpx

# 4. 검증
python3 "$SKILL_DIR/scripts/validate.py" edited.hwpx
```

---

## 워크플로우 3: HWPX → JSON 구조 읽기 (read_document.py)

HWPX 문서를 파싱하여 `section_builder.py` 호환 JSON으로 역변환한다.
라운드트립(HWPX → JSON → HWPX → JSON) 100% 일치가 핵심 목표.

### CLI 사용법

```bash
source "$VENV"

# 기본 출력 (stdout, 압축 JSON)
python3 "$SKILL_DIR/scripts/read_document.py" document.hwpx

# Pretty-print + 파일 저장
python3 "$SKILL_DIR/scripts/read_document.py" document.hwpx --pretty -o output.json

# 스타일 스펙 포함 (charPr/paraPr 상세 정보를 _styles 키에 추가)
python3 "$SKILL_DIR/scripts/read_document.py" document.hwpx --pretty --include-styles -o output.json
```

### 출력 JSON 구조

```json
{
  "template": "kcup",
  "header": {"text": "- {{page}} -", "align": "center"},
  "footer": {"text": "{{page}} / {{total_pages}}", "align": "right"},
  "blocks": [
    {"type": "heading", "text": "제목", "level": 1},
    {"type": "text", "text": "본문 텍스트"},
    {"type": "kcup_box", "text": "□ 항목 제목"},
    {"type": "kcup_o", "keyword": "핵심", "text": "설명 내용"},
    {"type": "table", "rows": [["A", "B"], ["C", "D"]]},
    {"type": "spacing", "height": 10}
  ]
}
```

### 감지 블록 타입 (35종)

**기본 19종**: heading(1~6), text, spacing, table, image, textbox, bullet, numbered(circle/parenthesis), page_break, section_break, text_footnote, text_endnote, hyperlink, bookmark, field, caption

**KCUP 16종**: kcup_box, kcup_o, kcup_o_heading, kcup_dash, kcup_gap14, kcup_gap14_alt, kcup_gap10, kcup_note, kcup_signature, kcup_cover_title, kcup_spacing_*, kcup_table

### Python API

```python
from read_document import HWPXReader

reader = HWPXReader("document.hwpx")
reader.load()
result = reader.to_json(include_styles=True)  # dict 반환
# result["blocks"], result["header"], result["footer"], result.get("_styles")
```

### 활용 시나리오

- **라운드트립 편집**: HWPX → JSON으로 읽고 → 블록 수정 → `create_document.py`로 재생성
- **문서 분석**: 블록 타입 통계, 구조 파악, 스타일 사용 패턴 조회
- **마이그레이션**: HWPX 콘텐츠를 JSON으로 추출하여 다른 포맷으로 변환

---

## 워크플로우 4: HWPX 인플레이스 편집 (edit_document.py)

기존 HWPX의 ZIP 내부 section0.xml을 직접 수정하여 저장한다.
스타일·서식·이미지·표 구조 등 원본의 모든 요소가 보존되며, 변경 대상만 정밀하게 수정된다.

### CLI 사용법

```bash
source "$VENV"

# 텍스트 찾아 바꾸기
python3 "$SKILL_DIR/scripts/edit_document.py" doc.hwpx \
  --replace "원본텍스트" "새텍스트" -o edited.hwpx

# 정규식 찾아 바꾸기
python3 "$SKILL_DIR/scripts/edit_document.py" doc.hwpx \
  --replace "2024년 \d+월" "2025년 3월" --regex -o edited.hwpx

# 블록 삭제 (인덱스 5번)
python3 "$SKILL_DIR/scripts/edit_document.py" doc.hwpx \
  --delete-block 5 -o edited.hwpx

# 텍스트 블록 삽입 (인덱스 3 위치에)
python3 "$SKILL_DIR/scripts/edit_document.py" doc.hwpx \
  --insert-text 3 "새로 삽입할 문단" -o edited.hwpx

# JSON 편집 스크립트로 복합 작업
python3 "$SKILL_DIR/scripts/edit_document.py" doc.hwpx \
  --edit-json edit_commands.json -o edited.hwpx
```

### JSON 편집 스크립트 형식

```json
{
  "operations": [
    {"op": "replace_text", "find": "원본", "replace": "새것"},
    {"op": "replace_text", "find": "2024년 \\d+월", "replace": "2025년 3월", "regex": true},
    {"op": "insert_block", "index": 3, "block": {"type": "text", "text": "새 문단"}},
    {"op": "delete_block", "index": 5},
    {"op": "update_block_text", "index": 2, "text": "수정된 텍스트"},
    {"op": "update_block", "index": 4, "block": {"type": "heading", "text": "새 제목", "level": 2}},
    {"op": "reorder_blocks", "order": [0, 2, 1, 3, 4]},
    {"op": "update_header_footer", "target": "header", "text": "새 머리말", "align": "center"},
    {"op": "update_header_footer", "target": "footer", "text": "{{page}} / {{total_pages}}"}
  ]
}
```

### 지원 편집 작업 (6종)

| 작업 | 설명 |
|------|------|
| `replace_text` | 텍스트 찾아 바꾸기 (정규식 지원) |
| `insert_block` | 지정 인덱스에 새 블록 삽입 (section_builder 활용) |
| `delete_block` | 인덱스로 블록(문단/표) 삭제 |
| `update_block_text` | 인덱스로 블록의 텍스트만 수정 (서식 보존) |
| `update_block` | 인덱스로 블록 전체 교체 (새 블록으로 대체) |
| `reorder_blocks` | 블록 순서 재배치 |
| `update_header_footer` | 머리말/꼬리말 텍스트·정렬 수정 |

### Python API

```python
from edit_document import HWPXEditor

editor = HWPXEditor("doc.hwpx")
editor.load()

editor.replace_text("원본", "새것", regex=False)
editor.insert_block(3, {"type": "text", "text": "삽입 문단"})
editor.delete_block(5)
editor.update_block_text(2, "수정 텍스트")
editor.update_header_footer("footer", "{{page}} / {{total_pages}}", align="right")

editor.save("edited.hwpx")  # mimetype ZIP_STORED 자동 보장
```

### 핵심 원칙

- **서식 100% 보존**: ZIP 내부의 header.xml, BinData, META-INF 등 편집 대상 외 파일은 원본 그대로 유지
- **mimetype ZIP_STORED**: 재패키징 시 mimetype은 반드시 ZIP_STORED(compress_type=0)
- **인덱스 기준**: 블록 인덱스는 `read_document.py` 출력의 blocks 배열 순서와 일치
- **insert_block은 section_builder 활용**: 삽입할 블록의 JSON은 `section_builder.py`의 블록 타입 스펙을 따름

---

## 워크플로우 5: 읽기/텍스트 추출

```bash
source "$VENV"

# 순수 텍스트
python3 "$SKILL_DIR/scripts/text_extract.py" document.hwpx

# 테이블 포함
python3 "$SKILL_DIR/scripts/text_extract.py" document.hwpx --include-tables

# 마크다운 형식
python3 "$SKILL_DIR/scripts/text_extract.py" document.hwpx --format markdown
```

### Python API

```python
from hwpx import TextExtractor
with TextExtractor("document.hwpx") as ext:
    text = ext.extract_text(include_nested=True, object_behavior="nested")
    print(text)
```

---

## 워크플로우 6: 검증

```bash
source "$VENV"
python3 "$SKILL_DIR/scripts/validate.py" document.hwpx
```

검증 항목: ZIP 유효성, 필수 파일 존재, mimetype 내용/위치/압축방식, XML well-formedness

---

## 워크플로우 7: 레퍼런스 기반 문서 생성 (첨부 HWPX가 있을 때 기본 적용)

사용자가 제공한 HWPX 파일을 분석하여 동일한 레이아웃의 문서를 생성하는 워크플로우.
이 스킬에서는 첨부 레퍼런스가 존재하면 본 워크플로우를 기본으로 사용한다.

### 흐름

1. **분석** — `analyze_template.py`로 레퍼런스 문서 심층 분석
2. **header.xml 추출** — 레퍼런스의 스타일 정의를 그대로 사용
3. **section0.xml 작성** — 분석 결과의 구조를 따라 새 내용으로 작성
4. **빌드** — 추출한 header.xml + 새 section0.xml로 빌드
5. **검증** — `validate.py`
6. **쪽수 가드** — `page_guard.py` (실패 시 재수정)

### 사용법

```bash
source "$VENV"

# 1. 심층 분석 (구조 청사진 출력)
python3 "$SKILL_DIR/scripts/analyze_template.py" reference.hwpx

# 2. header.xml과 section0.xml을 추출하여 참고용으로 보관
python3 "$SKILL_DIR/scripts/analyze_template.py" reference.hwpx \
  --extract-header /tmp/ref_header.xml \
  --extract-section /tmp/ref_section.xml

# 3. 분석 결과를 보고 새 section0.xml 작성
#    - 동일한 charPrIDRef, paraPrIDRef 사용
#    - 동일한 테이블 구조 (열 수, 열 너비, 행 수, rowSpan/colSpan)
#    - 동일한 borderFillIDRef, cellMargin

# 4. 추출한 header.xml + 새 section0.xml로 빌드
python3 "$SKILL_DIR/scripts/build_hwpx.py" \
  --header /tmp/ref_header.xml \
  --section /tmp/new_section0.xml \
  --output result.hwpx

# 5. 검증
python3 "$SKILL_DIR/scripts/validate.py" result.hwpx

# 6. 쪽수 드리프트 가드 (필수)
python3 "$SKILL_DIR/scripts/page_guard.py" \
  --reference reference.hwpx \
  --output result.hwpx
```

### 분석 출력 항목

| 항목 | 설명 |
|------|------|
| 폰트 정의 | hangul/latin 폰트 매핑 |
| borderFill | 테두리 타입/두께 + 배경색 (각 면별 상세) |
| charPr | 글꼴 크기(pt), 폰트명, 색상, 볼드/이탤릭/밑줄/취소선, fontRef |
| paraPr | 정렬, 줄간격, 여백(left/right/prev/next/intent), heading, borderFillIDRef |
| 문서 구조 | 페이지 크기, 여백, 페이지 테두리, 본문폭 |
| 본문 상세 | 모든 문단의 id/paraPr/charPr + 텍스트 내용 |
| 표 상세 | 행×열, 열너비 배열, 셀별 span/margin/borderFill/vertAlign + 내용 |

### 핵심 원칙

- **charPrIDRef/paraPrIDRef를 그대로 사용**: 추출한 header.xml의 스타일 ID를 변경하지 말 것
- **열 너비 합계 = 본문폭**: 분석 결과의 열너비 배열을 그대로 복제
- **rowSpan/colSpan 패턴 유지**: 분석된 셀 병합 구조를 정확히 재현
- **cellMargin 보존**: 분석된 셀 여백 값을 동일하게 적용
- **페이지 증가 금지**: 사용자 명시 승인 없이 결과 쪽수를 늘리지 말 것
- **치환 우선 편집**: 새 문단/표 추가보다 기존 텍스트 노드 치환을 우선할 것

---

## 스크립트 요약

| 스크립트 | 용도 |
|----------|------|
| `scripts/create_document.py` | **원커맨드** — JSON → section_builder → build_hwpx → validate 파이프라인 |
| `scripts/read_document.py` | **HWPX → JSON 역변환** — 35개 블록 타입 자동 감지, 라운드트립 지원 |
| `scripts/edit_document.py` | **HWPX 인플레이스 편집** — 텍스트 교체/블록 삽입·삭제·수정/머리말·꼬리말 변경 |
| `scripts/section_builder.py` | JSON → section0.xml 동적 생성 (35개 블록 타입, auto_spacing) |
| `scripts/build_hwpx.py` | 템플릿 + XML → HWPX 조립 |
| `scripts/analyze_template.py` | HWPX 심층 분석 (레퍼런스 기반 생성의 청사진) |
| `scripts/office/unpack.py` | HWPX → 디렉토리 (XML pretty-print) |
| `scripts/office/pack.py` | 디렉토리 → HWPX (mimetype first) |
| `scripts/validate.py` | HWPX 파일 구조 검증 |
| `scripts/page_guard.py` | 레퍼런스 대비 페이지 드리프트 위험 검사 (필수 게이트) |
| `scripts/diff_docs.py` | 텍스트 unified diff + 구조 비교 |
| `scripts/text_extract.py` | HWPX 텍스트 추출 |

## 단위 변환

| 값 | HWPUNIT | 의미 |
|----|---------|------|
| 1pt | 100 | 기본 단위 |
| 10pt | 1000 | 기본 글자크기 |
| 1mm | 283.5 | 밀리미터 |
| 1cm | 2835 | 센티미터 |
| A4 폭 | 59528 | 210mm |
| A4 높이 | 84186 | 297mm |
| 좌우여백(기본) | 8504 | 30mm |
| 좌우여백(kcup) | 5669 | 20mm |
| 본문폭(기본) | 42520 | 150mm (A4-좌우여백 30mm) |
| 본문폭(kcup) | 48190 | 170mm (A4-좌우여백 20mm) |

## Critical Rules

1. **HWPX만 지원**: `.hwp`(바이너리) 파일은 지원하지 않는다. 사용자가 `.hwp` 파일을 제공하면 **한글 오피스에서 `.hwpx`로 다시 저장**하도록 안내할 것. (파일 → 다른 이름으로 저장 → 파일 형식: HWPX)
2. **secPr 필수**: section0.xml 첫 문단의 첫 run에 반드시 secPr + colPr 포함
3. **mimetype 순서**: HWPX 패키징 시 mimetype은 첫 번째 ZIP 엔트리, ZIP_STORED
4. **네임스페이스 보존**: XML 편집 시 `hp:`, `hs:`, `hh:`, `hc:` 접두사 유지
5. **itemCnt 정합성**: header.xml의 charProperties/paraProperties/borderFills itemCnt가 실제 자식 수와 일치
6. **ID 참조 정합성**: section0.xml의 charPrIDRef/paraPrIDRef가 header.xml 정의와 일치
7. **venv 사용**: 프로젝트의 `.venv/bin/python3` (lxml 패키지 필요)
8. **검증**: 생성 후 반드시 `validate.py`로 무결성 확인
9. **레퍼런스**: 상세 XML 구조는 `$SKILL_DIR/references/hwpx-format.md` 참조
10. **build_hwpx.py 우선**: 새 문서 생성은 build_hwpx.py 사용 (python-hwpx API 직접 호출 지양)
11. **빈 줄**: `<hp:t/>` 사용 (self-closing tag)
12. **레퍼런스 우선 강제**: 사용자가 HWPX를 첨부하면 반드시 `analyze_template.py` + 추출 XML 기반으로 복원/재작성할 것
13. **examples 폴더 미사용**: 작업 중 `.claude/skills/hwpx/examples/*` 파일은 읽기/참조/복사에 사용하지 말 것
14. **쪽수 동일 필수**: 레퍼런스 기반 작업에서는 최종 결과의 쪽수를 레퍼런스와 동일하게 유지할 것
15. **무단 페이지 증가 금지**: 사용자 명시 요청/승인 없이 쪽수 증가를 유발하는 구조 변경 금지
16. **구조 변경 제한**: 사용자 요청이 없는 한 문단/표의 추가·삭제·분할·병합 금지 (치환 중심 편집)
17. **page_guard 필수 통과**: `validate.py`와 별개로 `page_guard.py`를 반드시 통과해야 완료 처리
