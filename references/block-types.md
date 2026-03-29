# 블록 타입 상세 스펙

section_builder.py가 처리하는 35개 블록 타입의 JSON 필드 명세.

---

## 기본 타입 (19개)

### text / paragraph

```json
{"type": "text", "text": "본문 텍스트"}
{"type": "text", "text": "혼합 서식", "runs": [
  {"text": "일반 ", "charPr": 0},
  {"text": "볼드", "charPr": {"bold": true}}
]}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| text | str | 단일 텍스트 (runs 없을 때) |
| runs | list | 다중 run (`[{"text":..., "charPr":...}]`) |
| charPr | int\|dict | 글자 스타일 ID 또는 dict 스펙 |
| paraPr | int\|dict | 문단 스타일 ID 또는 dict 스펙 |

### empty

```json
{"type": "empty"}
{"type": "empty", "charPr": 19}
```

빈 줄. charPr로 줄높이 조절 가능.

### heading

```json
{"type": "heading", "text": "제목", "level": 1}
```

| 필드 | 기본값 | 설명 |
|------|--------|------|
| level | 1 | 1~3 |
| charPr | HEADING_DEFAULTS[level]["charPr"] | 오버라이드 가능 |
| paraPr | HEADING_DEFAULTS[level]["paraPr"] | 오버라이드 가능 |

HEADING_DEFAULTS: `1={size:20,bold,CENTER}`, `2={size:14,bold}`, `3={size:12,bold}`

### bullet

```json
{"type": "bullet", "text": "항목 내용"}
{"type": "bullet", "label": "▶", "text": "항목 내용"}
```

| 필드 | 기본값 | 설명 |
|------|--------|------|
| label | "•" | 앞 기호 |
| text | "" | 내용 |
| paraPr | 24 | 들여쓰기 |

### numbered

```json
{"type": "numbered", "num": 1, "text": "첫째 항목"}
{"type": "numbered", "num": 1, "style": "circle", "text": "항목"}
```

| style | prefix 형태 | NUMBERED_DEFAULTS paraPr |
|-------|------------|--------------------------|
| circle (기본) | ① ② ... | left:600 |
| dot | 1. 2. ... | left:1200 |
| dash | 1. (fallback) | left:1800 |
| roman | Ⅰ Ⅱ ... | left:600 (circle fallback) |
| kcup | □ 1. | left:600 (circle fallback) |

### indent

```json
{"type": "indent", "label": "○ 세부", "text": "내용"}
```

label이 있으면 `"label: text"`, 없으면 text만.

### note

```json
{"type": "note", "text": "주의사항"}
```

`"※ text"` 형태로 출력. charPr 기본값 11 (9pt).

### table

```json
{
  "type": "table",
  "rows": [["헤더1", "헤더2"], ["값1", "값2"]],
  "headerRows": 1,
  "colRatios": [1, 3]
}
```

| 필드 | 설명 |
|------|------|
| rows | 2D 배열. 셀에 str 또는 `{"text":..., "charPr":..., "paraPr":..., "runs":[...]}` |
| headerRows | 헤더 행 수 (기본 0) |
| colRatios | 열 너비 비율 (기본 균등분할) |
| colSpan | 셀별 열 병합 수 (rows와 동일 구조) |
| rowSpan | 셀별 행 병합 수 |
| charPr | 전체 셀 기본 글자 스타일 |
| paraPr | 전체 셀 기본 문단 스타일 |

### image

```json
{"type": "image", "src": "/path/to/img.png"}
{"type": "image", "src": "/path/img.png", "width": 80, "height": 60, "align": "center"}
```

| 필드 | 기본값 | 설명 |
|------|--------|------|
| src | (필수) | 절대 경로. PNG/JPEG/GIF/BMP |
| width | 본문폭 비율 | mm 단위 |
| height | 원본 비율 | mm 단위 |
| align | "left" | left/center/right |

### label_value

```json
{"type": "label_value", "pairs": [["작성일", "2026-03-30"], ["부서", "개발팀"]]}
```

2열 표로 자동 생성. 좌열=라벨, 우열=값.

### signature

```json
{"type": "signature", "lines": ["2026년 3월 30일", "기관명", "담당자명"]}
```

우측 정렬 서명 블록.

### pagebreak

```json
{"type": "pagebreak"}
```

강제 페이지 나누기.

### hyperlink

```json
{"type": "hyperlink", "url": "https://example.com", "text": "링크 텍스트"}
{"type": "hyperlink", "url": "https://example.com", "prefix": "참고: ", "suffix": " 참조"}
```

XML 구조: `hp:fieldBegin type="HYPERLINK"` + parameters + display run + `hp:fieldEnd`

### text_footnote / text_endnote

```json
{"type": "text_footnote", "text": "본문 텍스트", "footnote": "각주 내용"}
{"type": "text_endnote", "text": "본문 텍스트", "endnote": "미주 내용"}
```

각주는 페이지 하단, 미주는 문서 끝. 번호 자동 증가.

### textbox

```json
{
  "type": "textbox", "text": "글상자 내용",
  "width": 100, "height": 30,
  "bg_color": "#E8F0FE", "border_color": "#1A73E8",
  "text_align": "center"
}
```

| 필드 | 기본값 | 설명 |
|------|--------|------|
| text | (필수) | 단일 텍스트 또는 `lines` 배열 |
| width | 본문폭 | mm |
| height | 30 | mm |
| bg_color | #FFFFFF | 배경색 |
| border_color | #000000 | 테두리색 |
| border_width | "0.12 mm" | 테두리 두께 |
| text_align | center | top/center/bottom |

### caption

```json
{"type": "caption", "label": "그림", "num": 1, "text": "도형 설명"}
```

출력: `"그림 1. 도형 설명"`. styleIDRef=22 (내장 캡션 스타일).

### bookmark

```json
{"type": "bookmark", "name": "section_intro", "text": "책갈피된 텍스트"}
```

XML: `hp:fieldBegin type="BOOKMARK"` + 텍스트 + `hp:fieldEnd`

### field

```json
{"type": "field", "field_type": "date", "format": "yyyy-MM-dd", "prefix": "작성일: "}
{"type": "field", "field_type": "page_number"}
{"type": "field", "field_type": "total_pages"}
```

---

## KCUP 전용 타입 (16개)

template=kcup에서 사용. 매핑 파일: `templates/kcup/mappings/{cost,ref3,mtg2}.json`

### kcup_box

```json
{"type": "kcup_box", "text": "항목 제목"}
```

`□ ` + 제목 (14pt 볼드 휴먼명조). 2-run.

### kcup_o

```json
{"type": "kcup_o", "keyword": "핵심 키워드", "text": "설명 내용"}
```

`o ` + 키워드(볼드) + ` ` + 본문. 4-run. hanging indent.

### kcup_o_plain

```json
{"type": "kcup_o_plain", "text": "o항목 본문만"}
```

`o ` + 본문(일반). 2-run.

### kcup_o_heading

```json
{"type": "kcup_o_heading", "text": "소제목"}
```

`o ` + 소제목(볼드). 2-run.

### kcup_dash

```json
{"type": "kcup_dash", "text": "세부 내용"}
{"type": "kcup_dash", "keyword": "키워드", "text": "내용"}
```

`- ` + 키워드(볼드, 있을 때) + 내용. hanging indent.

### kcup_dash_plain

```json
{"type": "kcup_dash_plain", "text": "항목 내용"}
```

`- ` + 내용(일반). 2-run.

### kcup_numbered

```json
{"type": "kcup_numbered", "number": 1, "text": "첫째 항목"}
```

`① ` + 내용 (CIRCLE_NUMS). 2-run.

### kcup_note

```json
{"type": "kcup_note", "text": "주의사항"}
```

9pt 소형 주석.

### kcup_attachment

```json
{"type": "kcup_attachment", "text": "붙임 내용"}
```

`붙임 ` + 내용. 2-run.

### kcup_pointer

```json
{"type": "kcup_pointer", "text": "가리킴 내용"}
```

`▶ ` + 내용.

### kcup_mixed_run

```json
{"type": "kcup_mixed_run", "runs": [
  {"text": "첫 run", "charPr": "body"},
  {"text": "볼드 run", "charPr": "bold"}
]}
```

runs 배열을 직접 지정. charPr에 KCUP_CP 역할명 문자열 또는 int 사용 가능.

### auto_spacing 간격줄 (4종)

자동 삽입 전용. JSON에 직접 넣어도 되지만 `"auto_spacing": true`로 자동 처리 권장.

| 타입 | 설명 |
|------|------|
| kcup_box_spacing | □항목 전 간격줄 (14pt, 160%) |
| kcup_o_spacing | o/dash항목 전 간격줄 (10pt, 100%) |
| kcup_o_heading_spacing | o_heading 전 간격줄 (14pt, 100%) |
| kcup_dash_spacing | -항목 전 간격줄 (10pt, 100%) |

### auto_spacing 전이 규칙

| 이전 블록 → 다음 블록 | 삽입 간격줄 |
|----------------------|------------|
| box → 아무 항목 | kcup_box_spacing |
| o/numbered → 다음 | kcup_o_spacing |
| dash → 다음 | kcup_o_spacing |
| o_heading → o_heading | kcup_o_heading_spacing |
