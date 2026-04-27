"""T09 — PropertyRegistry ID 충돌 방어 테스트.

Layer 1: header_path=None → 안전 시작 ID (_SAFE_START_ID=100)
Layer 2: apply() 시 기존 ID 충돌 감지 + 자동 재할당
Layer 3: 경고 로그 출력 확인
"""

import json
import shutil
import sys
from pathlib import Path

import pytest
from lxml import etree

SRC_DIR = Path(__file__).resolve().parent.parent / "src" / "hwpx_studio"
sys.path.insert(0, str(SRC_DIR))

from property_registry import PropertyRegistry, _hh  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parent.parent
_PKG_TEMPLATES = SRC_DIR / "templates"
_SKILL_TEMPLATES = SKILL_DIR / "templates"


def _find_base_header() -> Path | None:
    """base 템플릿의 header.xml 경로를 찾는다."""
    for tpl_dir in (_PKG_TEMPLATES, _SKILL_TEMPLATES):
        candidate = tpl_dir / "base" / "Contents" / "header.xml"
        if candidate.exists():
            return candidate
    return None


# ── Layer 1: 안전 시작 ID ───────────────────────────────────────

class TestSafeStartID:
    """header_path=None일 때 시작 ID가 _SAFE_START_ID(100)인지 검증."""

    def test_default_start_id_without_header(self):
        reg = PropertyRegistry(header_path=None)
        stats = reg.get_stats()
        assert stats["next_charPr_id"] == PropertyRegistry._SAFE_START_ID
        assert stats["next_paraPr_id"] == PropertyRegistry._SAFE_START_ID
        assert stats["next_borderFill_id"] == PropertyRegistry._SAFE_START_ID

    def test_first_allocated_id_is_safe(self):
        reg = PropertyRegistry(header_path=None)
        cp_id = reg.resolve_charPr({"bold": True, "size": 14})
        pp_id = reg.resolve_paraPr({"align": "CENTER"})
        bf_id = reg.resolve_borderFill({"bg": "#FF0000"})
        assert cp_id == PropertyRegistry._SAFE_START_ID
        assert pp_id == PropertyRegistry._SAFE_START_ID
        assert bf_id == PropertyRegistry._SAFE_START_ID

    def test_incremental_allocation(self):
        reg = PropertyRegistry(header_path=None)
        id1 = reg.resolve_charPr({"bold": True, "size": 14})
        id2 = reg.resolve_charPr({"bold": True, "size": 20})
        assert id1 == PropertyRegistry._SAFE_START_ID
        assert id2 == PropertyRegistry._SAFE_START_ID + 1

    def test_with_header_starts_from_max(self, tmp_dir):
        """header.xml 제공 시 기존 max ID + 1부터 시작."""
        header = _find_base_header()
        if header is None:
            pytest.skip("base header.xml not found")
        reg = PropertyRegistry(header_path=str(header))
        stats = reg.get_stats()
        # base 템플릿은 charPr id가 0~N이므로 next_id > 0
        assert stats["next_charPr_id"] > 0
        assert stats["next_paraPr_id"] > 0


# ── Layer 2: apply() 충돌 감지 + 재할당 ─────────────────────────

