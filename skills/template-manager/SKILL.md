---
name: template-manager
description: "HWPX 양식(문서 골격) 관리 — 양식 CRUD. '양식 만들어', '양식 수정', '문서 구조', '템플릿' 언급 시 사용."
---

# 양식 관리 (Template Manager)

양식 = 문서 골격 (섹션 순서, 블록 배치). 테마와 독립.

## 양식 구조

```yaml
template:
  id: "status-report"
  name: "현황 보고서"
  description: "주간/월간 현황 보고"
  kcup_header: "ref3"         # hwpx_create의 header 매핑

  structure:
    - block: "cover"
      required: true
    - block: "section"
      default_title: "전체 현황 요약"
      contains: [text, table]
      guidance: "L2에서 주요 수치 요약"
    - block: "note"
      position: "end"

  file_naming: "YYMMDD {사업명} - {제목} v{X.X}.hwpx"
```

## 워크플로우

### 목록 조회
1. `hwpx_theme_list()` → templates 항목 확인

### 양식 생성
1. 사용자에게 문서 구조를 대화형으로 구성:
   - 표지 포함 여부
   - 섹션 제목과 순서
   - 각 섹션에 포함될 블록 유형 (text, table, image)
   - 붙임/참고 포함 여부
2. template.yaml 조합
3. `hwpx_theme_save(name, yaml, category="templates")` 저장

### 양식 수정
1. `hwpx_theme_get(name, category="templates")` 로 로드
2. 섹션 추가/삭제/순서변경
3. 저장

### block 유형

| block | 설명 |
|-------|------|
| cover | 표지 페이지 (제목, 날짜, 작성자) |
| section | 본문 섹션 (□ 제목 + 하위 블록) |
| note | ※ 참고사항 |
| attachment | 붙임 문서 목록 |
| table | 독립 데이터 표 |
| image | 이미지 첨부 |
| process_flow | 프로세스 플로우 (다열 화살표 표) |

### contains 유형

section 내부에 올 수 있는 블록 유형:
- text: ○/– 텍스트 항목
- table: 데이터 표
- image: 이미지 첨부
- mixed: 텍스트+표+이미지 혼합

## MCP 도구

| 도구 | 용도 |
|------|------|
| `hwpx_theme_list` | 양식 목록 (category="templates") |
| `hwpx_theme_get` | 양식 내용 조회 |
| `hwpx_theme_save` | 양식 생성/수정 |
| `hwpx_theme_delete` | 양식 삭제 |
