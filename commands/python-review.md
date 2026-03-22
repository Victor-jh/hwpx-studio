---
description: Python 코드 리뷰 실행
---

# /python-review

Invoke the **python-reviewer** agent to review recent Python changes.

## Steps

1. Run `git diff -- '*.py'` to identify changed files
2. Run `pytest tests/ -q` to verify tests pass
3. Check for CRITICAL/HIGH issues:
   - validate.py 호출 누락
   - 네임스페이스 불일치
   - 타입 힌트 누락
   - 보안 문제
4. Output review summary
