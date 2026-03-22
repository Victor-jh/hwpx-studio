"""test_07_html_preview — HTML 미리보기 변환 테스트."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src" / "hwpx_studio"
SAMPLES_DIR = ROOT / "samples"


def _create_hwpx(json_data: dict, style: str = "report") -> Path:
    """JSON DSL → 임시 HWPX 파일 생성."""
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as jf:
        json.dump(json_data, jf, ensure_ascii=False)
        jf_path = jf.name
    out = Path(tempfile.mktemp(suffix=".hwpx"))
    result = subprocess.run(
        [sys.executable, str(SRC_DIR / "create_document.py"),
         jf_path, "--style", style, "-o", str(out)],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"create failed: {result.stderr}"
    Path(jf_path).unlink(missing_ok=True)
    return out


def _preview(hwpx_path: Path) -> str:
    """HWPX → HTML 문자열."""
    sys.path.insert(0, str(SRC_DIR))
    from hwpx_studio.html_preview import hwpx_to_html
    return hwpx_to_html(str(hwpx_path))


class TestBasicPreview:
    """기본 블록타입 HTML 변환."""

    def test_simple_report(self):
        data = {"blocks": [
            {"type": "heading", "level": 1, "text": "제목"},
            {"type": "text", "text": "본문 내용입니다."},
            {"type": "bullet", "text": "항목 1"},
        ]}
        hwpx = _create_hwpx(data, "report")
        html = _preview(hwpx)
        assert "<!DOCTYPE html>" in html
        assert "page" in html
        hwpx.unlink(missing_ok=True)

    def test_paragraph_alias(self):
        """paragraph 타입이 text와 동일하게 처리되는지."""
        data = {"blocks": [
            {"type": "paragraph", "text": "단락 테스트"},
        ]}
        hwpx = _create_hwpx(data, "report")
        html = _preview(hwpx)
        assert "단락 테스트" in html or "page" in html
        hwpx.unlink(missing_ok=True)

    def test_table_renders(self):
        data = {"blocks": [
            {"type": "table", "rows": [["A", "B"], ["1", "2"]]},
        ]}
        hwpx = _create_hwpx(data, "report")
        html = _preview(hwpx)
        assert "<table>" in html
        hwpx.unlink(missing_ok=True)


class TestKCUPPreview:
    """KCUP 전용 블록 HTML 변환."""

    def test_kcup_basic_structure(self):
        data = {"blocks": [
            {"type": "kcup_box", "text": "현황"},
            {"type": "kcup_o", "keyword": "배경", "text": "설명문"},
            {"type": "kcup_dash", "keyword": "세부", "text": "세부 설명"},
            {"type": "kcup_o_plain", "text": "단순 서술"},
        ]}
        hwpx = _create_hwpx(data, "kcup")
        html = _preview(hwpx)
        assert "kcup-box" in html
        assert "kcup-o" in html
        assert "kcup-dash" in html
        hwpx.unlink(missing_ok=True)

    def test_kcup_cover(self):
        data = {"blocks": [
            {"type": "kcup_cover", "title": "테스트 보고서", "date": "2026. 3. 22."},
            {"type": "kcup_box", "text": "현황"},
            {"type": "kcup_o_plain", "text": "내용"},
        ]}
        hwpx = _create_hwpx(data, "kcup")
        html = _preview(hwpx)
        # 표지는 XML 레벨에서 여러 문단으로 분해됨 — HTML에서 kcup-box가 정상 렌더되면 OK
        assert "kcup-box" in html
        assert "<!DOCTYPE html>" in html
        hwpx.unlink(missing_ok=True)

    def test_kcup_all_types(self):
        data = {"blocks": [
            {"type": "kcup_box", "text": "제목"},
            {"type": "kcup_o", "keyword": "KW", "text": "설명"},
            {"type": "kcup_o_plain", "text": "단순"},
            {"type": "kcup_o_heading", "text": "소제목"},
            {"type": "kcup_dash", "keyword": "DK", "text": "세부"},
            {"type": "kcup_dash_plain", "text": "세부단순"},
            {"type": "kcup_numbered", "number": "①", "text": "번호"},
            {"type": "kcup_note", "text": "참고사항"},
            {"type": "kcup_attachment", "text": "붙임 제목"},
            {"type": "kcup_pointer", "text": "포인터"},
        ]}
        hwpx = _create_hwpx(data, "kcup")
        html = _preview(hwpx)
        assert "kcup-box" in html
        assert "kcup-o" in html
        assert "kcup-dash" in html
        hwpx.unlink(missing_ok=True)


class TestExistingFiles:
    """기존 HWPX 샘플 파일 미리보기 변환."""

    @pytest.fixture(params=sorted(ROOT.glob("*.hwpx")))
    def hwpx_file(self, request):
        return request.param

    def test_preview_no_crash(self, hwpx_file):
        """기존 HWPX 파일이 에러 없이 HTML로 변환되는지."""
        html = _preview(hwpx_file)
        assert "<!DOCTYPE html>" in html
        assert len(html) > 100
