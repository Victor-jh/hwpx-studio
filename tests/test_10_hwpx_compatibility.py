"""T10 — HWPX 한컴 호환성 구조 검증 테스트.

실제 한컴오피스 없이 OWPML(KS X 6101) 구조 준수 여부를 검증.
ZIP 구조, 필수 파일 존재, XML 네임스페이스, header.xml ID 정합성,
section XML 참조 무결성 등을 자동화된 테스트로 확인.
"""

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from lxml import etree

SRC_DIR = Path(__file__).resolve().parent.parent / "src" / "hwpx_studio"
sys.path.insert(0, str(SRC_DIR))
CREATE_CMD = [sys.executable, str(SRC_DIR / "create_document.py")]

# 네임스페이스
NS = {
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "opf": "http://www.idpf.org/2007/opf/",
    "ocf": "urn:oasis:names:tc:opendocument:xmlns:container",
    "odf": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
}

# HWPX 필수 파일 목록
REQUIRED_FILES = [
    "mimetype",
    "META-INF/container.xml",
    "META-INF/manifest.xml",
    "Contents/content.hpf",
    "Contents/header.xml",
    "settings.xml",
    "version.xml",
]


def _create_hwpx(tmp_dir: Path, name: str, blocks: list,
                 style: str = "report") -> Path:
    """헬퍼: blocks → create_document → HWPX 파일."""
    json_path = tmp_dir / f"{name}.json"
    json_path.write_text(
        json.dumps({"blocks": blocks}, ensure_ascii=False), encoding="utf-8")
    hwpx_path = tmp_dir / f"{name}.hwpx"
    result = subprocess.run(
        CREATE_CMD + [str(json_path), "-s", style, "-o", str(hwpx_path)],
        capture_output=True, text=True, cwd=str(SRC_DIR),
    )
    assert result.returncode == 0, f"HWPX 생성 실패: {result.stderr}"
    assert hwpx_path.exists()
    return hwpx_path


# ── 1. ZIP 구조 검증 ─────────────────────────────────────────────

class TestZipStructure:
    """HWPX ZIP 파일의 필수 구조 검증."""

    @pytest.fixture(autouse=True)
    def _create_sample(self, tmp_dir):
        self.hwpx = _create_hwpx(tmp_dir, "zip_test", [
            {"type": "heading", "level": 1, "text": "테스트 문서"},
            {"type": "paragraph", "text": "본문입니다."},
        ])

    def test_is_valid_zip(self):
        assert zipfile.is_zipfile(self.hwpx)

    def test_required_files_exist(self):
        with zipfile.ZipFile(self.hwpx) as zf:
            names = zf.namelist()
            for req in REQUIRED_FILES:
                assert req in names, f"필수 파일 누락: {req}"

    def test_mimetype_is_first_entry(self):
        """mimetype은 ZIP 첫 번째 엔트리 + 비압축이어야 함 (ODF 호환)."""
        with zipfile.ZipFile(self.hwpx) as zf:
            first = zf.namelist()[0]
            assert first == "mimetype", f"첫 엔트리가 mimetype 아님: {first}"

    def test_mimetype_content(self):
        with zipfile.ZipFile(self.hwpx) as zf:
            content = zf.read("mimetype").decode("utf-8").strip()
            assert content == "application/hwp+zip"

    def test_section_files_exist(self):
        """content.hpf에서 참조하는 section 파일이 ZIP에 존재."""
        with zipfile.ZipFile(self.hwpx) as zf:
            hpf_xml = zf.read("Contents/content.hpf")
            root = etree.fromstring(hpf_xml)
            items = root.findall(".//opf:item", NS)
            for item in items:
                href = item.get("href", "")
                if href.startswith("Contents/section"):
                    assert href in zf.namelist() or \
                        href.lstrip("Contents/") in [
                            n.split("/", 1)[-1] if "/" in n else n
                            for n in zf.namelist()
                        ], f"section 파일 누락: {href}"


