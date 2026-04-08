---
name: write
description: "테마 기반 HWPX 문서 작성"
---

# /write — 문서 작성

테마 + 양식 + 컨텍스트를 조합하여 HWPX 문서를 생성합니다.

## 사용법

```
/write                           → 테마/양식 선택부터 시작
/write 현황 보고서                → 양식 자동 매칭
/write --theme kcup-ryu-yj       → 테마 지정
```

## 동작

1. `skills/style-writer/SKILL.md`를 읽고 워크플로우를 따릅니다.
2. 테마 선택 → 양식 선택 → 컨텍스트 확인 → 내용 구성 → HWPX 생성
