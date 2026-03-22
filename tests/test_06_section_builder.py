"""T06 — section_builder.py 단위 테스트.

34개 블록 타입 핸들러(make_* 함수)가 valid XML을 생성하는지 개별 검증.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from lxml import etree

SRC_DIR = Path(__file__).resolve().parent.parent / "src" / "hwpx_studio"
SKILL_DIR = Path(__file__).resolve().parent.parent
SB_CMD = [sys.executable, str(SRC_DIR / "section_builder.py")]

# base section0.xml 경로 (secPr 복사용)
BASE_SECTION = SKILL_DIR / "templates" / "base" / "Contents" / "section0.xml"


def _build_section(blocks: list[dict], tmp_dir: Path, name: str = "test") -> Path:
    """헬퍼: blocks → section_builder → section0.xml 생성."""
    json_path = tmp_dir / f"{name}.json"
    json_path.write_text(
        json.dumps({"blocks": blocks}, ensure_ascii=False), encoding="utf-8"
    )
    out = tmp_dir / f"{name}_section0.xml"
    result = subprocess.run(
        SB_CMD + [str(json_path), "-o", str(out),
                  "--base-section", str(BASE_SECTION)],
        capture_output=True, text=True, cwd=str(SRC_DIR),
    )
    assert result.returncode == 0, f"section_builder 실패: {result.stderr}"
    assert out.exists()
    return out


def _parse_xml(path: Path) -> etree._Element:
    """XML 파싱 + well-formed 확인."""
    return etree.parse(str(path)).getroot()


# ── 공통 블록 타입 개별 테스트 ────────────────────────────────────

COMMON_BLOCKS = [
    ("paragraph", {"type": "paragraph", "text": "기본 문단"}),
    ("heading_1", {"type": "heading", "level": 1, "text": "제목 1"}),
    ("heading_2", {"type": "heading", "level": 2, "text": "제목 2"}),
    ("heading_3", {"type": "heading", "level": 3, "text": "제목 3"}),
    ("bullet", {"type": "bullet", "text": "글머리 항목"}),
    ("numbered", {"type": "numbered", "text": "번호 항목"}),
    ("indent", {"type": "indent", "text": "들여쓰기"}),
    ("note", {"type": "note", "text": "주의사항"}),
    ("pagebreak", {"type": "pagebreak"}),
    ("signature", {"type": "signature", "text": "서명란"}),
    ("label_value", {"type": "label_value", "label": "항목", "value": "값"}),
    ("hyperlink", {"type": "hyperlink", "text": "링크", "url": "https://example.com"}),
    ("bookmark", {"type": "bookmark", "name": "bm1", "text": "북마크"}),
    ("field_date", {"type": "field", "field_type": "date"}),
    ("field_page", {"type": "field", "field_type": "page_number"}),
    ("table_2x2", {"type": "table", "rows": [
        [{"text": "A"}, {"text": "B"}],
        [{"text": "C"}, {"text": "D"}],
    ]}),
]


class TestCommonBlocks:
    """공통 블록 타입이 각각 well-formed XML을 생성."""

    @pytest.mark.parametrize("name,block", COMMON_BLOCKS,
                             ids=[b[0] for b in COMMON_BLOCKS])
    def test_block_produces_valid_xml(self, name, block, tmp_dir):
        xml_path = _build_section([block], tmp_dir, name)
        root = _parse_xml(xml_path)
        # section 태그가 존재하고, 자식(paragraph)이 최소 1개
        assert len(root) >= 1, f"{name}: section에 자식 요소 없음"


class TestTableVariants:
    """테이블 변형: colRatios, 셀 병합, 다중 run."""

    def test_table_with_col_ratios(self, tmp_dir):
        block = {
            "type": "table",
            "colRatios": [30, 70],
            "rows": [
                [{"text": "좁은 열"}, {"text": "넓은 열"}],
            ],
        }
        xml_path = _build_section([block], tmp_dir, "col_ratios")
        _parse_xml(xml_path)  # well-formed 확인

    def test_table_with_merge(self, tmp_dir):
        block = {
            "type": "table",
            "rows": [
                [{"text": "병합", "colspan": 2}],
                [{"text": "A"}, {"text": "B"}],
            ],
        }
        xml_path = _build_section([block], tmp_dir, "merge")
        _parse_xml(xml_path)


# ── KCUP 블록 타입 개별 테스트 ────────────────────────────────────

KCUP_BLOCKS = [
    ("kcup_box", {"type": "kcup_box", "text": "박스"}),
    ("kcup_box_spacing", {"type": "kcup_box_spacing"}),
    ("kcup_o", {"type": "kcup_o", "text": "O항목"}),
    ("kcup_o_plain", {"type": "kcup_o_plain", "text": "O일반"}),
    ("kcup_o_heading", {"type": "kcup_o_heading", "text": "O제목"}),
    ("kcup_o_spacing", {"type": "kcup_o_spacing"}),
    ("kcup_o_heading_spacing", {"type": "kcup_o_heading_spacing"}),
    ("kcup_dash", {"type": "kcup_dash", "text": "대시"}),
    ("kcup_dash_plain", {"type": "kcup_dash_plain", "text": "대시일반"}),
    ("kcup_dash_spacing", {"type": "kcup_dash_spacing"}),
    ("kcup_numbered", {"type": "kcup_numbered", "number": "1", "text": "번호"}),
    ("kcup_note", {"type": "kcup_note", "text": "비고"}),
    ("kcup_attachment", {"type": "kcup_attachment", "text": "첨부"}),
    ("kcup_pointer", {"type": "kcup_pointer", "text": "포인터"}),
    ("kcup_mixed_run", {"type": "kcup_mixed_run", "runs": [
        {"text": "일반"}, {"text": "볼드", "bold": True}
    ]}),
]


class TestKCUPBlocks:
    """KCUP 전용 블록 타입이 각각 well-formed XML을 생성."""

    @pytest.mark.parametrize("name,block", KCUP_BLOCKS,
                             ids=[b[0] for b in KCUP_BLOCKS])
    def test_kcup_block_valid_xml(self, name, block, tmp_dir):
        xml_path = _build_section([block], tmp_dir, name)
        root = _parse_xml(xml_path)
        assert len(root) >= 1, f"{name}: section에 자식 요소 없음"


# ── 대량 블록 스트레스 테스트 ─────────────────────────────────────

class TestStress:

    def test_100_paragraphs(self, tmp_dir):
        """100개 paragraph 블록 생성."""
        blocks = [{"type": "paragraph", "text": f"문단 {i}"} for i in range(100)]
        xml_path = _build_section(blocks, tmp_dir, "stress_100")
        root = _parse_xml(xml_path)
        # secPr + 100 paragraphs
        para_count = sum(1 for _ in root.iter() if "p" in _.tag.lower()
                         and "run" not in _.tag.lower())
        assert para_count >= 100, f"100개 미만: {para_count}"
