# Git Workflow

## Commit Message Format
```
<type>: <description>

<optional body>
```

Types: feat, fix, refactor, docs, test, chore, perf

## Pull Request Workflow

1. Analyze full commit history (not just latest commit)
2. Use `git diff main...HEAD` to see all changes
3. Draft comprehensive PR summary
4. Include test plan with TODOs
5. Push with `-u` flag if new branch

## Before Commit

- [ ] `pytest tests/ -v` — ALL PASSED
- [ ] No unused imports
- [ ] SKILL.md와 코드 일관성 확인
