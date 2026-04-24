"""T03 — read_document.py 단위 테스트.

HWPX → JSON 역변환 결과의 구조와 정합성 검증.
자체 HWPX 생성으로 외부 샘플 의존 없이 동작.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parent.parent / "src" / "hwpx_studio"
READ_CMD = [sys.executable, str(SRC_DIR / "read_document.py")]
CREATE_CMD = [sys.executable, str(SRC_DIR / "create_document.py")]
SKILL_DIR = Path(__file__).resolve().parent.parent

# 외부 샘플 (있으면 추가 검증, 없으면 SKIP)
_sample_dir = SKILL_DIR / "test_outputs" / "hwpx"
SAMPLE_FILES = sorted(_sample_dir.glob("*.hwpx")) if _sample_dir.exists() else []


def _create_test_hwpx(tmp_dir: Path, name: str = "self_gen",
                      blocks: list | None = None) -> Path:
    """테스트용 HWPX를 자체 생성하여 반환."""
    if blocks is None:
        blocks = [
            {"type": "heading", "level": 1, "text": "자체생성 테스트"},
            {"type": "paragraph", "text": "read_document 단위테스트용 문서입니다."},
            {"type": "bullet", "text": "항목 A"},
            {"type": "table", "rows": [
                [{"text": "이름"}, {"text": "값"}],
                [{"text": "키"}, {"text": "180"}],
            ]},
        ]
    json_path = tmp_dir / f"{name}.json"
    json_path.write_text(
        json.dumps({"blocks": blocks}, ensure_ascii=False), encoding="utf-8")
    hwpx_path = tmp_dir / f"{name}.hwpx"
    result = subprocess.run(
        CREATE_CMD + [str(json_path), "-s", "report", "-o", str(hwpx_path)],
        capture_output=True, text=True, cwd=str(SRC_DIR),
    )
    assert result.returncode == 0, f"HWPX 생성 실패: {result.stderr}"
    assert hwpx_path.exists()
    return hwpx_path


# ── 기존 샘플 파일 전수 읽기 ──────────────────────────────────────

class TestReadExisting:
    """프로젝트 루트의 모든 .hwpx 파일을 read_document로 JSON 변환."""

    @pytest.mark.parametrize("hwpx_file", SAMPLE_FILES,
                             ids=[f.name for f in SAMPLE_FILES])
    def test_read_produces_valid_json(self, hwpx_file, tmp_dir):
        out = tmp_dir / f"{hwpx_file.stem}.json"
        result = subprocess.run(
            READ_CMD + [str(hwpx_file), "-o", str(out), "--pretty"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
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
            capture_output=True, text=True, cwd=str(SRC_DIR),
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
        """자체 생성 HWPX → stdout JSON 출력 검증."""
        sample = _create_test_hwpx(tmp_dir, "stdout_test")
        result = subprocess.run(
            READ_CMD + [str(sample)],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        assert result.returncode == 0, f"stdout 모드 실패: {result.stderr}"
        data = json.loads(result.stdout)
        assert "blocks" in data
        assert len(data["blocks"]) > 0

    def test_stdout_json_with_sample(self, tmp_dir):
        """외부 샘플이 있으면 추가 검증."""
        if not SAMPLE_FILES:
            pytest.skip("외부 샘플 없음")
        sample = min(SAMPLE_FILES, key=lambda f: f.stat().st_size)
        result = subprocess.run(
            READ_CMD + [str(sample)],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        assert result.returncode == 0, f"stdout 모드 실패: {result.stderr}"
        data = json.loads(result.stdout)
        assert "blocks" in data


# ── --include-styles 옵션 ─────────────────────────────────────────

class TestReadStyles:
    """--include-styles 시 _styles 필드 포함."""

    def test_include_styles(self, tmp_dir):
        """자체 생성 HWPX로 스타일 포함 출력 검증."""
        sample = _create_test_hwpx(tmp_dir, "style_test")
        out = tmp_dir / "styled.json"
        result = subprocess.run(
            READ_CMD + [str(sample), "-o", str(out), "--pretty", "--include-styles"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        assert result.returncode == 0, f"read 실패: {result.stderr}"
        data = json.loads(out.read_text(encoding="utf-8"))
        # _styles 필드가 존재하거나, 블록 내부에 스타일 정보가 있어야 함
        has_styles = "_styles" in data or any(
            "_styles" in b for b in data.get("blocks", [])
        )
        assert has_styles, "--include-styles 인데 스타일 정보 없음"

    def test_include_styles_with_sample(self, tmp_dir):
        """외부 샘플이 있으면 추가 스타일 검증."""
        if not SAMPLE_FILES:
            pytest.skip("외부 샘플 없음")
        sample = SAMPLE_FILES[0]
        out = tmp_dir / "styled_sample.json"
        result = subprocess.run(
            READ_CMD + [str(sample), "-o", str(out), "--pretty", "--include-styles"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        if result.returncode != 0:
            pytest.skip(f"read 실패: {result.stderr[:200]}")
        data = json.loads(out.read_text(encoding="utf-8"))
        has_styles = "_styles" in data or any(
            "_styles" in b for b in data.get("blocks", [])
        )
        assert has_styles, "--include-styles 인데 스타일 정보 없음"


# ── 자체 생성 HWPX 읽기 검증 ──────────────────────────────────────

class TestReadSelfGenerated:
    """외부 샘플 없이도 완전히 동작하는 읽기 테스트."""

    def test_read_paragraph(self, tmp_dir):
        hwpx = _create_test_hwpx(tmp_dir, "para", [
            {"type": "paragraph", "text": "단락 테스트"},
        ])
        out = tmp_dir / "para.json"
        result = subprocess.run(
            READ_CMD + [str(hwpx), "-o", str(out), "--pretty"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        assert result.returncode == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        # paragraph는 read 시 "text"로 매핑됨 (라운드트립 정상)
        assert any(b.get("type") in ("paragraph", "text") for b in data["blocks"])

    def test_read_heading(self, tmp_dir):
        hwpx = _create_test_hwpx(tmp_dir, "heading", [
            {"type": "heading", "level": 2, "text": "2단계 제목"},
        ])
        out = tmp_dir / "heading.json"
        result = subprocess.run(
            READ_CMD + [str(hwpx), "-o", str(out), "--pretty"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        assert result.returncode == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert len(data["blocks"]) > 0

    def test_read_table(self, tmp_dir):
        hwpx = _create_test_hwpx(tmp_dir, "table", [
            {"type": "table", "rows": [
                [{"text": "A"}, {"text": "B"}],
                [{"text": "C"}, {"text": "D"}],
            ]},
        ])
        out = tmp_dir / "table.json"
        result = subprocess.run(
            READ_CMD + [str(hwpx), "-o", str(out), "--pretty"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        assert result.returncode == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        tables = [b for b in data["blocks"] if b.get("type") == "table"]
        assert len(tables) >= 1

    def test_read_multi_block(self, tmp_dir):
        """다양한 블록 혼합 문서의 블록 수 보존."""
        blocks = [
            {"type": "heading", "level": 1, "text": "제목"},
            {"type": "paragraph", "text": "본문"},
            {"type": "bullet", "text": "글머리"},
            {"type": "numbered", "text": "번호"},
        ]
        hwpx = _create_test_hwpx(tmp_dir, "multi", blocks)
        out = tmp_dir / "multi.json"
        result = subprocess.run(
            READ_CMD + [str(hwpx), "-o", str(out), "--pretty"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        assert result.returncode == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert len(data["blocks"]) >= len(blocks)

    def test_all_blocks_have_type(self, tmp_dir):
        """자체 생성 문서의 모든 블록에 type 필드 존재."""
        hwpx = _create_test_hwpx(tmp_dir, "type_check")
        out = tmp_dir / "type_check.json"
        result = subprocess.run(
            READ_CMD + [str(hwpx), "-o", str(out), "--pretty"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        assert result.returncode == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        for i, block in enumerate(data["blocks"]):
            assert "type" in block, f"블록 [{i}]에 type 누락: {block}"

    def test_heading_roundtrip(self, tmp_dir):
        """heading 타입이 라운드트립에서 보존되는지 검증."""
        blocks = [
            {"type": "heading", "level": 1, "text": "1단계 제목"},
            {"type": "heading", "level": 2, "text": "2단계 제목"},
            {"type": "heading", "level": 3, "text": "3단계 제목"},
            {"type": "paragraph", "text": "일반 본문"},
        ]
        hwpx = _create_test_hwpx(tmp_dir, "heading_rt", blocks)
        result = subprocess.run(
            READ_CMD + [str(hwpx)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        headings = [b for b in data["blocks"]
                     if b.get("type") == "heading"]
        assert len(headings) == 3, (
            f"heading 3개 기대, {len(headings)}개 감지: "
            f"{[b.get('type') for b in data['blocks']]}")
        # level 보존 확인
        levels = [h["level"] for h in headings]
        assert levels == [1, 2, 3], f"level 불일치: {levels}"
        # paragraph가 heading으로 오감지되지 않는지
        texts = [b for b in data["blocks"]
                  if b.get("type") in ("text", "paragraph")]
        assert len(texts) >= 1, "paragraph가 사라짐"
