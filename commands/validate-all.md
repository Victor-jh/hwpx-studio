---
description: 전체 프로젝트 검증 — 테스트 + 기존 샘플 + 코드 품질
---

# /validate-all

전체 프로젝트 무결성을 검증하는 명령.

## Steps

1. `pytest tests/ -v` — 160+ 테스트 전체 통과 확인
2. 프로젝트 루트의 모든 `.hwpx` 파일 validate 확인
3. `ruff check scripts/ src/` — 린팅
4. 미사용 import 확인
5. SKILL.md와 코드 일관성 검사
