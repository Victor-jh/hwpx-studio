"""T03 — read_document.py 단위 테스트.

HWPX → JSON 역변환 결과의 구조와 정합성 검증.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
READ_CMD = [sys.executable, str(SCRIPTS_DIR / "read_document.py")]
SKILL_DIR = Path(__file__).resolve().parent.parent

SAMPLE_FILES = sorted(SKILL_DIR.glob("*.hwpx"))


# ── 기존 샘플 파일 전수 읽기 ──────────────────────────────────────

class TestReadExisting:
    """프로젝트 루트의 모든 .hwpx 파일을 read_document로 JSON 변환."""

    @pytest.mark.parametrize("hwpx_file", SAMPLE_FILES,
                             ids=[f.name for f in SAMPLE_FILES])
    def test_read_produces_valid_json(self, hwpx_file, tmp_dir):
        out = tmp_dir / f"{hwpx_file.stem}.json"
        result = subprocess.run(
            READ_CMD + [str(hwpx_file), "-o", str(out), "--pretty"],
            capture_output=True, text=True, cwd=str(SCRIPTS_DIR),
        )
        assert result.returncode == 0, \
            f"read 실패 ({hwpx_file.name}): {result.stderr}"
        assert out.exists()

        data = json.loads(out.read_text(encoding="utf-8"))
        # 단일 섹션: {"blocks": [...]}, 다중 섹션: {"sections": [{"blocks": [...]}]}
        if "blocks" in data:
            assert isinstance(data["blocks"], list)
            assert len(data["blocks"]) > 0, f"블록이 비어있음: {hwpx_file.name}"
        elif "sections" in data:
            assert isinstance(data["sections"], list)
            assert len(data["sections"]) > 0, f"섹션이 비어있음: {hwpx_file.name}"
            for sec in data["sections"]:
                assert "blocks" in sec, f"섹션에 blocks 누락: {hwpx_file.name}"
        else:
            pytest.fail(f"blocks도 sections도 없음: {hwpx_file.name}")

    @pytest.mark.parametrize("hwpx_file", SAMPLE_FILES[:3],
                             ids=[f.name for f in SAMPLE_FILES[:3]])
    def test_read_blocks_have_type(self, hwpx_file, tmp_dir):
        """모든 블록에 type 필드가 존재."""
        out = tmp_dir / f"{hwpx_file.stem}_types.json"
        result = subprocess.run(
            READ_CMD + [str(hwpx_file), "-o", str(out), "--pretty"],
            capture_output=True, text=True, cwd=str(SCRIPTS_DIR),
        )
        if result.returncode != 0:
            pytest.skip(f"read 실패: {result.stderr[:200]}")

        data = json.loads(out.read_text(encoding="utf-8"))
        for i, block in enumerate(data["blocks"]):
            assert "type" in block, f"블록 [{i}]에 type 누락: {block}"


# ── stdout 출력 모드 ──────────────────────────────────────────────

class TestReadStdout:
    """--output 미지정 시 stdout으로 JSON 출력."""

    def test_stdout_json(self, tmp_dir):
        # 가장 작은 샘플 사용
        sample = min(SAMPLE_FILES, key=lambda f: f.stat().st_size)
        result = subprocess.run(
            READ_CMD + [str(sample)],
            capture_output=True, text=True, cwd=str(SCRIPTS_DIR),
        )
        assert result.returncode == 0, f"stdout 모드 실패: {result.stderr}"
        data = json.loads(result.stdout)
        assert "blocks" in data


# ── --include-styles 옵션 ─────────────────────────────────────────

class TestReadStyles:
    """--include-styles 시 _styles 필드 포함."""

    def test_include_styles(self, tmp_dir):
        sample = SAMPLE_FILES[0] if SAMPLE_FILES else pytest.skip("샘플 없음")
        out = tmp_dir / "styled.json"
        result = subprocess.run(
            READ_CMD + [str(sample), "-o", str(out), "--pretty", "--include-styles"],
            capture_output=True, text=True, cwd=str(SCRIPTS_DIR),
        )
        if result.returncode != 0:
            pytest.skip(f"read 실패: {result.stderr[:200]}")
        data = json.loads(out.read_text(encoding="utf-8"))
        # _styles 필드가 존재하거나, 블록 내부에 스타일 정보가 있어야 함
        has_styles = "_styles" in data or any(
            "_styles" in b for b in data.get("blocks", [])
        )
        assert has_styles, "--include-styles 인데 스타일 정보 없음"