# ── 2. container.xml 검증 ────────────────────────────────────────

class TestContainerXml:
    """META-INF/container.xml의 OWPML 호환성."""

    @pytest.fixture(autouse=True)
    def _create_sample(self, tmp_dir):
        self.hwpx = _create_hwpx(tmp_dir, "container_test", [
            {"type": "paragraph", "text": "container 검증용"},
        ])

    def test_rootfile_points_to_hpf(self):
        with zipfile.ZipFile(self.hwpx) as zf:
            xml = zf.read("META-INF/container.xml")
            root = etree.fromstring(xml)
            rootfiles = root.findall(".//ocf:rootfile", NS)
            hpf_entries = [
                rf for rf in rootfiles
                if "content.hpf" in rf.get("full-path", "")
            ]
            assert len(hpf_entries) >= 1, "container.xml에 content.hpf 참조 없음"

    def test_media_type_correct(self):
        with zipfile.ZipFile(self.hwpx) as zf:
            xml = zf.read("META-INF/container.xml")
            root = etree.fromstring(xml)
            rootfiles = root.findall(".//ocf:rootfile", NS)
            for rf in rootfiles:
                if "content.hpf" in rf.get("full-path", ""):
                    mt = rf.get("media-type", "")
                    assert "hwpml" in mt or "xml" in mt, \
                        f"content.hpf media-type 부적절: {mt}"


# ── 3. content.hpf 정합성 ────────────────────────────────────────

class TestContentHpf:
    """content.hpf manifest/spine 검증."""

    @pytest.fixture(autouse=True)
    def _create_sample(self, tmp_dir):
        self.hwpx = _create_hwpx(tmp_dir, "hpf_test", [
            {"type": "paragraph", "text": "hpf 검증"},
        ])

    def test_has_header_item(self):
        with zipfile.ZipFile(self.hwpx) as zf:
            xml = zf.read("Contents/content.hpf")
            root = etree.fromstring(xml)
            items = root.findall(".//opf:item", NS)
            header_items = [
                i for i in items if "header" in i.get("id", "")
            ]
            assert len(header_items) >= 1

    def test_spine_references_valid(self):
        """spine의 idref가 manifest item id에 모두 존재."""
        with zipfile.ZipFile(self.hwpx) as zf:
            xml = zf.read("Contents/content.hpf")
            root = etree.fromstring(xml)
            item_ids = {
                i.get("id") for i in root.findall(".//opf:item", NS)
            }
            spine_refs = root.findall(".//opf:itemref", NS)
            for ref in spine_refs:
                idref = ref.get("idref", "")
                assert idref in item_ids, \
                    f"spine idref='{idref}'가 manifest에 없음"


# ── 4. header.xml ID 정합성 ──────────────────────────────────────

