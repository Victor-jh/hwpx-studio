---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Coding Style

> Extends [common/coding-style.md](../common/coding-style.md)

## Standards

- Follow **PEP 8** conventions
- Use **type annotations** on all function signatures
- Python 3.10+ features: `X | None` instead of `Optional[X]`

## Formatting

- **ruff** for linting + formatting (replaces black + isort + flake8)

## HWPX-Specific Patterns

```python
# 네임스페이스 상수 정의
HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"

# 네임스페이스 헬퍼
def _hp(tag: str) -> str:
    return f"{{{HP}}}{tag}"

# lxml 요소 생성 패턴
elem = etree.SubElement(parent, _hp("p"))
elem.set("id", str(idgen.next()))
```

## Import Order

1. stdlib (argparse, json, sys, ...)
2. third-party (lxml)
3. local (property_registry, section_builder)
