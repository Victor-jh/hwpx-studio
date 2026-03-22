"""T05 — edit_document.py 통합 테스트.

생성된 HWPX를 편집한 후 validate 통과 + 내용 변경 확인.
"""

import json
import subprocess
import sys
from pathlib import Path

from validate import validate

SRC_DIR = Path(__file__).resolve().parent.parent / "src" / "hwpx_studio"
CREATE_CMD = [sys.executable, str(SRC_DIR / "create_document.py")]
EDIT_CMD = [sys.executable, str(SRC_DIR / "edit_document.py")]
READ_CMD = [sys.executable, str(SRC_DIR / "read_document.py")]


def _create_sample(json_fixture, tmp_dir, name="sample.hwpx"):
    """헬퍼: JSON으로 샘플 HWPX 생성."""
    out = tmp_dir / name
    result = subprocess.run(
        CREATE_CMD + [str(json_fixture), "--style", "report", "-o", str(out)],
        capture_output=True, text=True, cwd=str(SRC_DIR),
    )
    assert result.returncode == 0, f"샘플 생성 실패: {result.stderr}"
    return out


# ── 텍스트 교체 ──────────────────────────────────────────────────

class TestEditReplace:

    def test_simple_replace(self, minimal_json, tmp_dir):
        """단순 텍스트 교체 후 validate + 내용 확인."""
        src = _create_sample(minimal_json, tmp_dir)
        edited = tmp_dir / "edited.hwpx"

        result = subprocess.run(
            EDIT_CMD + [str(src), "-o", str(edited),
                        "--replace", "테스트 문단입니다.", "수정된 문단입니다."],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        assert result.returncode == 0, f"edit 실패: {result.stderr}"

        # validate
        errors = validate(str(edited))
        assert errors == [], f"validate 실패: {errors}"

        # 내용 확인
        read_json = tmp_dir / "edited.json"
        subprocess.run(
            READ_CMD + [str(edited), "-o", str(read_json), "--pretty"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        data = json.loads(read_json.read_text(encoding="utf-8"))
        all_text = json.dumps(data, ensure_ascii=False)
        assert "수정된 문단" in all_text, "교체된 텍스트가 없음"
        assert "테스트 문단입니다." not in all_text, "원본 텍스트가 남아있음"

    def test_regex_replace(self, minimal_json, tmp_dir):
        """정규식 기반 교체."""
        src = _create_sample(minimal_json, tmp_dir)
        edited = tmp_dir / "regex_edited.hwpx"

        result = subprocess.run(
            EDIT_CMD + [str(src), "-o", str(edited),
                        "--replace", "테스트.*입니다", "정규식 교체 완료",
                        "--regex"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        assert result.returncode == 0, f"regex edit 실패: {result.stderr}"
        errors = validate(str(edited))
        assert errors == [], f"validate 실패: {errors}"


# ── 블록 삽입 ────────────────────────────────────────────────────

class TestEditInsert:

    def test_insert_text(self, minimal_json, tmp_dir):
        """텍스트 블록 삽입 후 validate + 블록 수 증가 확인."""
        src = _create_sample(minimal_json, tmp_dir)

        # 원본 블록 수
        orig_json = tmp_dir / "orig.json"
        subprocess.run(
            READ_CMD + [str(src), "-o", str(orig_json), "--pretty"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        orig_data = json.loads(orig_json.read_text(encoding="utf-8"))
        orig_count = len(orig_data["blocks"])

        # 삽입
        edited = tmp_dir / "inserted.hwpx"
        result = subprocess.run(
            EDIT_CMD + [str(src), "-o", str(edited),
                        "--insert-text", "0", "삽입된 새 텍스트"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        assert result.returncode == 0, f"insert 실패: {result.stderr}"
        errors = validate(str(edited))
        assert errors == [], f"validate 실패: {errors}"

        # 블록 수 확인
        new_json = tmp_dir / "inserted.json"
        subprocess.run(
            READ_CMD + [str(edited), "-o", str(new_json), "--pretty"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        new_data = json.loads(new_json.read_text(encoding="utf-8"))
        assert len(new_data["blocks"]) >= orig_count, \
            f"삽입 후 블록 수가 줄었음: {orig_count} → {len(new_data['blocks'])}"


# ── 블록 삭제 ────────────────────────────────────────────────────

class TestEditDelete:

    def test_delete_block(self, multi_block_json, tmp_dir):
        """블록 삭제 후 validate 통과."""
        src = _create_sample(multi_block_json, tmp_dir, "multi.hwpx")
        edited = tmp_dir / "deleted.hwpx"

        result = subprocess.run(
            EDIT_CMD + [str(src), "-o", str(edited), "--delete-block", "0"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        assert result.returncode == 0, f"delete 실패: {result.stderr}"
        errors = validate(str(edited))
        assert errors == [], f"validate 실패: {errors}"


# ── 편집 후 재편집 (편집 체이닝) ──────────────────────────────────

class TestEditChain:

    def test_replace_then_insert(self, minimal_json, tmp_dir):
        """교체 → 삽입 체이닝 후 validate."""
        src = _create_sample(minimal_json, tmp_dir)

        # 1차: 교체
        step1 = tmp_dir / "step1.hwpx"
        subprocess.run(
            EDIT_CMD + [str(src), "-o", str(step1),
                        "--replace", "테스트 문단입니다.", "1차 수정"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )

        # 2차: 삽입
        step2 = tmp_dir / "step2.hwpx"
        result = subprocess.run(
            EDIT_CMD + [str(step1), "-o", str(step2),
                        "--insert-text", "0", "추가된 문단"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        assert result.returncode == 0, f"체이닝 실패: {result.stderr}"
        errors = validate(str(step2))
        assert errors == [], f"체이닝 후 validate 실패: {errors}"
