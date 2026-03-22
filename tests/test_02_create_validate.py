"""T02 — create_document.py → validate.py 통합 테스트.

JSON → HWPX 생성 후 validate 통과 확인.
각 스타일/템플릿, 다양한 블록 타입 조합.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from validate import validate

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
CREATE_CMD = [sys.executable, str(SCRIPTS_DIR / "create_document.py")]

STYLES = ["kcup", "gonmun", "report", "minutes", "proposal"]


# ── 스타일별 최소 생성 + 검증 ─────────────────────────────────────

class TestCreateMinimal:
    """각 스타일로 최소 JSON → HWPX 생성 후 validate 통과."""

    @pytest.mark.parametrize("style", STYLES)
    def test_create_with_style(self, style, minimal_json, tmp_dir):
        out = tmp_dir / f"{style}_minimal.hwpx"
        result = subprocess.run(
            CREATE_CMD + [str(minimal_json), "--style", style, "-o", str(out)],
            capture_output=True, text=True, cwd=str(SCRIPTS_DIR),
        )
        assert result.returncode == 0, f"create 실패 ({style}): {result.stderr}"
        assert out.exists(), f"출력 파일 없음: {out}"
        errors = validate(str(out))
        assert errors == [], f"validate 실패 ({style}): {errors}"

    def test_create_no_style_uses_report(self, minimal_json, tmp_dir):
        """스타일 미지정 시 report 템플릿으로 fallback."""
        out = tmp_dir / "report_minimal.hwpx"
        result = subprocess.run(
            CREATE_CMD + [str(minimal_json), "--template", "report", "-o", str(out)],
            capture_output=True, text=True, cwd=str(SCRIPTS_DIR),
        )
        assert result.returncode == 0, f"create 실패 (report): {result.stderr}"
        errors = validate(str(out))
        assert errors == [], f"validate 실패 (report): {errors}"


# ── 다양한 블록 타입 조합 ─────────────────────────────────────────

class TestCreateMultiBlock:
    """heading, bullet, numbered, table, note, indent, pagebreak 조합."""

    def test_multi_block_report(self, multi_block_json, tmp_dir):
        out = tmp_dir / "multi_report.hwpx"
        result = subprocess.run(
            CREATE_CMD + [str(multi_block_json), "--style", "report", "-o", str(out)],
            capture_output=True, text=True, cwd=str(SCRIPTS_DIR),
        )
        assert result.returncode == 0, f"create 실패: {result.stderr}"
        errors = validate(str(out))
        assert errors == [], f"validate 실패: {errors}"


class TestCreateSpecialBlocks:
    """하이퍼링크, 각주, 북마크, label_value 등 개별 블록 검증."""

    def test_hyperlink(self, hyperlink_json, tmp_dir):
        out = tmp_dir / "hyperlink.hwpx"
        result = subprocess.run(
            CREATE_CMD + [str(hyperlink_json), "--style", "report", "-o", str(out)],
            capture_output=True, text=True, cwd=str(SCRIPTS_DIR),
        )
        assert result.returncode == 0, f"create 실패: {result.stderr}"
        errors = validate(str(out))
        assert errors == [], f"validate 실패: {errors}"

    def test_footnote(self, footnote_json, tmp_dir):
        out = tmp_dir / "footnote.hwpx"
        result = subprocess.run(
            CREATE_CMD + [str(footnote_json), "--style", "report", "-o", str(out)],
            capture_output=True, text=True, cwd=str(SCRIPTS_DIR),
        )
        assert result.returncode == 0, f"create 실패: {result.stderr}"
        errors = validate(str(out))
        assert errors == [], f"validate 실패: {errors}"

    def test_bookmark(self, bookmark_json, tmp_dir):
        out = tmp_dir / "bookmark.hwpx"
        result = subprocess.run(
            CREATE_CMD + [str(bookmark_json), "--style", "report", "-o", str(out)],
            capture_output=True, text=True, cwd=str(SCRIPTS_DIR),
        )
        assert result.returncode == 0, f"create 실패: {result.stderr}"
        errors = validate(str(out))
        assert errors == [], f"validate 실패: {errors}"

    def test_label_value(self, label_value_json, tmp_dir):
        out = tmp_dir / "label_value.hwpx"
        result = subprocess.run(
            CREATE_CMD + [str(label_value_json), "--style", "report", "-o", str(out)],
            capture_output=True, text=True, cwd=str(SCRIPTS_DIR),
        )
        assert result.returncode == 0, f"create 실패: {result.stderr}"
        errors = validate(str(out))
        assert errors == [], f"validate 실패: {errors}"


# ── KCUP 전용 블록 ───────────────────────────────────────────────

class TestCreateKCUP:
    """KCUP 전용 블록 타입이 kcup 스타일에서 정상 생성."""

    def test_kcup_blocks(self, kcup_json, tmp_dir):
        out = tmp_dir / "kcup_test.hwpx"
        result = subprocess.run(
            CREATE_CMD + [str(kcup_json), "--style", "kcup", "-o", str(out)],
            capture_output=True, text=True, cwd=str(SCRIPTS_DIR),
        )
        assert result.returncode == 0, f"create 실패: {result.stderr}"
        errors = validate(str(out))
        assert errors == [], f"validate 실패: {errors}"
