# Testing Requirements

## Minimum Test Coverage: 80%

Test Types (ALL required):
1. **Unit Tests** — Individual functions, block handlers
2. **Integration Tests** — create → validate, edit → validate pipelines
3. **Roundtrip Tests** — JSON → HWPX → JSON → HWPX 블록 수/타입 보존

## Test-Driven Development

MANDATORY workflow for new features:
1. Write test first (RED)
2. Run test — it should FAIL
3. Write minimal implementation (GREEN)
4. Run test — it should PASS
5. Refactor (IMPROVE)
6. Verify: `pytest tests/ -v` ALL PASSED

## Validation Gate

모든 HWPX 생성/편집 테스트는 반드시:
- `validate.py` 통과
- 라운드트립 시 블록 수/타입 보존

## Agent Support

- **tdd-guide** — Use PROACTIVELY for new block types or script features
