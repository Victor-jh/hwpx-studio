# hwpx-studio

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.1.0-orange.svg)](CHANGELOG.md)

한컴오피스 HWPX 문서를 **생성 · 읽기 · 편집**하는 Python 라이브러리 + MCP 서버.

OWPML(KS X 6101) 표준 XML을 lxml + zipfile로 직접 조작합니다. 서드파티 HWP 라이브러리 의존 없이 charPr/paraPr 단위의 정밀한 서식 제어가 가능합니다.

```
JSON DSL ─→ section_builder ─→ section0.xml ─→ build_hwpx ─→ .hwpx
                                                                 │
.hwpx ─→ read_document ─→ JSON (라운드트립 지원)                  │
                                                                 │
.hwpx ─→ edit_document ─→ .hwpx (인플레이스 편집)                 │
                                                                 │
.hwpx ─→ validate + page_guard ─→ 이중 검증 게이트 ←─────────────┘
```

## 주요 기능

**생성**: JSON DSL로 블록을 정의하면 HWPX 문서가 나옵니다. 35개 블록 타입, 6개 템플릿(공문·보고서·회의록·제안서·KCUP 등), 동적 서식(PropertyRegistry)으로 인라인 스타일 지정.

**읽기**: HWPX → JSON 역변환. 35개 블록 타입 자동 감지, 머리말/꼬리말, 스타일 추출. 라운드트립(HWPX → JSON → HWPX) 블록 수/타입 100% 보존.

**편집**: ZIP 내부 XML 직접 수정. 텍스트 찾아 바꾸기(정규식), 블록 삽입/삭제, 머리말·꼬리말 변경. 원본 서식·이미지·표 구조 완벽 보존.

**MCP 서버**: Claude Desktop, Claude Code 등 LLM 도구에서 5개 tool(create, read, edit, validate, extract_text)로 직접 호출.

## 설치

```bash
# PyPI (라이브러리 + CLI)
pip install hwpx-studio

# MCP 서버 포함
pip install hwpx-studio[mcp]

# 개발 (테스트 포함)
pip install hwpx-studio[all]

# 소스에서
git clone https://github.com/Victor-jh/hwpx-studio.git
cd hwpx-studio
pip install -e ".[all]"
```

## 빠른 시작

### CLI

```bash
# 새 문서 생성
hwpx-create input.json -s report -o output.hwpx

# 문서 읽기 (HWPX → JSON)
hwpx-read document.hwpx --pretty -o output.json

# 문서 편집
hwpx-edit doc.hwpx --replace "원본" "수정" -o edited.hwpx

# 구조 검증
hwpx-validate output.hwpx
```

### Python API

```python
from hwpx_studio.read_document import HWPXReader
from hwpx_studio.edit_document import HWPXEditor
from hwpx_studio.validate import validate

# 읽기
reader = HWPXReader("document.hwpx")
reader.load()
data = reader.to_json(include_styles=True)

# 편집
editor = HWPXEditor("document.hwpx")
editor.load()
editor.replace_text("기존", "변경")
editor.save("edited.hwpx")

# 검증
errors = validate("output.hwpx")
```

### MCP 서버 (Claude Desktop)

`claude_desktop_config.json`에 추가:

```json
{
  "mcpServers": {
    "hwpx-studio": {
      "command": "hwpx-mcp"
    }
  }
}
```

제공되는 tool: `hwpx_create`, `hwpx_read`, `hwpx_edit`, `hwpx_validate`, `hwpx_extract_text`

### Agent Skill 모드

Claude Code, Cursor, Codex CLI에서 스킬 디렉토리에 넣으면 자동 활성화:

```bash
# Claude Code
cp -r hwpx-studio ~/.claude/skills/hwpx-studio

# Cursor
cp -r hwpx-studio ~/.cursor/skills/hwpx-studio
```

## JSON DSL 예시

```json
{
  "blocks": [
    {"type": "heading", "level": 1, "text": "분기 보고서"},
    {"type": "paragraph", "text": "2026년 1분기 실적을 요약합니다."},
    {"type": "table", "rows": [
      [{"text": "항목"}, {"text": "금액"}],
      [{"text": "매출"}, {"text": "1,200만원"}],
      [{"text": "영업이익"}, {"text": "340만원"}]
    ]},
    {"type": "bullet", "text": "전년 대비 12% 성장"},
    {"type": "image", "src": "chart.png", "width": 120}
  ],
  "header": {"text": "{{page}} / {{total_pages}}", "align": "right"},
  "footer": {"text": "기밀", "align": "center"}
}
```

35개 블록 타입을 지원합니다: heading, paragraph/text, bullet, numbered, indent, note, table, label_value, signature, empty, separator, pagebreak, hyperlink, footnote, endnote, textbox, caption, bookmark, field, image + KCUP 16종(kcup_box, kcup_o, kcup_dash, kcup_numbered 등).

## 템플릿

| 템플릿 | 용도 | 특징 |
|--------|------|------|
| base | 기본 골격 | 최소 스타일, 빈 문서 시작점 |
| gonmun | 공문서 | 기관명, 수신처, 시행일자, 연락처 |
| report | 보고서 | 섹션 헤더, 들여쓰기, 체크박스 |
| minutes | 회의록 | 섹션 라벨, 테두리 구분 |
| proposal | 제안서 | 색상 헤더, 번호 뱃지 |
| kcup | KCUP 보고서 | 독립 헤더, 20mm 여백, 전용 폰트 |

## 스크립트 / CLI

| CLI 명령 | 하는 일 |
|----------|---------|
| `hwpx-create` | JSON → HWPX 원커맨드 파이프라인 |
| `hwpx-read` | HWPX → JSON 역변환 (35개 블록 타입) |
| `hwpx-edit` | HWPX 인플레이스 편집 |
| `hwpx-validate` | HWPX 구조 검증 |
| `hwpx-build` | 템플릿 + XML → HWPX 조립 |
| `hwpx-section` | JSON → section0.xml 생성 |
| `hwpx-analyze` | 레퍼런스 HWPX 심층 분석 |
| `hwpx-extract` | 텍스트 추출 |
| `hwpx-diff` | 텍스트/구조 비교 |
| `hwpx-guard` | 페이지 드리프트 감지 |
| `hwpx-pack` | 디렉토리 → HWPX |
| `hwpx-unpack` | HWPX → 디렉토리 |
| `hwpx-mcp` | MCP 서버 (stdio) |

## kordoc 연동

hwpx-studio는 [kordoc](https://www.npmjs.com/package/kordoc)과 역할을 분리하여 병행 사용할 수 있습니다.

| 작업 | 담당 |
|------|------|
| HWPX 생성 (KCUP 보고서) | hwpx-studio |
| HWPX 편집 (텍스트 교체) | hwpx-studio |
| 기존 양식 필드 채우기 | kordoc fill_form |
| HWP/DOCX/PPTX/PDF 읽기 | kordoc parse_document |

## 개발

```bash
git clone https://github.com/Victor-jh/hwpx-studio.git
cd hwpx-studio
pip install -e ".[all]"

# 테스트
pytest tests/ -v

# 커버리지
pytest --cov=hwpx_studio --cov-report=term-missing tests/
```

## 요구사항

- Python 3.10+
- lxml >= 4.9
- (선택) mcp >= 1.0 — MCP 서버용

## 라이선스

MIT
