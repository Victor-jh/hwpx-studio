# 스타일 가이드 — HEADING_DEFAULTS, NUMBERED_DEFAULTS, 템플릿별 스타일 맵

---

## HEADING_DEFAULTS (section_builder.py)

Phase 1에서 정적 ID → dict 기반으로 변경. PropertyRegistry가 자동 할당.

```python
HEADING_DEFAULTS = {
    1: {"charPr": {"size": 20, "bold": True}, "paraPr": {"align": "CENTER"}},
    2: {"charPr": {"size": 14, "bold": True}, "paraPr": {}},
    3: {"charPr": {"size": 12, "bold": True}, "paraPr": {}},
}
```

- level 1: 20pt 볼드 가운데 정렬
- level 2: 14pt 볼드
- level 3: 12pt 볼드

JSON에서 `"charPr"`/`"paraPr"` 필드로 오버라이드 가능.

---

## NUMBERED_DEFAULTS (section_builder.py)

```python
NUMBERED_DEFAULTS = {
    "circle": {"paraPr": {"left": 600},  "charPr": 0},
    "dot":    {"paraPr": {"left": 1200}, "charPr": 0},
    "dash":   {"paraPr": {"left": 1800}, "charPr": 0},
}
```

- `circle`: ①②③ — left 600 (약 2.1mm)
- `dot`: 1. 2. — left 1200 (약 4.2mm)
- `dash`: - 항목 — left 1800 (약 6.4mm)

`roman`/`kcup` style은 `circle` 폴백 적용.

---

## charPr dict 속성

| 키 | 타입 | 설명 | 단위 |
|----|------|------|------|
| size | int | 글자 크기 | pt (×100 = HWPUNIT) |
| bold | bool | 볼드 | — |
| italic | bool | 이탤릭 | — |
| underline | bool | 밑줄 | — |
| strikeout | bool | 취소선 | — |
| color | str | 글자색 | #RRGGBB |
| shadeColor | str | 음영색 | #RRGGBB |
| fontRef | int | 폰트 참조 ID | header.xml fontface id |
| spacing | int | 자간 | HWPUNIT |
| height | int | 글자 높이 (height 직접 지정) | HWPUNIT |

**폰트 참조** (base/gonmun/report/minutes/proposal):
- `fontRef=0` → 함초롬돋움 (고딕)
- `fontRef=1` → 함초롬바탕 (명조)

**폰트 참조** (kcup):
- `fontRef=0` → 함초롬돋움
- `fontRef=1` → 함초롬바탕
- `fontRef=2` → HY헤드라인M
- `fontRef=3` → 휴먼명조
- `fontRef=4` → 고도M

---

## paraPr dict 속성

| 키 | 타입 | 설명 | 단위 |
|----|------|------|------|
| align | str | 정렬 | JUSTIFY/LEFT/CENTER/RIGHT |
| lineSpacing | int | 줄간격 | % (예: 160 = 160%) |
| lineSpacingType | str | 줄간격 타입 | PERCENT/FIXED |
| left | int | 왼쪽 들여쓰기 | HWPUNIT |
| right | int | 오른쪽 들여쓰기 | HWPUNIT |
| indent | int | 첫줄 들여쓰기 (음수=내어쓰기) | HWPUNIT |
| prev | int | 문단 위 여백 | HWPUNIT |
| next | int | 문단 아래 여백 | HWPUNIT |
| borderFill | dict | 문단 배경색 | `{"bg": "#RRGGBB"}` |

**borderFill dict 키**:
- `bg`: 배경색 #RRGGBB
- `border`: 테두리 (all sides)
- `borderWidth`: 두께 문자열 (예: "0.12 mm")
- `borderColor`: 테두리색

---

## 템플릿별 스타일 ID 맵

### base

| ID | 유형 | 설명 |
|----|------|------|
| charPr 0 | 글자 | 10pt 함초롬바탕 기본 |
| charPr 1 | 글자 | 10pt 함초롬돋움 |
| charPr 2~6 | 글자 | Skeleton 기본 |
| paraPr 0 | 문단 | JUSTIFY, 160% |
| paraPr 1~19 | 문단 | Skeleton 기본 (개요, 각주 등) |
| borderFill 1 | 테두리 | 없음 (페이지 보더) |
| borderFill 2 | 테두리 | 없음 + 투명배경 |

### gonmun (공문) — base + 추가

| ID | 유형 | 설명 |
|----|------|------|
| charPr 7 | 글자 | 22pt 볼드 함초롬바탕 (기관명/제목) |
| charPr 8 | 글자 | 16pt 볼드 함초롬바탕 (서명자) |
| charPr 9 | 글자 | 8pt 함초롬바탕 (하단 연락처) |
| charPr 10 | 글자 | 10pt 볼드 함초롬바탕 (표 헤더) |
| paraPr 20 | 문단 | CENTER, 160% |
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
| charPr 10 | 글자 | 10pt 볼드+밑줄 (강조) |
| charPr 11 | 글자 | 9pt 함초롬바탕 (소형/각주) |
| charPr 12 | 글자 | 16pt 볼드 (1줄 제목) |
| charPr 13 | 글자 | 12pt 볼드 함초롬돋움 (섹션 헤더) |
| paraPr 20 | 문단 | CENTER, 160% |
| paraPr 21 | 문단 | CENTER, 130% (표 셀) |
| paraPr 22 | 문단 | JUSTIFY, 130% (표 셀) |
| paraPr 23 | 문단 | RIGHT 정렬, 160% |
| paraPr 24 | 문단 | JUSTIFY, left 600 (□ 들여쓰기) |
| paraPr 25 | 문단 | JUSTIFY, left 1200 (①②③ 들여쓰기) |
| paraPr 26 | 문단 | JUSTIFY, left 1800 (- 들여쓰기) |
| paraPr 27 | 문단 | LEFT, 상하단 테두리선 (섹션 헤더), prev 400 |
| borderFill 3 | 테두리 | SOLID 0.12mm 4면 |
| borderFill 4 | 테두리 | SOLID 0.12mm + #DAEEF3 배경 |
| borderFill 5 | 테두리 | 상단 0.4mm + 하단 0.12mm (섹션 헤더) |

