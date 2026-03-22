---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Security

> Extends [common/security.md](../common/security.md)

## lxml Safety

lxml은 기본적으로 external entity 비활성화. 하지만:
```python
# WRONG — 외부 엔티티 허용
parser = etree.XMLParser(resolve_entities=True)

# CORRECT — 기본값 유지 (resolve_entities=False)
root = etree.fromstring(data)
```

## ZIP Handling

```python
# ALWAYS: mimetype는 ZIP_STORED
info = zf.getinfo("mimetype")
assert info.compress_type == ZIP_STORED
```

## Path Validation

사용자 입력 경로는 항상 검증:
```python
path = Path(user_input).resolve()
if ".." in path.parts:
    raise ValueError("Path traversal detected")
```
