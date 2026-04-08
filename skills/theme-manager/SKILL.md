---
name: theme-manager
description: "HWPX 테마 관리 — 테마(기호체계+시각서식+작성스타일) CRUD. '테마 만들어', '테마 수정', '테마 삭제', '테마 목록', '스타일 설정' 언급 시 사용."
---

# 테마 관리 (Theme Manager)

테마 = 기호체계(L1a) + 시각서식(L1b) + 작성스타일(L3) 번들.
테마를 생성/조회/수정/삭제하여 문서 스타일을 관리한다.

## 테마 구조

```yaml
theme:
  id: "테마-id"
  name: "표시명"

  # Layer 1a — 기호 체계
  markers:
    system: "kcup"         # kcup | gov-official | numbered
    L1: { marker: "□" }
    L2: { marker: "○" }
    L3: { marker: "–" }
    note: { marker: "※" }

  # Layer 1b — 시각 서식
  format:
    levels:
      L1: { font: "함초롬바탕", size: 14, bold: true, indent: 0, lineHeight: 160 }
      L2: { font: "함초롬바탕", size: 14, bold: false, indent: 3, lineHeight: 160 }
    spacing:
      L1: { size: 14, lineHeight: 160 }  # 빈줄 높이 = size × lineHeight / 100
      L2: { size: 10, lineHeight: 100 }
    table:
      header: { font: "함초롬바탕", size: 12, bold: true, bgColor: "D6E4F0" }

  # Layer 3 — 작성 스타일
  writing:
    parentheses:
      L2: "(키워드) + 서술"
    keyword_spacing: "2~3글자 공백 벌림"
    note_placement: "인라인 우선"
```

## 워크플로우

### 목록 조회
1. `hwpx_theme_list()` 호출
2. 등록된 테마/양식/컨텍스트 전체 표시

### 테마 생성
1. 사용자에게 3개 레이어를 순차 확인:
   - 기호 체계: kcup/gov-official/numbered 또는 커스텀
   - 시각 서식: 글꼴, 크기, 줄간격, 빈줄 높이
   - 작성 스타일: 괄호 패턴, 키워드 처리
2. theme.yaml 조합
3. `hwpx_theme_save(name, yaml, category="themes")` 호출

### 테마 수정
1. `hwpx_theme_get(name)` 로 기존 테마 로드
2. 사용자가 요청한 레이어만 변경
3. `hwpx_theme_save(name, updated_yaml)` 로 저장

### 테마 삭제
1. 사용자 확인 후 `hwpx_theme_delete(name)` 호출

### 테마 복제
1. `hwpx_theme_get(source)` 로 로드
2. id/name 변경 후 `hwpx_theme_save(new_name, yaml)` 저장

## theme.yaml → style_overrides 변환 규칙

style-writer가 문서 생성 시, theme.yaml의 format 섹션을 hwpx_create의
style_overrides 파라미터로 변환해야 한다:

```python
# theme.yaml format → style_overrides JSON
overrides = {
    "charPr": {
        "box":   {"size": L1.size, "bold": L1.bold, "font": L1.font},
        "body":  {"size": L2.size, "bold": L2.bold, "font": L2.font},
        "bold":  {"size": L2.size, "bold": True, "font": L2.font},
        "gap14": {"size": spacing.L1.size},
        "gap10": {"size": spacing.L2.size},
        "gap6":  {"size": spacing.L3.size},
    },
    "paraPr": {
        "box":  {"lineSpacing": L1.lineHeight, "indent": L1.indent * 283},
        "o":    {"lineSpacing": L2.lineHeight, "indent": L2.indent * 283},
        "dash": {"lineSpacing": L3.lineHeight, "indent": L3.indent * 283},
        "gap":  {"lineSpacing": spacing.L2.lineHeight},
    }
}
```

indent 단위: yaml은 mm, HWPX는 HWPUNIT (1mm ≈ 283).

## MCP 도구

| 도구 | 용도 |
|------|------|
| `hwpx_theme_list` | 등록된 테마/양식/컨텍스트 목록 |
| `hwpx_theme_get` | 특정 테마 내용 조회 |
| `hwpx_theme_save` | 테마 생성/수정 |
| `hwpx_theme_delete` | 테마 삭제 |
