# Coding Style

## Immutability (CRITICAL)

ALWAYS create new XML elements, NEVER mutate existing ones:

```python
# WRONG: 기존 요소 직접 수정
element.text = "new"

# CORRECT: 새 요소 생성 후 교체
new_elem = etree.SubElement(parent, tag)
new_elem.text = "new"
```

## File Organization

- 200-400 lines typical, 800 max (section_builder.py는 예외 — 블록 핸들러 집합)
- Extract utilities from large modules
- Organize by feature/domain

## Error Handling

- Handle errors explicitly at every level
- Never silently swallow errors
- Validate all input before processing
- Fail fast with clear error messages

## Code Quality Checklist

Before marking work complete:
- [ ] Code is readable and well-named
- [ ] Functions are small (<50 lines)
- [ ] No deep nesting (>4 levels)
- [ ] Proper error handling
- [ ] No hardcoded values (use constants)
- [ ] validate.py 통과 확인