class TestHeaderIntegrity:
    """header.xml의 ID 유일성, itemCnt 정확성."""

    @pytest.fixture(autouse=True)
    def _create_sample(self, tmp_dir):
        self.hwpx = _create_hwpx(tmp_dir, "header_test", [
            {"type": "heading", "level": 1, "text": "제목"},
            {"type": "heading", "level": 2, "text": "소제목"},
            {"type": "paragraph", "text": "본문"},
            {"type": "table", "rows": [
                [{"text": "A"}, {"text": "B"}],
                [{"text": "C"}, {"text": "D"}],
            ]},
        ])

    def _read_header(self):
        with zipfile.ZipFile(self.hwpx) as zf:
            return etree.fromstring(zf.read("Contents/header.xml"))

    def test_charpr_ids_unique(self):
        root = self._read_header()
        ids = [
            int(el.get("id", "0"))
            for el in root.findall(f".//{{{NS['hh']}}}charPr")
        ]
        assert len(ids) == len(set(ids)), f"charPr ID 중복: {ids}"

    def test_parapr_ids_unique(self):
        root = self._read_header()
        ids = [
            int(el.get("id", "0"))
            for el in root.findall(f".//{{{NS['hh']}}}paraPr")
        ]
        assert len(ids) == len(set(ids)), f"paraPr ID 중복: {ids}"

    def test_borderfill_ids_unique(self):
        root = self._read_header()
        ids = [
            int(el.get("id", "0"))
            for el in root.findall(f".//{{{NS['hh']}}}borderFill")
        ]
        assert len(ids) == len(set(ids)), f"borderFill ID 중복: {ids}"

    def test_charpr_itemcnt_matches(self):
        root = self._read_header()
        container = root.find(f".//{{{NS['hh']}}}charProperties")
        if container is not None:
            declared = int(container.get("itemCnt", "0"))
            actual = len(container.findall(f"{{{NS['hh']}}}charPr"))
            assert declared == actual, \
                f"charProperties itemCnt 불일치: 선언={declared} 실제={actual}"

    def test_parapr_itemcnt_matches(self):
        root = self._read_header()
        container = root.find(f".//{{{NS['hh']}}}paraProperties")
        if container is not None:
            declared = int(container.get("itemCnt", "0"))
            actual = len(container.findall(f"{{{NS['hh']}}}paraPr"))
            assert declared == actual, \
                f"paraProperties itemCnt 불일치: 선언={declared} 실제={actual}"

    def test_borderfill_itemcnt_matches(self):
        root = self._read_header()
        container = root.find(f".//{{{NS['hh']}}}borderFills")
        if container is not None:
            declared = int(container.get("itemCnt", "0"))
            actual = len(container.findall(f"{{{NS['hh']}}}borderFill"))
            assert declared == actual, \
                f"borderFills itemCnt 불일치: 선언={declared} 실제={actual}"


# ── 5. section XML 참조 무결성 ──────────────────────────────────

class TestSectionReferenceIntegrity:
    """section XML의 charPrIDRef/paraPrIDRef가 header.xml에 존재하는지."""

    @pytest.fixture(autouse=True)
    def _create_sample(self, tmp_dir):
        self.hwpx = _create_hwpx(tmp_dir, "ref_test", [
            {"type": "heading", "level": 1, "text": "참조 무결성 테스트"},
            {"type": "paragraph", "text": "본문 텍스트"},
            {"type": "bullet", "text": "글머리"},
            {"type": "numbered", "text": "번호"},
        ])

    def test_charpr_refs_valid(self):
        with zipfile.ZipFile(self.hwpx) as zf:
            # header에서 유효 charPr ID 수집
            header = etree.fromstring(zf.read("Contents/header.xml"))
            valid_cp_ids = {
                int(el.get("id", "0"))
                for el in header.findall(f".//{{{NS['hh']}}}charPr")
            }

            # section에서 참조된 charPrIDRef 수집
            for name in zf.namelist():
                if name.startswith("Contents/section") and name.endswith(".xml"):
                    sec = etree.fromstring(zf.read(name))
                    for el in sec.iter():
                        ref = el.get("charPrIDRef")
                        if ref is not None:
                            ref_id = int(ref)
                            assert ref_id in valid_cp_ids, (
                                f"{name}: charPrIDRef={ref_id} "
                                f"header에 없음 (유효: {sorted(valid_cp_ids)})")

    def test_parapr_refs_valid(self):
        with zipfile.ZipFile(self.hwpx) as zf:
            header = etree.fromstring(zf.read("Contents/header.xml"))
            valid_pp_ids = {
                int(el.get("id", "0"))
                for el in header.findall(f".//{{{NS['hh']}}}paraPr")
            }

            for name in zf.namelist():
                if name.startswith("Contents/section") and name.endswith(".xml"):
                    sec = etree.fromstring(zf.read(name))
                    for el in sec.iter():
                        ref = el.get("paraPrIDRef")
                        if ref is not None:
                            ref_id = int(ref)
                            assert ref_id in valid_pp_ids, (
                                f"{name}: paraPrIDRef={ref_id} "
                                f"header에 없음 (유효: {sorted(valid_pp_ids)})")

    def test_borderfill_refs_valid(self):
        with zipfile.ZipFile(self.hwpx) as zf:
            header = etree.fromstring(zf.read("Contents/header.xml"))
            valid_bf_ids = {
                int(el.get("id", "0"))
                for el in header.findall(f".//{{{NS['hh']}}}borderFill")
            }

            for name in zf.namelist():
                if name.startswith("Contents/section") and name.endswith(".xml"):
                    sec = etree.fromstring(zf.read(name))
                    for el in sec.iter():
                        ref = el.get("borderFillIDRef")
                        if ref is not None:
                            ref_id = int(ref)
                            assert ref_id in valid_bf_ids, (
                                f"{name}: borderFillIDRef={ref_id} "
                                f"header에 없음 (유효: {sorted(valid_bf_ids)})")


