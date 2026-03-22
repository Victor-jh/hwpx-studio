"""T01 — validate.py 단위 테스트.

기존 HWPX 샘플 파일의 구조 검증 + 비정상 파일 거부 확인.
"""

import tempfile
import zipfile
from pathlib import Path

import pytest

from validate import validate

SKILL_DIR = Path(__file__).resolve().parent.parent
SAMPLE_FILES = sorted(SKILL_DIR.glob("*.hwpx"))


# ── 기존 샘플 파일 전수 검증 ──────────────────────────────────────

class TestExistingSamples:
    """프로젝트 루트의 모든 .hwpx 파일이 validate를 통과해야 한다."""

    @pytest.mark.parametrize("hwpx_file", SAMPLE_FILES,
                             ids=[f.name for f in SAMPLE_FILES])
    def test_existing_hwpx_valid(self, hwpx_file):
        errors = validate(str(hwpx_file))
        assert errors == [], f"{hwpx_file.name} 검증 실패: {errors}"


# ── 비정상 입력 거부 ──────────────────────────────────────────────

class TestInvalidInputs:

    def test_nonexistent_file(self, tmp_dir):
        errors = validate(str(tmp_dir / "없는파일.hwpx"))
        assert len(errors) == 1
        assert "File not found" in errors[0]

    def test_not_a_zip(self, tmp_dir):
        bad = tmp_dir / "bad.hwpx"
        bad.write_text("이것은 ZIP이 아닙니다")
        errors = validate(str(bad))
        assert any("Not a valid ZIP" in e for e in errors)

    def test_missing_mimetype(self, tmp_dir):
        """mimetype 파일이 없는 ZIP."""
        bad = tmp_dir / "no_mime.hwpx"
        with zipfile.ZipFile(bad, "w") as zf:
            zf.writestr("Contents/content.hpf", "<pkg/>")
        errors = validate(str(bad))
        assert any("Missing required file: mimetype" in e for e in errors)

    def test_wrong_mimetype_content(self, tmp_dir):
        """mimetype 값이 잘못된 경우."""
        bad = tmp_dir / "wrong_mime.hwpx"
        with zipfile.ZipFile(bad, "w") as zf:
            zf.writestr("mimetype", "application/wrong")
            zf.writestr("Contents/content.hpf", "<pkg/>")
            zf.writestr("Contents/header.xml", "<hdr/>")
            zf.writestr("Contents/section0.xml", "<sec/>")
        errors = validate(str(bad))
        assert any("Invalid mimetype" in e for e in errors)

    def test_malformed_xml(self, tmp_dir):
        """XML 구문 오류가 있는 파일."""
        bad = tmp_dir / "bad_xml.hwpx"
        with zipfile.ZipFile(bad, "w") as zf:
            zf.writestr("mimetype", "application/hwp+zip")
            zf.writestr("Contents/content.hpf", "<pkg>")  # 닫는 태그 없음
            zf.writestr("Contents/header.xml", "<hdr/>")
            zf.writestr("Contents/section0.xml", "<sec/>")
        errors = validate(str(bad))
        assert any("Malformed XML" in e for e in errors)
