---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Testing

> Extends [common/testing.md](../common/testing.md)

## Framework

Use **pytest** as the testing framework.

## Coverage

```bash
pytest --cov=scripts --cov-report=term-missing tests/
```

## Test Organization

```python
import pytest

class TestCreateValidate:
    """create → validate 통합 테스트."""

    @pytest.mark.parametrize("style", ["kcup", "gonmun", "report"])
    def test_create_with_style(self, style, minimal_json, tmp_dir):
        ...

class TestRoundtrip:
    """JSON → HWPX → JSON → HWPX 라운드트립."""
    ...
```

## Fixtures

공통 fixture는 `tests/conftest.py`에 정의:
- `minimal_json` — paragraph 1개
- `multi_block_json` — 다양한 블록 타입 조합
- `kcup_json` — KCUP 전용 블록
