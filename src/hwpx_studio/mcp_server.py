#!/usr/bin/env python3
"""mcp-hwpx-studio — MCP 서버.

Claude/LLM에서 HWPX 문서 생성·읽기·편집·검증을 직접 호출할 수 있는
Model Context Protocol 서버.

Usage:
    # stdio 모드 (Claude Desktop / Claude Code 연동)
    python -m hwpx_studio.mcp_server

    # 또는 entry point
    hwpx-mcp
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ── 내부 모듈 임포트 ──────────────────────────────────────────────
try:
    from hwpx_studio.build_hwpx import build as build_hwpx
    from hwpx_studio.edit_document import HWPXEditor
    from hwpx_studio.read_document import HWPXReader
    from hwpx_studio.section_builder import build_xml, reset_image_registry
    from hwpx_studio.validate import validate
except ImportError:
    from build_hwpx import build as build_hwpx
    from edit_document import HWPXEditor
    from read_document import HWPXReader
    from section_builder import build_xml, reset_image_registry
    from validate import validate

# text_extract는 python-hwpx(hwpx) 의존성이 있어 선택적 임포트
_extract_plain = None
try:
    try:
        from hwpx_studio.text_extract import extract_plain as _extract_plain
    except ImportError:
        from text_extract import extract_plain as _extract_plain
except (ImportError, ModuleNotFoundError):
    pass  # hwpx 패키지 없으면 텍스트 추출 비활성화

# ── 서버 초기화 ───────────────────────────────────────────────────
mcp = FastMCP("hwpx-studio")


def _resolve_template_dir() -> Path:
    """템플릿 디렉토리 경로 해결."""
    here = Path(__file__).resolve().parent
    # 패키지 모드: src/hwpx_studio/templates/
    pkg = here / "templates"
    if pkg.is_dir():
        return pkg
    # 스킬 모드: scripts/../templates/
    skill = here.parent / "templates"
    if skill.is_dir():
        return skill
    return pkg  # fallback


# ── Tool 1: create ────────────────────────────────────────────────
@mcp.tool()
def hwpx_create(
    json_dsl: str,
    output_path: str,
    style: str = "report",
) -> str:
    """JSON DSL로 HWPX(한글) 문서를 생성합니다.

    Args:
        json_dsl: JSON 문자열. 아래 예시 참고.
        output_path: 생성할 HWPX 파일 경로 (예: /tmp/output.hwpx)
        style: 템플릿 — report(보고서), gonmun(공문서), kcup, minutes(회의록), proposal(제안서)

    예시 1 — 기본 보고서:
        {"blocks": [
            {"type": "heading", "level": 1, "text": "3분기 실적 보고"},
            {"type": "paragraph", "text": "2024년 3분기 매출은 전년 대비 15% 증가했습니다."},
            {"type": "table", "rows": [["구분","금액"],["매출","150억"],["영업이익","30억"]]},
            {"type": "bullet", "text": "신규 고객 200건 확보"},
            {"type": "numbered", "text": "다음 단계: 해외 진출 검토"}
        ]}

    예시 2 — 서식 지정:
        {"blocks": [
            {"type": "heading", "level": 1, "text": "제목", "charPr": {"bold": true}},
            {"type": "paragraph", "text": "강조 텍스트", "charPr": {"bold": true, "color": "#FF0000"}},
            {"type": "label_value", "label": "담당자", "value": "홍길동"}
        ]}

    전체 블록 타입: heading(level:1-3), paragraph, bullet, numbered, indent, note,
    table(rows 배열), pagebreak, signature, label_value, hyperlink(url), bookmark(name),
    footnote(text_footnote), image(path/base64), textbox, field_date, field_page
    """
    try:
        data = json.loads(json_dsl)
    except json.JSONDecodeError as e:
        return f"ERROR: JSON 파싱 실패 — {e}"

    try:
        reset_image_registry()
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        templates_dir = _resolve_template_dir()

        # section XML 생성
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
            section_tmp = Path(tmp.name)

        try:
            base_section = templates_dir / style / "section0.xml"
            base = base_section if base_section.exists() else None

            tree = build_xml(data, base_section_path=base, template=style)
            tree.write(str(section_tmp), xml_declaration=True, encoding="UTF-8", pretty_print=True)

            # HWPX 빌드
            build_hwpx(
                template=style,
                header_override=None,
                section_override=section_tmp,
                title=None,
                creator=None,
                output=out,
            )
        finally:
            section_tmp.unlink(missing_ok=True)

        # 생성 후 검증
        errors = validate(str(out))
        if errors:
            return f"WARNING: 파일 생성됨 ({out}) 하지만 검증 경고:\n" + "\n".join(f"  - {e}" for e in errors)
        return f"OK: {out} (style={style})"
    except Exception as e:
        return f"ERROR: 생성 실패 — {type(e).__name__}: {e}"


# ── Tool 2: read ──────────────────────────────────────────────────
@mcp.tool()
def hwpx_read(
    input_path: str,
    include_styles: bool = False,
) -> str:
    """HWPX 문서를 읽어 JSON으로 변환합니다. 라운드트립 지원(JSON→HWPX→JSON 보존).

    Args:
        input_path: HWPX 파일 경로.
        include_styles: True이면 charPr/paraPr 스타일 정보도 포함.

    Returns:
        {"blocks": [{"type": "heading", "text": "..."}, ...]} 형태의 JSON.
        35개 블록 타입 자동 감지. 이 JSON을 hwpx_create에 그대로 넘기면 동일 문서 재생성 가능.
    """
    path = Path(input_path)
    if not path.exists():
        return f"ERROR: 파일 없음 — {input_path}"

    try:
        reader = HWPXReader(str(path))
        reader.load()
        result = reader.to_json(include_styles=include_styles)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"ERROR: 읽기 실패 — {type(e).__name__}: {e}"


# ── Tool 3: edit ──────────────────────────────────────────────────
@mcp.tool()
def hwpx_edit(
    input_path: str,
    output_path: str,
    operations: str,
) -> str:
    """HWPX 문서를 편집합니다. 원본 서식/이미지/표 구조 완벽 보존.

    Args:
        input_path: 원본 HWPX 파일 경로.
        output_path: 편집된 HWPX 저장 경로.
        operations: JSON 배열 문자열. 예시:
            [
                {"op": "replace", "old": "2024년", "new": "2025년"},
                {"op": "replace_regex", "pattern": "\\d+월", "replacement": "3월"},
                {"op": "insert", "index": 0, "block": {"type": "paragraph", "text": "추가 문단"}},
                {"op": "delete", "index": 5}
            ]

    op 종류: replace(텍스트 치환), replace_regex(정규식), insert(블록 삽입), delete(블록 삭제)
    """
    if not Path(input_path).exists():
        return f"ERROR: 파일 없음 — {input_path}"

    try:
        ops = json.loads(operations)
    except json.JSONDecodeError as e:
        return f"ERROR: operations JSON 파싱 실패 — {e}"

    try:
        editor = HWPXEditor(input_path)
        editor.load()
        results = []

        for op_def in ops:
            op_type = op_def.get("op", "")
            if op_type == "replace":
                count = editor.replace_text(op_def["old"], op_def["new"])
                results.append(f"replace: {count}건 치환")
            elif op_type == "replace_regex":
                count = editor.replace_text(op_def["pattern"], op_def.get("replacement", ""), regex=True)
                results.append(f"replace_regex: {count}건 치환")
            elif op_type == "insert":
                idx = op_def.get("index", -1)
                editor.insert_block(idx, op_def["block"])
                results.append(f"insert: index={idx}")
            elif op_type == "delete":
                editor.delete_block(index=op_def["index"])
                results.append(f"delete: index={op_def['index']}")
            else:
                results.append(f"SKIP: 알 수 없는 op '{op_type}'")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        editor.save(output_path)
        return f"OK: {output_path}\n" + "\n".join(f"  [{i+1}] {r}" for i, r in enumerate(results))
    except Exception as e:
        return f"ERROR: 편집 실패 — {type(e).__name__}: {e}"


# ── Tool 4: validate ──────────────────────────────────────────────
@mcp.tool()
def hwpx_validate(input_path: str) -> str:
    """HWPX 파일의 구조적 무결성을 검증합니다.

    검사 항목: ZIP 아카이브, mimetype (첫 번째 엔트리 + ZIP_STORED),
    필수 파일(content.hpf, header.xml, section0.xml), XML 웰폼드.

    Args:
        input_path: 검증할 HWPX 파일 경로.

    Returns:
        "VALID" 또는 에러 목록.
    """
    path = Path(input_path)
    if not path.exists():
        return f"ERROR: 파일 없음 — {input_path}"

    try:
        errors = validate(str(path))
        if errors:
            return f"INVALID: {input_path}\n" + "\n".join(f"  - {e}" for e in errors)
        return f"VALID: {input_path} — 모든 구조 검사 통과"
    except Exception as e:
        return f"ERROR: 검증 실패 — {type(e).__name__}: {e}"


# ── Tool 5: extract_text ──────────────────────────────────────────
@mcp.tool()
def hwpx_extract_text(input_path: str) -> str:
    """HWPX 문서에서 텍스트만 추출합니다.

    Args:
        input_path: HWPX 파일 경로.

    Returns:
        추출된 텍스트 (줄바꿈 구분).
    """
    path = Path(input_path)
    if not path.exists():
        return f"ERROR: 파일 없음 — {input_path}"

    if _extract_plain is None:
        # fallback: read_document의 JSON에서 텍스트 추출
        try:
            reader = HWPXReader(str(path))
            reader.load()
            result = reader.to_json()
            blocks = result.get("blocks", [])
            if not blocks:
                for sec in result.get("sections", []):
                    blocks.extend(sec.get("blocks", []))
            texts = []
            for b in blocks:
                t = b.get("text", "")
                if t:
                    texts.append(t)
            return "\n".join(texts) if texts else "(빈 문서)"
        except Exception as e:
            return f"ERROR: 텍스트 추출 실패 — {type(e).__name__}: {e}"

    try:
        text = _extract_plain(str(path))
        return text if text.strip() else "(빈 문서)"
    except Exception as e:
        return f"ERROR: 텍스트 추출 실패 — {type(e).__name__}: {e}"


# ── Tool 6: preview ───────────────────────────────────────────────
@mcp.tool()
def hwpx_preview(
    input_path: str,
    output_path: str = "",
) -> str:
    """HWPX 문서를 HTML 미리보기로 변환합니다. 한컴오피스 없이 결과를 즉시 확인할 수 있습니다.

    Args:
        input_path: HWPX 파일 경로.
        output_path: 출력 HTML 파일 경로 (비어 있으면 input_path.html로 자동 생성).

    Returns:
        생성된 HTML 파일 경로, 또는 에러 메시지.
    """
    path = Path(input_path)
    if not path.exists():
        return f"ERROR: 파일 없음 — {input_path}"

    try:
        try:
            from hwpx_studio.html_preview import hwpx_to_html
        except ImportError:
            from html_preview import hwpx_to_html

        html = hwpx_to_html(str(path))

        if not output_path:
            output_path = str(path.with_suffix(".html"))

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        return f"OK: {out}"
    except Exception as e:
        return f"ERROR: 미리보기 생성 실패 — {type(e).__name__}: {e}"


# ── 진입점 ────────────────────────────────────────────────────────
def main():
    """stdio 모드로 MCP 서버 시작."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
