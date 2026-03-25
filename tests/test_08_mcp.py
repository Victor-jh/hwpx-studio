"""test_08_mcp — MCP 서버 E2E 통합 테스트.

FastMCP.call_tool()을 사용하여 6개 MCP 도구를 실제 호출하고
JSON DSL → HWPX 생성 → 읽기 → 편집 → 검증 → 텍스트추출 → 미리보기
전체 파이프라인을 검증한다.
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT / "samples"


# ── Fixture: MCP 서버 인스턴스 ────────────────────────────────────

@pytest.fixture(scope="module")
def mcp_server():
    """hwpx-studio MCP 서버 인스턴스 (import-only, no stdio)."""
    import sys
    sys.path.insert(0, str(ROOT / "src" / "hwpx_studio"))
    from hwpx_studio.mcp_server import mcp
    return mcp


def _call(mcp_server, tool_name: str, arguments: dict) -> str:
    """MCP tool 동기 호출 헬퍼."""
    result = asyncio.get_event_loop().run_until_complete(
        mcp_server.call_tool(tool_name, arguments)
    )
    # FastMCP call_tool → (list[TextContent], dict) tuple
    if isinstance(result, tuple):
        content_list = result[0]
    else:
        content_list = result
    texts = [c.text for c in content_list if hasattr(c, "text")]
    return "\n".join(texts)


# ── Tool 목록 확인 ────────────────────────────────────────────────

class TestToolDiscovery:
    """MCP 서버에 등록된 도구 목록 확인."""

    def test_list_tools(self, mcp_server):
        tools = asyncio.get_event_loop().run_until_complete(
            mcp_server.list_tools()
        )
        names = {t.name for t in tools}
        expected = {"hwpx_create", "hwpx_read", "hwpx_edit",
                    "hwpx_validate", "hwpx_extract_text", "hwpx_preview"}
        assert expected.issubset(names), f"Missing tools: {expected - names}"

    def test_tool_descriptions(self, mcp_server):
        tools = asyncio.get_event_loop().run_until_complete(
            mcp_server.list_tools()
        )
        for tool in tools:
            assert tool.description, f"Tool {tool.name} has no description"
            assert len(tool.description) > 20, f"Tool {tool.name} description too short"


# ── Tool 1: create ────────────────────────────────────────────────

class TestCreate:
    """hwpx_create 도구 E2E 테스트."""

    def test_create_report(self, mcp_server, tmp_path):
        out = tmp_path / "report.hwpx"
        dsl = {"blocks": [
            {"type": "heading", "level": 1, "text": "MCP 테스트 보고서"},
            {"type": "text", "text": "MCP에서 생성된 문서입니다."},
            {"type": "bullet", "text": "항목 1"},
            {"type": "table", "rows": [["A", "B"], ["1", "2"]]},
        ]}
        result = _call(mcp_server, "hwpx_create", {
            "json_dsl": json.dumps(dsl, ensure_ascii=False),
            "output_path": str(out),
            "style": "report",
        })
        assert result.startswith("OK:"), f"Create failed: {result}"
        assert out.exists()
        assert out.stat().st_size > 1000

    def test_create_kcup(self, mcp_server, tmp_path):
        out = tmp_path / "kcup.hwpx"
        dsl = {"blocks": [
            {"type": "kcup_box", "text": "현황"},
            {"type": "kcup_o", "keyword": "배경", "text": "설명문"},
            {"type": "kcup_dash", "keyword": "세부", "text": "세부 내용"},
        ]}
        result = _call(mcp_server, "hwpx_create", {
            "json_dsl": json.dumps(dsl, ensure_ascii=False),
            "output_path": str(out),
            "style": "kcup",
        })
        assert result.startswith("OK:"), f"Create KCUP failed: {result}"
        assert out.exists()

    def test_create_kcup_with_cover(self, mcp_server, tmp_path):
        out = tmp_path / "kcup_cover.hwpx"
        dsl = {"blocks": [
            {"type": "kcup_cover", "title": "MCP 표지 테스트", "date": "2026. 3. 22."},
            {"type": "kcup_box", "text": "내용"},
            {"type": "kcup_o_plain", "text": "본문"},
        ]}
        result = _call(mcp_server, "hwpx_create", {
            "json_dsl": json.dumps(dsl, ensure_ascii=False),
            "output_path": str(out),
            "style": "kcup",
        })
        assert result.startswith("OK:"), f"Create KCUP cover failed: {result}"

    def test_create_invalid_json(self, mcp_server, tmp_path):
        result = _call(mcp_server, "hwpx_create", {
            "json_dsl": "{invalid json",
            "output_path": str(tmp_path / "bad.hwpx"),
        })
        assert "ERROR" in result

    def test_create_all_styles(self, mcp_server, tmp_path):
        """모든 스타일 템플릿으로 생성 가능한지 확인."""
        dsl = {"blocks": [
            {"type": "heading", "level": 1, "text": "스타일 테스트"},
            {"type": "text", "text": "본문"},
        ]}
        templates_dir = ROOT / "src" / "hwpx_studio" / "templates"
        if not templates_dir.exists():
            templates_dir = ROOT / "templates"
        styles = [d.name for d in templates_dir.iterdir() if d.is_dir() and d.name != "__pycache__"]
        for style in styles:
            out = tmp_path / f"{style}.hwpx"
            result = _call(mcp_server, "hwpx_create", {
                "json_dsl": json.dumps(dsl, ensure_ascii=False),
                "output_path": str(out),
                "style": style,
            })
            assert "ERROR" not in result or "WARNING" in result, \
                f"Style '{style}' create failed: {result}"


# ── Tool 2: read ──────────────────────────────────────────────────

class TestRead:
    """hwpx_read 도구 E2E 테스트."""

    def test_read_created_doc(self, mcp_server, tmp_path):
        """create → read 라운드트립."""
        out = tmp_path / "roundtrip.hwpx"
        dsl = {"blocks": [
            {"type": "heading", "level": 1, "text": "라운드트립 제목"},
            {"type": "text", "text": "라운드트립 본문"},
        ]}
        _call(mcp_server, "hwpx_create", {
            "json_dsl": json.dumps(dsl, ensure_ascii=False),
            "output_path": str(out),
            "style": "report",
        })
        result = _call(mcp_server, "hwpx_read", {
            "input_path": str(out),
        })
        data = json.loads(result)
        assert "blocks" in data
        texts = [b.get("text", "") for b in data["blocks"]]
        assert any("라운드트립 제목" in t for t in texts)
        assert any("라운드트립 본문" in t for t in texts)

    def test_read_with_styles(self, mcp_server, tmp_path):
        out = tmp_path / "styled.hwpx"
        dsl = {"blocks": [{"type": "text", "text": "스타일 포함 읽기"}]}
        _call(mcp_server, "hwpx_create", {
            "json_dsl": json.dumps(dsl, ensure_ascii=False),
            "output_path": str(out),
        })
        result = _call(mcp_server, "hwpx_read", {
            "input_path": str(out),
            "include_styles": True,
        })
        data = json.loads(result)
        assert "blocks" in data

    def test_read_nonexistent(self, mcp_server):
        result = _call(mcp_server, "hwpx_read", {
            "input_path": "/tmp/nonexistent_12345.hwpx",
        })
        assert "ERROR" in result

    @pytest.fixture(params=sorted((ROOT / "test_outputs" / "hwpx").glob("*.hwpx"))[:5])
    def sample_hwpx(self, request):
        return request.param

    def test_read_existing_samples(self, mcp_server, sample_hwpx):
        """기존 HWPX 샘플 파일 읽기."""
        result = _call(mcp_server, "hwpx_read", {
            "input_path": str(sample_hwpx),
        })
        assert "ERROR" not in result
        data = json.loads(result)
        assert "blocks" in data


# ── Tool 3: edit ──────────────────────────────────────────────────

class TestEdit:
    """hwpx_edit 도구 E2E 테스트."""

    def _make_doc(self, mcp_server, path: Path) -> Path:
        dsl = {"blocks": [
            {"type": "heading", "level": 1, "text": "편집 대상 문서"},
            {"type": "text", "text": "이 문장을 수정합니다. 원본 텍스트."},
            {"type": "bullet", "text": "항목 A"},
        ]}
        _call(mcp_server, "hwpx_create", {
            "json_dsl": json.dumps(dsl, ensure_ascii=False),
            "output_path": str(path),
            "style": "report",
        })
        return path

    def test_replace_text(self, mcp_server, tmp_path):
        src = self._make_doc(mcp_server, tmp_path / "src.hwpx")
        out = tmp_path / "edited.hwpx"
        ops = [{"op": "replace", "old": "원본 텍스트", "new": "수정된 텍스트"}]
        result = _call(mcp_server, "hwpx_edit", {
            "input_path": str(src),
            "output_path": str(out),
            "operations": json.dumps(ops, ensure_ascii=False),
        })
        assert result.startswith("OK:"), f"Edit failed: {result}"
        assert out.exists()
        # 읽어서 확인
        read_result = _call(mcp_server, "hwpx_read", {"input_path": str(out)})
        data = json.loads(read_result)
        all_text = " ".join(b.get("text", "") for b in data["blocks"])
        assert "수정된 텍스트" in all_text
        assert "원본 텍스트" not in all_text

    def test_replace_regex(self, mcp_server, tmp_path):
        src = self._make_doc(mcp_server, tmp_path / "regex_src.hwpx")
        out = tmp_path / "regex_edited.hwpx"
        ops = [{"op": "replace_regex", "pattern": r"항목\s+A", "replacement": "항목 Z"}]
        result = _call(mcp_server, "hwpx_edit", {
            "input_path": str(src),
            "output_path": str(out),
            "operations": json.dumps(ops, ensure_ascii=False),
        })
        assert result.startswith("OK:")

    def test_edit_invalid_operations(self, mcp_server, tmp_path):
        src = self._make_doc(mcp_server, tmp_path / "bad_ops.hwpx")
        result = _call(mcp_server, "hwpx_edit", {
            "input_path": str(src),
            "output_path": str(tmp_path / "out.hwpx"),
            "operations": "not json",
        })
        assert "ERROR" in result

    def test_edit_nonexistent(self, mcp_server, tmp_path):
        result = _call(mcp_server, "hwpx_edit", {
            "input_path": "/tmp/nonexistent_12345.hwpx",
            "output_path": str(tmp_path / "out.hwpx"),
            "operations": "[]",
        })
        assert "ERROR" in result


# ── Tool 4: validate ──────────────────────────────────────────────

class TestValidate:
    """hwpx_validate 도구 E2E 테스트."""

    def test_validate_good_doc(self, mcp_server, tmp_path):
        out = tmp_path / "valid.hwpx"
        dsl = {"blocks": [{"type": "text", "text": "유효한 문서"}]}
        _call(mcp_server, "hwpx_create", {
            "json_dsl": json.dumps(dsl, ensure_ascii=False),
            "output_path": str(out),
        })
        result = _call(mcp_server, "hwpx_validate", {
            "input_path": str(out),
        })
        assert "VALID" in result

    def test_validate_nonexistent(self, mcp_server):
        result = _call(mcp_server, "hwpx_validate", {
            "input_path": "/tmp/nonexistent_12345.hwpx",
        })
        assert "ERROR" in result

    def test_validate_bad_file(self, mcp_server, tmp_path):
        bad = tmp_path / "bad.hwpx"
        bad.write_text("this is not a zip file")
        result = _call(mcp_server, "hwpx_validate", {
            "input_path": str(bad),
        })
        assert "INVALID" in result or "ERROR" in result


# ── Tool 5: extract_text ──────────────────────────────────────────

class TestExtractText:
    """hwpx_extract_text 도구 E2E 테스트."""

    def test_extract_text_basic(self, mcp_server, tmp_path):
        out = tmp_path / "extract.hwpx"
        dsl = {"blocks": [
            {"type": "heading", "level": 1, "text": "추출 테스트 제목"},
            {"type": "text", "text": "추출 대상 본문입니다."},
        ]}
        _call(mcp_server, "hwpx_create", {
            "json_dsl": json.dumps(dsl, ensure_ascii=False),
            "output_path": str(out),
        })
        result = _call(mcp_server, "hwpx_extract_text", {
            "input_path": str(out),
        })
        assert "추출 테스트 제목" in result
        assert "추출 대상 본문" in result

    def test_extract_nonexistent(self, mcp_server):
        result = _call(mcp_server, "hwpx_extract_text", {
            "input_path": "/tmp/nonexistent_12345.hwpx",
        })
        assert "ERROR" in result


# ── Tool 6: preview ───────────────────────────────────────────────

class TestPreview:
    """hwpx_preview 도구 E2E 테스트."""

    def test_preview_basic(self, mcp_server, tmp_path):
        hwpx_out = tmp_path / "preview_src.hwpx"
        html_out = tmp_path / "preview.html"
        dsl = {"blocks": [
            {"type": "heading", "level": 1, "text": "미리보기 테스트"},
            {"type": "text", "text": "HTML로 변환됩니다."},
        ]}
        _call(mcp_server, "hwpx_create", {
            "json_dsl": json.dumps(dsl, ensure_ascii=False),
            "output_path": str(hwpx_out),
        })
        result = _call(mcp_server, "hwpx_preview", {
            "input_path": str(hwpx_out),
            "output_path": str(html_out),
        })
        assert result.startswith("OK:")
        assert html_out.exists()
        content = html_out.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    def test_preview_auto_path(self, mcp_server, tmp_path):
        """output_path 생략 시 자동 경로 생성."""
        hwpx_out = tmp_path / "auto_path.hwpx"
        dsl = {"blocks": [{"type": "text", "text": "자동경로"}]}
        _call(mcp_server, "hwpx_create", {
            "json_dsl": json.dumps(dsl, ensure_ascii=False),
            "output_path": str(hwpx_out),
        })
        result = _call(mcp_server, "hwpx_preview", {
            "input_path": str(hwpx_out),
        })
        assert result.startswith("OK:")
        auto_html = hwpx_out.with_suffix(".html")
        assert auto_html.exists()

    def test_preview_nonexistent(self, mcp_server):
        result = _call(mcp_server, "hwpx_preview", {
            "input_path": "/tmp/nonexistent_12345.hwpx",
        })
        assert "ERROR" in result

    def test_preview_kcup(self, mcp_server, tmp_path):
        """KCUP 스타일 문서 미리보기."""
        hwpx_out = tmp_path / "kcup_preview.hwpx"
        html_out = tmp_path / "kcup_preview.html"
        dsl = {"blocks": [
            {"type": "kcup_box", "text": "현황"},
            {"type": "kcup_o", "keyword": "KW", "text": "설명"},
            {"type": "kcup_dash", "keyword": "DK", "text": "세부"},
        ]}
        _call(mcp_server, "hwpx_create", {
            "json_dsl": json.dumps(dsl, ensure_ascii=False),
            "output_path": str(hwpx_out),
            "style": "kcup",
        })
        result = _call(mcp_server, "hwpx_preview", {
            "input_path": str(hwpx_out),
            "output_path": str(html_out),
        })
        assert result.startswith("OK:")
        content = html_out.read_text(encoding="utf-8")
        assert "kcup" in content.lower()


# ── 전체 파이프라인 E2E ───────────────────────────────────────────

class TestFullPipeline:
    """create → validate → read → edit → validate → extract → preview 전체 파이프라인."""

    def test_full_lifecycle(self, mcp_server, tmp_path):
        # 1. Create
        doc = tmp_path / "lifecycle.hwpx"
        dsl = {"blocks": [
            {"type": "heading", "level": 1, "text": "라이프사이클 테스트"},
            {"type": "text", "text": "원본 내용 ALPHA"},
            {"type": "bullet", "text": "항목 하나"},
        ]}
        r = _call(mcp_server, "hwpx_create", {
            "json_dsl": json.dumps(dsl, ensure_ascii=False),
            "output_path": str(doc),
            "style": "report",
        })
        assert r.startswith("OK:")

        # 2. Validate
        r = _call(mcp_server, "hwpx_validate", {"input_path": str(doc)})
        assert "VALID" in r

        # 3. Read
        r = _call(mcp_server, "hwpx_read", {"input_path": str(doc)})
        data = json.loads(r)
        assert len(data["blocks"]) >= 3

        # 4. Edit
        edited = tmp_path / "lifecycle_edited.hwpx"
        ops = [{"op": "replace", "old": "ALPHA", "new": "BETA"}]
        r = _call(mcp_server, "hwpx_edit", {
            "input_path": str(doc),
            "output_path": str(edited),
            "operations": json.dumps(ops),
        })
        assert r.startswith("OK:")

        # 5. Validate edited
        r = _call(mcp_server, "hwpx_validate", {"input_path": str(edited)})
        assert "VALID" in r

        # 6. Extract text
        r = _call(mcp_server, "hwpx_extract_text", {"input_path": str(edited)})
        assert "BETA" in r
        assert "ALPHA" not in r

        # 7. Preview
        html = tmp_path / "lifecycle.html"
        r = _call(mcp_server, "hwpx_preview", {
            "input_path": str(edited),
            "output_path": str(html),
        })
        assert r.startswith("OK:")
        assert html.exists()