### minutes (회의록) — base + 추가

| ID | 유형 | 설명 |
|----|------|------|
| charPr 7 | 글자 | 18pt 볼드 (제목) |
| charPr 8 | 글자 | 12pt 볼드 (섹션 라벨) |
| charPr 9 | 글자 | 10pt 볼드 (표 헤더) |
| paraPr 20~22 | 문단 | CENTER/JUSTIFY 변형 |
| borderFill 3 | 테두리 | SOLID 0.12mm 4면 |
| borderFill 4 | 테두리 | SOLID 0.12mm + #E2EFDA 배경 |

### proposal (제안서) — base + 추가

| ID | 유형 | 설명 |
|----|------|------|
| charPr 7 | 글자 | 20pt 볼드 (문서 제목) |
| charPr 8 | 글자 | 14pt 볼드 (소제목) |
| charPr 9 | 글자 | 10pt 볼드 (표 헤더) |
| charPr 10 | 글자 | 14pt 볼드 흰색 함초롬돋움 (대항목 번호, 녹색 배경) |
| charPr 11 | 글자 | 11pt 볼드 흰색 함초롬돋움 (소항목 번호, 파란 배경) |
| paraPr 20 | 문단 | CENTER, 160% |
| paraPr 21 | 문단 | CENTER, 130% (표 셀) |
| paraPr 22 | 문단 | JUSTIFY, 130% (표 셀) |
| borderFill 3 | 테두리 | SOLID 0.12mm 4면 |
| borderFill 4 | 테두리 | SOLID 0.12mm + #DAEEF3 배경 |
| borderFill 5 | 테두리 | 올리브녹색 #7B8B3D (대항목 번호 셀) |
| borderFill 6 | 테두리 | 연한 회색 #F2F2F2 + 회색 테두리 (대항목 제목 셀) |
| borderFill 7 | 테두리 | 파란색 #4472C4 (소항목 번호 배지) |
| borderFill 8 | 테두리 | 하단 테두리만 #D0D0D0 (소항목 제목 영역) |

### kcup — 독립 헤더 (본문폭 48190, 20mm 여백)

| ID | 유형 | 설명 |
|----|------|------|
| charPr 15 | 글자 | 19pt 볼드 HY헤드라인M (표지 제목) |
| charPr 16 | 글자 | 14pt 휴먼명조 (본문 body) |
| charPr 17 | 글자 | 14pt 볼드 휴먼명조 (키워드 bold) |
| charPr 18 | 글자 | 14pt 볼드 휴먼명조 (□항목 제목 box) |
| charPr 19 | 글자 | 14pt 휴먼명조 (간격줄 gap14) |
| charPr 20 | 글자 | 14pt 휴먼명조 (간격줄 alt gap14_alt) |
| charPr 21 | 글자 | 10pt 휴먼명조 (간격줄 gap10) |
| charPr 22 | 글자 | 14pt 휴먼명조 (대괄호/기호 bracket) |
| charPr 25 | 글자 | 12pt 고도M (sp_n4_12) |
| charPr 27 | 글자 | 고도M (sp_n3) |
| charPr 28 | 글자 | 12pt 고도M (sp_n1_12) |
| charPr 29 | 글자 | 고도M (sp_n1) |
| charPr 34 | 글자 | 고도M (sp_n4) |
| charPr 35 | 글자 | 고도M (sp_n5) |
| charPr 37 | 글자 | 고도M (sp_p3) |
| paraPr 26 | 문단 | JUSTIFY, indent=-2319 (o항목 hanging) |
| paraPr 28 | 문단 | JUSTIFY, left=252 (□항목) |
| paraPr 30 | 문단 | JUSTIFY, indent=-3103 (-항목 hanging) |
| paraPr 31 | 문단 | JUSTIFY, 100% 줄간격 (간격줄) |
| borderFill 3 | 테두리 | SOLID 테두리 |

**KCUP_CP 역할명 → charPr ID** (section_builder.py):
```python
KCUP_CP = {
    "cover_title": 15, "body": 16, "bold": 17, "box": 18,
    "gap14": 19, "gap14_alt": 20, "gap10": 21, "bracket": 22,
    "sp_n4_12": 25, "sp_n3": 27, "sp_n1_12": 28, "sp_n1": 29,
    "sp_n4": 34, "sp_n5": 35, "sp_p3": 37,
}
KCUP_PP = {"o": 26, "box": 28, "dash": 30, "gap": 31}
```
