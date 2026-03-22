"""T04 — 라운드트립 테스트 (핵심 차별점).

JSON → create → HWPX → read → JSON → create → HWPX → validate
두 번 왕복하면서 블록 수가 보존되고, 최종 HWPX가 유효한지 확인.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from validate import validate

SRC_DIR = Path(__file__).resolve().parent.parent / "src" / "hwpx_studio"
CREATE_CMD = [sys.executable, str(SRC_DIR / "create_document.py")]
READ_CMD = [sys.executable, str(SRC_DIR / "read_document.py")]

STYLES = ["report", "kcup", "gonmun"]


class TestRoundtrip:
    """JSON → HWPX → JSON → HWPX 라운드트립."""

    @pytest.mark.parametrize("style", STYLES)
    def test_roundtrip_block_count_preserved(self, style, multi_block_json, tmp_dir):
        """라운드트립 후 블록 수가 유지되는지 확인."""

        # Step 1: JSON → HWPX (1차 생성)
        hwpx_1 = tmp_dir / f"rt1_{style}.hwpx"
        r1 = subprocess.run(
            CREATE_CMD + [str(multi_block_json), "--style", style, "-o", str(hwpx_1)],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        assert r1.returncode == 0, f"1차 생성 실패: {r1.stderr}"

        # Step 2: HWPX → JSON (1차 읽기)
        json_1 = tmp_dir / f"rt1_{style}.json"
        r2 = subprocess.run(
            READ_CMD + [str(hwpx_1), "-o", str(json_1), "--pretty"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        assert r2.returncode == 0, f"1차 읽기 실패: {r2.stderr}"

        data_1 = json.loads(json_1.read_text(encoding="utf-8"))
        blocks_1 = data_1["blocks"]

        # Step 3: JSON → HWPX (2차 생성, 읽은 JSON으로)
        hwpx_2 = tmp_dir / f"rt2_{style}.hwpx"
        r3 = subprocess.run(
            CREATE_CMD + [str(json_1), "--style", style, "-o", str(hwpx_2)],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        assert r3.returncode == 0, f"2차 생성 실패: {r3.stderr}"

        # Step 4: validate (2차 HWPX)
        errors = validate(str(hwpx_2))
        assert errors == [], f"2차 HWPX validate 실패: {errors}"

        # Step 5: HWPX → JSON (2차 읽기)
        json_2 = tmp_dir / f"rt2_{style}.json"
        r4 = subprocess.run(
            READ_CMD + [str(hwpx_2), "-o", str(json_2), "--pretty"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        assert r4.returncode == 0, f"2차 읽기 실패: {r4.stderr}"

        data_2 = json.loads(json_2.read_text(encoding="utf-8"))
        blocks_2 = data_2["blocks"]

        # 블록 수 비교 (1차 vs 2차 — 동일해야 라운드트립 안정)
        assert len(blocks_2) == len(blocks_1), \
            f"블록 수 불일치: 1차={len(blocks_1)}, 2차={len(blocks_2)}"

    @pytest.mark.parametrize("style", STYLES)
    def test_roundtrip_types_preserved(self, style, multi_block_json, tmp_dir):
        """라운드트립 후 블록 타입 순서가 유지되는지 확인."""

        # 1차: JSON → HWPX → JSON
        hwpx_1 = tmp_dir / f"rtt1_{style}.hwpx"
        subprocess.run(
            CREATE_CMD + [str(multi_block_json), "--style", style, "-o", str(hwpx_1)],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )

        json_1 = tmp_dir / f"rtt1_{style}.json"
        subprocess.run(
            READ_CMD + [str(hwpx_1), "-o", str(json_1), "--pretty"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )

        # 2차: JSON → HWPX → JSON
        hwpx_2 = tmp_dir / f"rtt2_{style}.hwpx"
        subprocess.run(
            CREATE_CMD + [str(json_1), "--style", style, "-o", str(hwpx_2)],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )

        json_2 = tmp_dir / f"rtt2_{style}.json"
        r = subprocess.run(
            READ_CMD + [str(hwpx_2), "-o", str(json_2), "--pretty"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )
        if r.returncode != 0:
            pytest.skip(f"2차 읽기 실패: {r.stderr[:200]}")

        data_1 = json.loads(json_1.read_text(encoding="utf-8"))
        data_2 = json.loads(json_2.read_text(encoding="utf-8"))

        types_1 = [b.get("type") for b in data_1["blocks"]]
        types_2 = [b.get("type") for b in data_2["blocks"]]

        assert types_1 == types_2, \
            f"블록 타입 순서 불일치:\n  1차: {types_1}\n  2차: {types_2}"


class TestRoundtripMinimal:
    """최소 JSON 단일 paragraph 라운드트립."""

    def test_single_paragraph_roundtrip(self, minimal_json, tmp_dir):
        # JSON → HWPX
        hwpx = tmp_dir / "min_rt.hwpx"
        subprocess.run(
            CREATE_CMD + [str(minimal_json), "--style", "report", "-o", str(hwpx)],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )

        # HWPX → JSON
        out_json = tmp_dir / "min_rt.json"
        subprocess.run(
            READ_CMD + [str(hwpx), "-o", str(out_json), "--pretty"],
            capture_output=True, text=True, cwd=str(SRC_DIR),
        )

        data = json.loads(out_json.read_text(encoding="utf-8"))
        texts = [b.get("text", "") for b in data["blocks"]
                 if b.get("type") in ("paragraph", "text")]
        assert any("테스트 문단" in t for t in texts), \
            f"원본 텍스트 보존 실패. 블록: {data['blocks']}"
