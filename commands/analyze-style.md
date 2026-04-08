---
name: analyze-style
description: "HWPX 문서의 스타일 분석 및 테마 자동 추출"
---

# /analyze-style — 스타일 분석

HWPX 문서에서 기호체계, 서식, 양식, 작성스타일을 자동 추출하여
테마/양식/컨텍스트를 생성합니다.

## 사용법

```
/analyze-style                   → 첨부된 hwpx 파일 분석
/analyze-style /path/to/sample.hwpx → 경로 지정
```

## 동작

1. `skills/style-analyzer/SKILL.md`를 읽고 워크플로우를 따릅니다.
2. hwpx_read(resolve_styles=True)로 문서 구조 + 실제 서식값 추출
3. 기호체계/서식/양식/작성스타일/조직정보를 분석
4. 결과를 사용자에게 보여주고 확정 후 yaml 저장