class TestCollisionDetection:
    """apply() 시 기존 ID와 충돌하는 새 엔트리가 자동 재할당되는지 검증."""

    def _make_header_with_ids(self, tmp_dir: Path,
                               charpr_ids: list[int],
                               parapr_ids: list[int],
                               borderfill_ids: list[int]) -> Path:
        """테스트용 최소 header.xml 생성."""
        HH = "http://www.hancom.co.kr/hwpml/2011/head"
        nsmap = {None: HH}
        root = etree.Element(f"{{{HH}}}head", nsmap=nsmap)

        # charProperties
        cp_container = etree.SubElement(root, f"{{{HH}}}charProperties")
        cp_container.set("itemCnt", str(len(charpr_ids)))
        for cid in charpr_ids:
            cp = etree.SubElement(cp_container, f"{{{HH}}}charPr")
            cp.set("id", str(cid))
            cp.set("height", "1000")
            cp.set("textColor", "#000000")

        # paraProperties
        pp_container = etree.SubElement(root, f"{{{HH}}}paraProperties")
        pp_container.set("itemCnt", str(len(parapr_ids)))
        for pid in parapr_ids:
            pp = etree.SubElement(pp_container, f"{{{HH}}}paraPr")
            pp.set("id", str(pid))

        # borderFills
        bf_container = etree.SubElement(root, f"{{{HH}}}borderFills")
        bf_container.set("itemCnt", str(len(borderfill_ids)))
        for bid in borderfill_ids:
            bf = etree.SubElement(bf_container, f"{{{HH}}}borderFill")
            bf.set("id", str(bid))

        header_path = tmp_dir / "header.xml"
        tree = etree.ElementTree(root)
        tree.write(str(header_path), pretty_print=True,
                   xml_declaration=True, encoding="UTF-8")
        return header_path

    def test_no_collision_normal_apply(self, tmp_dir):
        """충돌 없는 경우 ID가 그대로 유지."""
        header = self._make_header_with_ids(
            tmp_dir, charpr_ids=[0, 1, 2],
            parapr_ids=[0, 1], borderfill_ids=[1, 2])
        reg = PropertyRegistry(header_path=str(header))
        # next_id는 3, 2, 3 → 충돌 없음
        cp_id = reg.resolve_charPr({"bold": True, "size": 14})
        assert cp_id == 3  # max(0,1,2)+1

        reg.apply(str(header))

        # 확인: header.xml에 id=3 charPr이 추가됨
        tree = etree.parse(str(header))
        root = tree.getroot()
        all_cp_ids = {
            int(el.get("id"))
            for el in root.findall(f".//{_hh('charPr')}")
        }
        assert 3 in all_cp_ids
        assert len(all_cp_ids) == 4  # 0,1,2,3

    def test_collision_remapped(self, tmp_dir):
        """ID가 기존과 충돌하면 자동 재할당."""
        header = self._make_header_with_ids(
            tmp_dir, charpr_ids=[0, 1, 2, 100],
            parapr_ids=[0, 1], borderfill_ids=[1, 2])

        # header_path=None으로 레지스트리 생성 → 시작 ID=100
        reg = PropertyRegistry(header_path=None)
        cp_id = reg.resolve_charPr({"bold": True, "size": 14})
        assert cp_id == 100  # 할당 시점에는 100

        # apply 시 기존 id=100과 충돌 → 재할당
        reg.apply(str(header))

        tree = etree.parse(str(header))
        root = tree.getroot()
        all_cp_ids = {
            int(el.get("id"))
            for el in root.findall(f".//{_hh('charPr')}")
        }
        # 기존 0,1,2,100 + 새로 할당된 ID (101)
        assert 100 in all_cp_ids  # 기존
        assert 101 in all_cp_ids  # 재할당
        assert len(all_cp_ids) == 5

    def test_multiple_collisions(self, tmp_dir):
        """여러 엔트리가 동시에 충돌해도 모두 고유 ID로 재할당."""
        header = self._make_header_with_ids(
            tmp_dir, charpr_ids=[100, 101, 102],
            parapr_ids=[100], borderfill_ids=[100])

        reg = PropertyRegistry(header_path=None)
        id1 = reg.resolve_charPr({"bold": True, "size": 14})
        id2 = reg.resolve_charPr({"bold": True, "size": 20})
        id3 = reg.resolve_charPr({"italic": True, "size": 10})
        assert [id1, id2, id3] == [100, 101, 102]

        reg.apply(str(header))

        tree = etree.parse(str(header))
        root = tree.getroot()
        all_cp_ids = sorted(
            int(el.get("id"))
            for el in root.findall(f".//{_hh('charPr')}")
        )
        # 기존 100,101,102 + 재할당 103,104,105
        assert len(all_cp_ids) == 6
        assert len(set(all_cp_ids)) == 6  # 모두 고유

    def test_borderfill_collision(self, tmp_dir):
        """borderFill ID 충돌 재할당."""
        header = self._make_header_with_ids(
            tmp_dir, charpr_ids=[0], parapr_ids=[0],
            borderfill_ids=[1, 2, 100])

        reg = PropertyRegistry(header_path=None)
        bf_id = reg.resolve_borderFill({"bg": "#FF0000"})
        assert bf_id == 100

        reg.apply(str(header))

        tree = etree.parse(str(header))
        root = tree.getroot()
        all_bf_ids = {
            int(el.get("id"))
            for el in root.findall(f".//{_hh('borderFill')}")
        }
        assert 100 in all_bf_ids  # 기존
        assert 101 in all_bf_ids  # 재할당
        assert len(all_bf_ids) == 4

    def test_parapr_collision(self, tmp_dir):
        """paraPr ID 충돌 재할당."""
        header = self._make_header_with_ids(
            tmp_dir, charpr_ids=[0], parapr_ids=[0, 100],
            borderfill_ids=[1])

        reg = PropertyRegistry(header_path=None)
        pp_id = reg.resolve_paraPr({"align": "CENTER"})
        assert pp_id == 100

        reg.apply(str(header))

        tree = etree.parse(str(header))
        root = tree.getroot()
        all_pp_ids = {
            int(el.get("id"))
            for el in root.findall(f".//{_hh('paraPr')}")
        }
        assert 100 in all_pp_ids
        assert 101 in all_pp_ids
        assert len(all_pp_ids) == 3


# ── Layer 3: 경고 로그 ──────────────────────────────────────────

