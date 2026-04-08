---
name: style-writer
description: "테마+양식+컨텍스트를 조합하여 HWPX 문서 생성. '보고서 작성', '문서 만들어', '회의 자료', '현황 보고', 'hwpx 작성' 언급 시 사용."
---

# 문서 작성 (Style Writer)

핵심 스킬. 테마 + 양식 + 컨텍스트를 조합해서 실제 HWPX 문서를 생성한다.

## 워크플로우

### STEP 1. 테마 선택

```
등록된 테마가 있음?
├─ Yes → 목록 제시, 사용자 선택 (또는 기본 테마 자동 적용)
├─ "기존 테마로" 명시 → 해당 테마 바로 적용
├─ 샘플 문서 첨부 → style-analyzer 호출 → 테마 자동 생성
└─ 없음 → "테마부터 만들까요?" 안내 (theme-manager 연계)
```

### STEP 2. 양식 선택

```
요청에서 키워드 매칭:
  "현황 보고" → status-report
  "회의 자료" → meeting-material
  "제안서/기획안" → proposal

매칭 안 되면 → 등록된 양식 목록 제시
새 양식 필요 → template-manager 연계
```

### STEP 3. 컨텍스트 확인

- 기본값 (kcup) 자동 적용
- 외부 기관이면 contexts/에서 로드 또는 신규 등록

### STEP 4. 내용 구성

양식 골격(structure)에 따라 섹션별 내용을 생성:

1. 양식의 각 section에 대해 내용 요청/생성
2. 테마의 writing 규칙 적용:
   - 괄호 패턴: L2는 (키워드), L3은 괄호 없이
   - 키워드 공백 벌림: 2~3글자 → "배  경"
   - 번호 대체: 항목 5개+ → ①②③
   - ※ 배치: 인라인 우선 (inline: true)
3. JSON DSL 블록으로 변환

### STEP 5. HWPX 생성

```python
# 1. theme.yaml → style_overrides 변환
overrides = convert_theme_to_overrides(theme)

# 2. hwpx_create 호출
hwpx_create(
    json_dsl=json.dumps({"blocks": blocks, "auto_spacing": True}),
    output_path=file_path,
    style="kcup",
    style_overrides=json.dumps(overrides),
)

# 3. 미리보기
hwpx_preview(input_path=file_path)
```

### STEP 6. 검증 & 반복

1. 사용자에게 HWPX + HTML 미리보기 링크 제공
2. 피드백 → 버전 올려서 재생성 (v1.0 → v1.1)

## theme.yaml → style_overrides 변환

theme.yaml의 format 섹션에서 hwpx_create의 style_overrides를 생성:

```python
def convert_theme_to_overrides(theme: dict) -> dict:
    fmt = theme["theme"]["format"]
    levels = fmt["levels"]
    spacing = fmt.get("spacing", {})

    MM = 283  # 1mm ≈ 283 HWPUNIT

    overrides = {"charPr": {}, "paraPr": {}}

    # charPr 매핑
    L1 = levels.get("L1", {})
    L2 = levels.get("L2", {})
    L3 = levels.get("L3", {})

    overrides["charPr"]["box"]  = {"size": L1.get("size", 14), "bold": L1.get("bold", True), "font": L1.get("font", "함초롬바탕")}
    overrides["charPr"]["body"] = {"size": L2.get("size", 14), "bold": L2.get("bold", False), "font": L2.get("font", "함초롬바탕")}
    overrides["charPr"]["bold"] = {"size": L2.get("size", 14), "bold": True, "font": L2.get("font", "함초롬바탕")}

    # spacing charPr
    sp_L1 = spacing.get("L1", {})
    sp_L2 = spacing.get("L2", {})
    sp_L3 = spacing.get("L3", {})
    if sp_L1:
        overrides["charPr"]["gap14"] = {"size": sp_L1.get("size", 14)}
    if sp_L2:
        overrides["charPr"]["gap10"] = {"size": sp_L2.get("size", 10)}
    if sp_L3:
        overrides["charPr"]["gap6"] = {"size": sp_L3.get("size", 6)}

    # paraPr 매핑
    overrides["paraPr"]["box"]  = {"lineSpacing": L1.get("lineHeight", 160), "indent": int(L1.get("indent", 0) * MM)}
    overrides["paraPr"]["o"]    = {"lineSpacing": L2.get("lineHeight", 160), "indent": int(L2.get("indent", 3) * MM)}
    overrides["paraPr"]["dash"] = {"lineSpacing": L3.get("lineHeight", 160), "indent": int(L3.get("indent", 6) * MM)}

    return overrides
```

## JSON DSL 블록 매핑

| 기호 | 블록 타입 | 키워드 패턴 |
|------|----------|------------|
| □ | kcup_box | title만 |
| ○ (키워드) | kcup_o | keyword + text |
| ○ (단순) | kcup_o_plain | text만 |
| – (키워드) | kcup_dash | keyword + text |
| – (단순) | kcup_dash_plain | text만 |
| ※ (인라인) | kcup_note | inline: true |
| ※ (독립) | kcup_note | mode: "line" |
| ①②③ | kcup_numbered | num + text |
| ☞ | kcup_pointer | text |

## writing 규칙 적용 예시

### 괄호 패턴

```
L2 — 키워드가 있으면:
  ○ (처리현황) 총 25건 접수
L2 — 단순 나열이면:
  ○ 총 25건 접수

L3 — 기본 괄호 없음:
  – 검토 중 15건
L3 — 구분 필요 시만:
  – (미완료) 검토 중 15건
```

### 키워드 공백 벌림

```
2글자: "배  경" (공백 2개)
3글자: "기대효과" → "기 대 효 과" (각 글자 사이 공백 1개)
4글자+: 벌리지 않음
```

### 번호 대체

```
항목 5개 이상이면:
  ○ 항목1 → ① 항목1
  ○ 항목2 → ② 항목2
```

## 파일명 규칙

양식의 file_naming 패턴을 따름:
```
260408 이용자 참여 신고제 - 현황 보고 v1.0.hwpx
```

## 기존 스킬 연동

- violation-report, case-review 등 기존 스킬이 문서를 생성할 때,
  style-writer의 테마 규칙을 따르도록 SKILL.md에서 참조 지시.
- 직접 호출 체인 없이, "문서 생성 시 테마가 등록되어 있으면 해당 테마 적용" 규칙.
