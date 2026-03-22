# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

**hwpx-studio** — 한글(HWPX) 문서 생성·읽기·편집 라이브러리 + MCP 서버 + Claude Skill.
OWPML(KS X 6101) 표준 기반, lxml + zipfile 직접 조작. 서드파티 HWP 라이브러리 사용 금지.

## Quick Start

```bash
# 패키지 설치 (개발 모드)
pip install -e ".[all]"

# 테스트 실행
pytest tests/ -v

# CLI 사용
hwpx-create input.json --style report -o output.hwpx
hwpx-read document.hwpx --pretty
hwpx-edit document.hwpx -o edited.hwpx --replace "old" "new"
hwpx-validate document.hwpx

# MCP 서버
hwpx-mcp
```

## Architecture

```
src/hwpx_studio/      # 단일 코드베이스 (패키지 + Skill + 직접 실행)
templates/            # HWPX 템플릿 (base, gonmun, kcup, report, minutes, proposal)
tests/                # pytest 테스트 (160개)
docs/                 # 공문서 작성 가이드, 예시
```

### Core Pipeline

```
JSON DSL → section_builder.py → section0.xml → build_hwpx.py → HWPX
                                                                  ↓
HWPX → read_document.py → JSON (라운드트립 지원)
                                                                  ↓
HWPX → edit_document.py → HWPX (인플레이스 편집)
                                                                  ↓
HWPX → validate.py + page_guard.py → 이중 검증 게이트
```

### 3 Core Paths (Decision Tree)

```python
if 사용자가_hwpx_첨부:
    if 의도 == "읽기":  → read_document.py
    elif 의도 == "편집": → edit_document.py (불가 시 unpack/pack)
    elif 의도 == "생성": → create_document.py (레퍼런스 모드)
    else:               → read_document.py (기본값)
else:
    → create_document.py (새 문서 모드)
```

### Key Modules (14개)

| Module | Purpose |
|--------|---------|
| create_document.py | JSON → HWPX 원커맨드 파이프라인 |
| read_document.py | HWPX → JSON 역변환 (35개 블록 타입) |
| edit_document.py | HWPX 인플레이스 편집 |
| section_builder.py | JSON → section0.xml (34개 블록 핸들러) |
| build_hwpx.py | 템플릿 + XML → HWPX 조립 |
| analyze_template.py | HWPX 심층 분석 (레퍼런스 기반 생성) |
| property_registry.py | 동적 charPr/paraPr/borderFill ID 할당 |
| validate.py | HWPX 구조 검증 |
| page_guard.py | 페이지 드리프트 위험 검사 |
| text_extract.py | HWPX 텍스트 추출 |
| diff_docs.py | 텍스트 + 구조 비교 |
| mcp_server.py | MCP 서버 (5개 tool: create/read/edit/validate/extract) |
| office/pack.py | 디렉토리 → HWPX |
| office/unpack.py | HWPX → 디렉토리 |

## Running Tests

```bash
# 전체 테스트
pytest tests/ -v

# 개별 테스트
pytest tests/test_01_validate.py -v          # validate 단위
pytest tests/test_04_roundtrip.py -v         # 라운드트립 핵심
pytest tests/test_06_section_builder.py -v   # 블록 타입 전수

# 커버리지
pytest --cov=hwpx_studio --cov-report=term-missing tests/
```

## Development Rules

- **Python 3.10+** required
- **lxml** only external dependency (no python-hwp, no pyhwp)
- **단일 코드베이스**: src/hwpx_studio/ 만 수정. 패키지/Skill/직접 실행 모두 여기서.
- **immutability**: XML 조작 시 원본 변경 금지, 항상 새 요소 생성
- **validate 필수**: 모든 HWPX 생성/편집 후 validate.py 통과 확인
- **page_guard 필수**: 레퍼런스 대비 페이지 드리프트 검사
- **HWPUNIT**: 1pt = 100, 1mm ≈ 283.5 (한컴 고유 단위)
- **라운드트립 보장**: read → create 파이프라인 블록 수/타입 보존

## Git Workflow

```
<type>: <description>

Types: feat, fix, refactor, docs, test, chore, perf
```

## Key Constraints

1. `.hwpx` only — binary `.hwp` 절대 불가
2. lxml + zipfile 직접 조작 — 서드파티 HWP 라이브러리 금지
3. mimetype는 ZIP 첫 번째 엔트리, ZIP_STORED (비압축)
4. UTF-8 인코딩 필수
5. OWPML 네임스페이스 정확히 유지
