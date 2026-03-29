---
name: hwpx-create
description: "JSON 블록 정의나 자연어 설명으로 한글(HWPX) 문서를 생성합니다."
argument-hint: "[json-file-or-description]"
allowed-tools: Read, Write, Bash
---

# /hwpx-create 커맨드

주어진 JSON 파일 경로 또는 자연어 설명을 기반으로 HWPX 문서를 생성한다.

## 실행 흐름

1. **인자 분석**: `$ARGUMENTS`가 `.json` 파일 경로이면 해당 파일을 읽는다. 자연어 설명이면 아래 JSON DSL로 변환한다.

2. **JSON DSL 구성**: 아래 블록 타입을 활용해 문서 구조를 작성한다.
   - `heading1/2/3`, `paragraph`, `table`, `image`, `pagebreak`
   - `list_item`, `hr`, `footer_text`, `header_text` 등 35개 블록 타입
   - 템플릿: `base`, `gonmun`(공문서), `report`, `minutes`, `proposal`, `kcup`

3. **문서 생성**: `skills/hwpx/scripts/create_document.py`를 호출한다.

```bash
cd skills/hwpx/scripts && python create_document.py \
  --input <json-file> \
  --template <template-name> \
  --output <output.hwpx>
```

4. **검증**: `validate.py`로 생성된 HWPX를 검증한다.

```bash
python validate.py <output.hwpx>
```

5. 결과 경로를 사용자에게 알린다.

## JSON DSL 예시

```json
{
  "template": "report",
  "meta": {
    "title": "업무 보고서",
    "author": "홍길동"
  },
  "blocks": [
    {"type": "heading1", "text": "1. 개요"},
    {"type": "paragraph", "text": "본 보고서는 ..."},
    {
      "type": "table",
      "rows": [
        ["항목", "내용"],
        ["날짜", "2026-03-29"]
      ]
    }
  ]
}
```

## 스크립트 경로

스크립트는 플러그인의 `skills/hwpx/scripts/` 디렉토리에 위치한다.
`SKILL.md`의 생성 경로 섹션을 함께 참조한다.