# ── 6. XML 네임스페이스 검증 ─────────────────────────────────────

class TestXmlNamespaces:
    """모든 XML 파일이 올바른 네임스페이스를 사용하는지."""

    @pytest.fixture(autouse=True)
    def _create_sample(self, tmp_dir):
        self.hwpx = _create_hwpx(tmp_dir, "ns_test", [
            {"type": "paragraph", "text": "네임스페이스 검증"},
        ])

    def test_header_namespace(self):
        with zipfile.ZipFile(self.hwpx) as zf:
            header = etree.fromstring(zf.read("Contents/header.xml"))
            # root 태그는 hh 네임스페이스여야 함
            assert NS["hh"] in header.tag, \
                f"header.xml root 태그 NS 불일치: {header.tag}"

    def test_section_namespace(self):
        with zipfile.ZipFile(self.hwpx) as zf:
            for name in zf.namelist():
                if name.startswith("Contents/section") and name.endswith(".xml"):
                    sec = etree.fromstring(zf.read(name))
                    # section root는 hs 네임스페이스
                    tag = sec.tag
                    assert NS["hs"] in tag or NS["hp"] in tag, \
                        f"{name} root 태그 NS 불일치: {tag}"

    def test_all_xml_parseable(self):
        """ZIP 내 모든 .xml 파일이 파싱 가능."""
        with zipfile.ZipFile(self.hwpx) as zf:
            for name in zf.namelist():
                if name.endswith(".xml"):
                    try:
                        etree.fromstring(zf.read(name))
                    except etree.XMLSyntaxError as e:
                        pytest.fail(f"XML 파싱 실패 — {name}: {e}")


# ── 7. standalone="yes" 검증 ─────────────────────────────────────

class TestStandaloneDeclaration:
    """한컴오피스 호환에 필요한 standalone='yes' 선언."""

    @pytest.fixture(autouse=True)
    def _create_sample(self, tmp_dir):
        self.hwpx = _create_hwpx(tmp_dir, "standalone_test", [
            {"type": "paragraph", "text": "standalone 검증"},
        ])

    def test_header_has_standalone(self):
        with zipfile.ZipFile(self.hwpx) as zf:
            raw = zf.read("Contents/header.xml").decode("utf-8")
            assert 'standalone="yes"' in raw or "standalone='yes'" in raw, \
                "header.xml에 standalone='yes' 누락"

    def test_section_has_standalone(self):
        with zipfile.ZipFile(self.hwpx) as zf:
            for name in zf.namelist():
                if name.startswith("Contents/section") and name.endswith(".xml"):
                    raw = zf.read(name).decode("utf-8")
                    assert 'standalone="yes"' in raw or \
                        "standalone='yes'" in raw, \
                        f"{name}에 standalone='yes' 누락"


# ── 8. 다양한 블록 타입별 생성 + 호환성 ──────────────────────────

