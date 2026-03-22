# Security

## Mandatory Checks Before Commit

- [ ] No hardcoded credentials or API keys
- [ ] No `eval()` or `exec()` on untrusted input
- [ ] No `pickle.loads()` on untrusted data
- [ ] Subprocess calls use list args (not shell=True)
- [ ] File paths validated (no path traversal)
- [ ] XML parsing: no external entity expansion (lxml default safe)

## HWPX-Specific Security

- ZIP bomb 방지: 압축 해제 시 크기 제한
- mimetype 검증: `application/hwp+zip` 확인
- XML well-formedness 검증 필수
