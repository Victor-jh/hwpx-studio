---
name: style-analyzer
description: "외부 문서 스타일 분석 — HWPX에서 기호체계/서식/양식/작성스타일을 추출하여 테마를 자동 생성. '이 문서 스타일 분석', '양식 추출', 샘플 hwpx + '이 스타일로' 언급 시 사용."
---

# 스타일 분석 (Style Analyzer)

외부 HWPX 문서에서 테마(기호체계+서식) + 양식(골격) + 컨텍스트(조직정보)를
자동 추출하여 yaml로 저장한다.

## 워크플로우

### STEP 1. 문서 읽기

```python
# resolve_styles=True로 실제 속성값까지 추출
result = hwpx_read(input_path=sample_path, resolve_styles=True)
```

### STEP 2. 기호 체계 식별 (Layer 1a)

블록 텍스트에서 기호 패턴을 매칭:

| 패턴 | 기호 체계 |
|------|----------|
| □/○/–/· | kcup |
| Ⅰ/1/가/1) | gov-official |
| 1./1.1/1.1.1 | numbered |
| ▪/▫/■ | bullet-square |

```python
markers = detect_marker_system(blocks)
# → {"system": "kcup", "L1": "□", "L2": "○", "L3": "–"}
```

### STEP 3. 시각 서식 추출 (Layer 1b)

resolve_styles=True의 charPr_resolved/paraPr_resolved에서:

```python
for block in blocks:
    cp = block.get("charPr_resolved", {})
    pp = block.get("paraPr_resolved", {})
    
    # L1 (□ 블록): size_pt, bold, font
    # L2 (○ 블록): size_pt, bold, font, margin.indent
    # spacing: 빈줄 블록의 size_pt, lineSpacing
```

결과:
```yaml
format:
  levels:
    L1: { font: "휴먼명조", size: 14, bold: true, indent: 0, lineHeight: 160 }
    L2: { font: "휴먼명조", size: 14, bold: false, indent: 3, lineHeight: 160 }
  spacing:
    L1: { size: 14, lineHeight: 160 }
```

### STEP 4. 문서 골격 추출 (Layer 2)

블록 순서에서 섹션 구조를 추론:

```python
sections = []
current_section = None
for block in blocks:
    if block["type"] in ("kcup_box", "heading"):
        # 새 섹션 시작
        current_section = {"title": block["text"], "contains": []}
        sections.append(current_section)
    elif block["type"] == "table":
        current_section["contains"].append("table")
    elif block["type"] == "image":
        current_section["contains"].append("image")
    else:
        if "text" not in current_section.get("contains", []):
            current_section["contains"].append("text")
```

### STEP 5. 작성 패턴 추론 (Layer 3)

텍스트 분석으로 작성 스타일 감지:

- 괄호 사용 빈도: `(키워드)` 패턴 카운트
- 키워드 공백 벌림: `"배  경"` 같은 이중 공백 감지
- ※ 위치: 독립 문단 vs 앞 블록 마지막 줄
- ①②③ 사용 여부

### STEP 6. 조직 정보 추출 (Context)

표지/머리말에서:
- 기관명
- 날짜 형식
- 팀/부서명

### STEP 7. 결과 저장

3개 yaml을 생성하여 저장:

```python
hwpx_theme_save(theme_name, theme_yaml, category="themes")
hwpx_theme_save(template_name, template_yaml, category="templates")
hwpx_theme_save(context_name, context_yaml, category="contexts")
```

### STEP 8. 사용자 확인

추출 결과를 요약하여 보여주고 수정/확정 선택:

```
[추출 결과]
  기호 체계: gov-official (Ⅰ/1/가)
  서식: 나눔고딕 12pt, 줄간격 150%
  양식: 5개 섹션 (개요/현황/분석/계획/기대효과)
  조직: KAIT (한국정보통신진흥협회)

이대로 저장할까요? 수정할 부분이 있으면 말씀해주세요.
```

## 분석 정밀도 참고

- 기호 체계: 텍스트 패턴으로 95%+ 정확도
- 글꼴/크기: resolve_styles로 정확한 값 반환
- 줄간격: paraPr_resolved.lineSpacing으로 정확
- 들여쓰기: paraPr_resolved.margin.intent로 정확 (HWPUNIT → mm 변환 필요)
- 빈줄 높이: 빈 블록의 charPr_resolved.size_pt로 추출
- 작성 스타일: 통계 기반 추론 (정확도 보통)

## MCP 도구

| 도구 | 용도 |
|------|------|
| `hwpx_read(resolve_styles=True)` | 문서 구조 + 실제 서식값 추출 |
| `hwpx_theme_save` | 추출된 테마/양식/컨텍스트 저장 |
| `hwpx_theme_list` | 기존 테마와 중복 확인 |