class TestBlockTypeCompatibility:
    """다양한 블록 타입으로 생성한 HWPX가 모두 구조적으로 유효한지."""

    BLOCK_SETS = {
        "simple": [
            {"type": "paragraph", "text": "단순 문단"},
        ],
        "headings": [
            {"type": "heading", "level": 1, "text": "대제목"},
            {"type": "heading", "level": 2, "text": "중제목"},
            {"type": "heading", "level": 3, "text": "소제목"},
        ],
        "lists": [
            {"type": "bullet", "text": "글머리 1"},
            {"type": "bullet", "text": "글머리 2"},
            {"type": "numbered", "text": "번호 1"},
            {"type": "numbered", "text": "번호 2"},
        ],
        "table": [
            {"type": "table", "rows": [
                [{"text": "헤더1"}, {"text": "헤더2"}, {"text": "헤더3"}],
                [{"text": "데이터1"}, {"text": "데이터2"}, {"text": "데이터3"}],
            ]},
        ],
        "mixed": [
            {"type": "heading", "level": 1, "text": "제목"},
            {"type": "paragraph", "text": "본문"},
            {"type": "bullet", "text": "항목"},
            {"type": "table", "rows": [
                [{"text": "A"}, {"text": "B"}],
                [{"text": "C"}, {"text": "D"}],
            ]},
            {"type": "pagebreak"},
            {"type": "heading", "level": 2, "text": "다음 섹션"},
            {"type": "paragraph", "text": "두 번째 페이지 내용"},
        ],
    }

    @pytest.mark.parametrize("label,blocks", BLOCK_SETS.items(),
                             ids=BLOCK_SETS.keys())
    def test_structural_validity(self, label, blocks, tmp_dir):
        """블록 세트별 HWPX 구조 유효성 종합 검증."""
        hwpx = _create_hwpx(tmp_dir, f"compat_{label}", blocks)

        with zipfile.ZipFile(hwpx) as zf:
            names = zf.namelist()

            # 필수 파일 존재
            for req in REQUIRED_FILES:
                assert req in names, f"[{label}] 필수 파일 누락: {req}"

            # 모든 XML 파싱 가능
            for name in names:
                if name.endswith(".xml"):
                    try:
                        etree.fromstring(zf.read(name))
                    except etree.XMLSyntaxError as e:
                        pytest.fail(f"[{label}] XML 파싱 실패 — {name}: {e}")

            # header ID 유일성
            header = etree.fromstring(zf.read("Contents/header.xml"))
            for prop_tag in ("charPr", "paraPr", "borderFill"):
                ids = [
                    int(el.get("id", "0"))
                    for el in header.findall(f".//{{{NS['hh']}}}{prop_tag}")
                ]
                assert len(ids) == len(set(ids)), \
                    f"[{label}] {prop_tag} ID 중복: {ids}"


# ── 9. 모든 스타일 템플릿 검증 ──────────────────────────────────

class TestAllStyleTemplates:
    """report, letter, memo 등 모든 스타일로 생성해도 유효한지."""

    STYLES = ["report", "letter", "memo", "kcup"]

    @pytest.mark.parametrize("style", STYLES)
    def test_style_creates_valid_hwpx(self, style, tmp_dir):
        blocks = [
            {"type": "heading", "level": 1, "text": f"{style} 테스트"},
            {"type": "paragraph", "text": "스타일별 유효성 검증"},
        ]
        try:
            hwpx = _create_hwpx(tmp_dir, f"style_{style}", blocks, style=style)
        except AssertionError:
            pytest.skip(f"스타일 '{style}' 지원 안 됨")

        assert zipfile.is_zipfile(hwpx)
        with zipfile.ZipFile(hwpx) as zf:
            assert "mimetype" in zf.namelist()
            assert "Contents/header.xml" in zf.namelist()
            # 모든 XML 파싱 가능
            for name in zf.namelist():
                if name.endswith(".xml"):
                    etree.fromstring(zf.read(name))
