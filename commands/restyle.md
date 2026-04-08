---
name: restyle
description: "기존 문서에 다른 테마 적용"
---

# /restyle — 테마 재적용

기존 HWPX 문서를 다른 테마로 다시 생성합니다.

## 사용법

```
/restyle                         → 첨부된 hwpx + 테마 선택
/restyle --theme kait-standard   → 특정 테마로 변환
```

## 동작

1. 기존 문서를 `hwpx_read(resolve_styles=True)`로 분석
2. 내용은 유지하면서 새 테마의 서식/기호체계를 적용
3. `skills/style-writer/SKILL.md`의 워크플로우로 새 문서 생성
4. 충돌 해결: theme.yaml의 conflict_resolution 규칙을 따름