class TestWarningLogs:
    """로그 메시지가 올바르게 출력되는지 검증."""

    def test_warning_on_no_header(self, caplog):
        """header_path=None일 때 경고 로그 출력."""
        import logging
        with caplog.at_level(logging.WARNING, logger="property_registry"):
            PropertyRegistry(header_path=None)
        assert any("header_path=None" in msg for msg in caplog.messages)
        assert any("시작 ID=100" in msg or "100" in msg for msg in caplog.messages)

    def test_warning_on_collision(self, tmp_dir, caplog):
        """apply() 충돌 시 경고 로그 출력."""
        import logging
        HH = "http://www.hancom.co.kr/hwpml/2011/head"
        nsmap = {None: HH}
        root = etree.Element(f"{{{HH}}}head", nsmap=nsmap)
        cp_container = etree.SubElement(root, f"{{{HH}}}charProperties")
        cp_container.set("itemCnt", "1")
        cp = etree.SubElement(cp_container, f"{{{HH}}}charPr")
        cp.set("id", "100")
        cp.set("height", "1000")
        pp_container = etree.SubElement(root, f"{{{HH}}}paraProperties")
        pp_container.set("itemCnt", "0")
        bf_container = etree.SubElement(root, f"{{{HH}}}borderFills")
        bf_container.set("itemCnt", "0")

        header_path = tmp_dir / "header_warn.xml"
        tree = etree.ElementTree(root)
        tree.write(str(header_path), pretty_print=True,
                   xml_declaration=True, encoding="UTF-8")

        reg = PropertyRegistry(header_path=None)
        reg.resolve_charPr({"bold": True, "size": 14})

        with caplog.at_level(logging.WARNING, logger="property_registry"):
            reg.apply(str(header_path))

        assert any("충돌 감지" in msg for msg in caplog.messages)
        assert any("재할당" in msg for msg in caplog.messages)


# ── 통합: 실제 템플릿 기반 라운드트립 ──────────────────────────

class TestRealTemplateIntegration:
    """실제 base 템플릿 header.xml 기반 통합 테스트."""

    def test_safe_id_no_collision_with_base_template(self, tmp_dir):
        """safe start ID(100)가 base 템플릿 기존 ID와 충돌하지 않는지 검증."""
        header = _find_base_header()
        if header is None:
            pytest.skip("base header.xml not found")

        # 기존 ID 범위 확인
        tree = etree.parse(str(header))
        root = tree.getroot()
        existing_cp_ids = {
            int(el.get("id", "0"))
            for el in root.findall(f".//{_hh('charPr')}")
        }
        existing_pp_ids = {
            int(el.get("id", "0"))
            for el in root.findall(f".//{_hh('paraPr')}")
        }

        # 기존 최대 ID가 _SAFE_START_ID 미만인지 확인
        if existing_cp_ids:
            max_cp = max(existing_cp_ids)
            assert max_cp < PropertyRegistry._SAFE_START_ID, (
                f"base charPr max id={max_cp} >= "
                f"SAFE_START_ID={PropertyRegistry._SAFE_START_ID}")
        if existing_pp_ids:
            max_pp = max(existing_pp_ids)
            assert max_pp < PropertyRegistry._SAFE_START_ID, (
                f"base paraPr max id={max_pp} >= "
                f"SAFE_START_ID={PropertyRegistry._SAFE_START_ID}")

    def test_apply_to_real_header_no_collision(self, tmp_dir):
        """실제 header.xml에 적용 시 충돌 없이 정상 삽입."""
        header = _find_base_header()
        if header is None:
            pytest.skip("base header.xml not found")

        # header.xml 복사 (원본 보호)
        test_header = tmp_dir / "header.xml"
        shutil.copy2(header, test_header)

        reg = PropertyRegistry(header_path=str(test_header))
        cp_id = reg.resolve_charPr({"bold": True, "size": 24})
        pp_id = reg.resolve_paraPr({"align": "CENTER", "lineSpacing": 200})
        bf_id = reg.resolve_borderFill({"bg": "#EEEEEE", "border": "SOLID"})

        reg.apply(str(test_header))

        # 검증: 새 ID가 파일에 존재
        tree = etree.parse(str(test_header))
        root = tree.getroot()
        all_cp_ids = {
            int(el.get("id"))
            for el in root.findall(f".//{_hh('charPr')}")
        }
        all_pp_ids = {
            int(el.get("id"))
            for el in root.findall(f".//{_hh('paraPr')}")
        }
        all_bf_ids = {
            int(el.get("id"))
            for el in root.findall(f".//{_hh('borderFill')}")
        }
        assert cp_id in all_cp_ids
        assert pp_id in all_pp_ids
        assert bf_id in all_bf_ids
        # 모든 ID가 고유한지
        assert len(all_cp_ids) == len(
            root.findall(f".//{_hh('charPr')}"))
        assert len(all_pp_ids) == len(
            root.findall(f".//{_hh('paraPr')}"))
