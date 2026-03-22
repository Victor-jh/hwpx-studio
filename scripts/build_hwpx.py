#!/usr/bin/env python3
"""Build an HWPX document from templates and XML overrides.

Assembles a valid HWPX file by:
1. Copying the base template
2. Optionally overlaying a document-type template (gonmun, report, minutes)
3. Optionally overriding header.xml and/or section0.xml with custom files
4. Optionally setting metadata (title, creator)
5. Validating XML well-formedness
6. Packaging as HWPX (ZIP with mimetype first, ZIP_STORED)

Usage:
    # Empty document from base template
    python build_hwpx.py --output result.hwpx

    # Using a document-type template
    python build_hwpx.py --template gonmun --output result.hwpx

    # Custom section XML override
    python build_hwpx.py --template gonmun --section my_section0.xml --output result.hwpx

    # Custom header and section
    python build_hwpx.py --header my_header.xml --section my_section0.xml --output result.hwpx

    # With metadata
    python build_hwpx.py --template gonmun --section my.xml --title "제목" --creator "작성자" --output result.hwpx
"""

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from lxml import etree
from property_registry import PropertyRegistry

# Resolve paths relative to this script
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATES_DIR = SKILL_DIR / "templates"
BASE_DIR = TEMPLATES_DIR / "base"

AVAILABLE_TEMPLATES = ["gonmun", "report", "minutes", "kcup", "proposal"]


def validate_xml(filepath: Path) -> None:
    """Check that an XML file is well-formed. Raises on error."""
    try:
        etree.parse(str(filepath))
    except etree.XMLSyntaxError as e:
        raise SystemExit(f"Malformed XML in {filepath.name}: {e}")


def update_metadata(content_hpf: Path, title: str | None, creator: str | None) -> None:
    """Update title and/or creator in content.hpf."""
    if not title and not creator:
        return

    tree = etree.parse(str(content_hpf))
    root = tree.getroot()
    ns = {"opf": "http://www.idpf.org/2007/opf/"}

    if title:
        title_el = root.find(".//opf:title", ns)
        if title_el is not None:
            title_el.text = title

    now = datetime.now(timezone.utc)
    iso_now = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    for meta in root.findall(".//opf:meta", ns):
        name = meta.get("name", "")
        if creator and name == "creator":
            meta.text = creator
        elif creator and name == "lastsaveby":
            meta.text = creator
        elif name == "CreatedDate":
            meta.text = iso_now
        elif name == "ModifiedDate":
            meta.text = iso_now
        elif name == "date":
            meta.text = now.strftime("%Y년 %m월 %d일")

    etree.indent(root, space="  ")
    tree.write(
        str(content_hpf),
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8",
    )


def pack_hwpx(input_dir: Path, output_path: Path) -> None:
    """Create HWPX archive with mimetype as first entry (ZIP_STORED)."""
    mimetype_file = input_dir / "mimetype"
    if not mimetype_file.is_file():
        raise SystemExit(f"Missing 'mimetype' in {input_dir}")

    # .DS_Store 등 비문서 파일 제외
    EXCLUDE = {".DS_Store", "Thumbs.db", ".gitignore"}
    all_files = sorted(
        p.relative_to(input_dir).as_posix()
        for p in input_dir.rglob("*")
        if p.is_file() and p.name not in EXCLUDE
    )

    with ZipFile(output_path, "w", ZIP_DEFLATED) as zf:
        zf.write(mimetype_file, "mimetype", compress_type=ZIP_STORED)
        for rel_path in all_files:
            if rel_path == "mimetype":
                continue
            zf.write(input_dir / rel_path, rel_path, compress_type=ZIP_DEFLATED)


def validate_hwpx(hwpx_path: Path) -> list[str]:
    """Quick structural validation of the output HWPX."""
    errors: list[str] = []
    required = [
        "mimetype",
        "Contents/content.hpf",
        "Contents/header.xml",
        "Contents/section0.xml",
    ]

    try:
        from zipfile import BadZipFile
        zf = ZipFile(hwpx_path, "r")
    except BadZipFile:
        return [f"Not a valid ZIP: {hwpx_path}"]

    with zf:
        names = zf.namelist()
        for r in required:
            if r not in names:
                errors.append(f"Missing: {r}")

        if "mimetype" in names:
            content = zf.read("mimetype").decode("utf-8").strip()
            if content != "application/hwp+zip":
                errors.append(f"Bad mimetype content: {content}")
            if names[0] != "mimetype":
                errors.append("mimetype is not the first ZIP entry")
            info = zf.getinfo("mimetype")
            if info.compress_type != ZIP_STORED:
                errors.append("mimetype is not ZIP_STORED")

        for name in names:
            if name.endswith(".xml") or name.endswith(".hpf"):
                try:
                    etree.fromstring(zf.read(name))
                except etree.XMLSyntaxError as e:
                    errors.append(f"Malformed XML: {name}: {e}")

    return errors


def _register_sections_in_hpf(content_hpf: Path, section_files: list[str]) -> None:
    """content.hpf의 manifest/spine에 섹션 파일들을 등록."""
    tree = etree.parse(str(content_hpf))
    root = tree.getroot()
    ns = {"opf": "http://www.idpf.org/2007/opf/"}

    manifest = root.find(".//opf:manifest", ns)
    spine = root.find(".//opf:spine", ns)
    if manifest is None or spine is None:
        return

    # 기존 section 항목 제거
    for item in list(manifest.findall("opf:item", ns)):
        item_id = item.get("id", "")
        if item_id.startswith("section"):
            manifest.remove(item)
    for ref in list(spine.findall("opf:itemref", ns)):
        idref = ref.get("idref", "")
        if idref.startswith("section"):
            spine.remove(ref)

    # 새 section 항목 추가
    OPF = "http://www.idpf.org/2007/opf/"
    for fname in section_files:
        sec_id = fname.replace(".xml", "")  # "section0", "section1", ...
        item = etree.SubElement(manifest, f"{{{OPF}}}item")
        item.set("id", sec_id)
        item.set("href", f"Contents/{fname}")
        item.set("media-type", "application/xml")

        ref = etree.SubElement(spine, f"{{{OPF}}}itemref")
        ref.set("idref", sec_id)
        ref.set("linear", "yes")

    etree.indent(root, space="  ")
    tree.write(str(content_hpf), pretty_print=True,
               xml_declaration=True, encoding="UTF-8")


def _register_images_in_hpf(content_hpf: Path, images: list[dict]) -> None:
    """content.hpf manifest에 BinData 이미지 항목 등록.

    images: [{"id": "image1", "filename": "image1.png", "media_type": "image/png"}, ...]
    """
    if not images:
        return

    tree = etree.parse(str(content_hpf))
    root = tree.getroot()
    ns = {"opf": "http://www.idpf.org/2007/opf/"}
    OPF = "http://www.idpf.org/2007/opf/"

    manifest = root.find(".//opf:manifest", ns)
    if manifest is None:
        return

    # 기존 image 항목 제거 (재생성 방지)
    for item in list(manifest.findall("opf:item", ns)):
        item_id = item.get("id", "")
        if item_id.startswith("image"):
            manifest.remove(item)

    # 이미지 항목 추가
    for img in images:
        item = etree.SubElement(manifest, f"{{{OPF}}}item")
        item.set("id", img["id"])
        item.set("href", f"BinData/{img['filename']}")
        item.set("media-type", img["media_type"])
        item.set("isEmbeded", "1")

    etree.indent(root, space="  ")
    tree.write(str(content_hpf), pretty_print=True,
               xml_declaration=True, encoding="UTF-8")


def _copy_images_to_bindata(work_dir: Path, images: list[dict]) -> None:
    """이미지 파일들을 빌드 디렉토리의 BinData/ 폴더에 복사."""
    if not images:
        return

    bindata_dir = work_dir / "BinData"
    bindata_dir.mkdir(exist_ok=True)

    for img in images:
        src = Path(img["src"])
        dest = bindata_dir / img["filename"]
        if src.exists():
            shutil.copy2(src, dest)
        else:
            print(f"WARNING: Image not found: {src}", file=sys.stderr)


def load_registry(registry_json: Path | None = None,
                   section_dir: Path | None = None,
                   section_path: Path | None = None) -> PropertyRegistry | None:
    """레지스트리 사이드카 JSON 로드. 여러 소스에서 자동 탐색."""
    if registry_json and registry_json.exists():
        return PropertyRegistry.load(str(registry_json))

    # 자동 탐색
    candidates = []
    if section_dir:
        candidates.append(section_dir / "_registry.json")
    if section_path:
        candidates.append(
            section_path.parent / f"{section_path.stem}_registry.json")

    for c in candidates:
        if c and c.exists():
            return PropertyRegistry.load(str(c))

    return None


def load_images_manifest(images_json: Path | None = None,
                          section_dir: Path | None = None,
                          section_path: Path | None = None) -> list[dict]:
    """이미지 매니페스트 로드. 여러 소스에서 자동 탐색."""
    if images_json and images_json.exists():
        with open(images_json, "r", encoding="utf-8") as f:
            return json.load(f)

    # 자동 탐색: section_dir 또는 section_path 옆에 _images.json
    candidates = []
    if section_dir:
        candidates.append(section_dir / "_images.json")
    if section_path:
        candidates.append(
            section_path.parent / f"{section_path.stem}_images.json")

    for c in candidates:
        if c and c.exists():
            with open(c, "r", encoding="utf-8") as f:
                return json.load(f)

    return []


def build(
    template: str | None,
    header_override: Path | None,
    section_override: Path | None,
    title: str | None,
    creator: str | None,
    output: Path,
    section_dir: Path | None = None,
    images_json: Path | None = None,
    registry: PropertyRegistry | None = None,
) -> None:
    """Main build logic.

    section_dir: 다중 섹션 시 section0.xml, section1.xml, ... 가 있는 디렉토리.
                 section_override와 동시 사용 불가.
    images_json: 이미지 매니페스트 JSON 경로 (자동 탐색도 지원).
    registry: 동적 charPr/paraPr/borderFill 레지스트리. 있으면 header.xml에 적용.
    """

    if not BASE_DIR.is_dir():
        raise SystemExit(f"Base template not found: {BASE_DIR}")

    with tempfile.TemporaryDirectory() as tmpdir:
        work = Path(tmpdir) / "build"

        # 1. Copy base template
        shutil.copytree(BASE_DIR, work)

        # 2. Apply template overlay
        if template:
            overlay_dir = TEMPLATES_DIR / template
            if not overlay_dir.is_dir():
                raise SystemExit(
                    f"Template '{template}' not found. "
                    f"Available: {', '.join(AVAILABLE_TEMPLATES)}"
                )
            for overlay_file in overlay_dir.iterdir():
                if overlay_file.is_file() and overlay_file.suffix == ".xml":
                    dest = work / "Contents" / overlay_file.name
                    shutil.copy2(overlay_file, dest)

        # 3. Apply custom overrides
        if header_override:
            if not header_override.is_file():
                raise SystemExit(f"Header file not found: {header_override}")
            shutil.copy2(header_override, work / "Contents" / "header.xml")

        if section_dir:
            # 다중 섹션: 디렉토리 내 section*.xml 복사
            section_files = sorted(
                f.name for f in section_dir.iterdir()
                if f.is_file() and f.name.startswith("section") and f.suffix == ".xml"
            )
            if not section_files:
                raise SystemExit(f"No section*.xml found in {section_dir}")
            # 기존 section0.xml 제거
            old_sec = work / "Contents" / "section0.xml"
            if old_sec.exists():
                old_sec.unlink()
            for fname in section_files:
                shutil.copy2(section_dir / fname, work / "Contents" / fname)
            # content.hpf 갱신
            _register_sections_in_hpf(work / "Contents" / "content.hpf",
                                       section_files)
        elif section_override:
            if not section_override.is_file():
                raise SystemExit(f"Section file not found: {section_override}")
            shutil.copy2(section_override, work / "Contents" / "section0.xml")

        # 4. Process images (BinData)
        # 레지스트리 자동 로드 (CLI에서 직접 전달되지 않은 경우)
        if registry is None:
            registry = load_registry(
                section_dir=section_dir,
                section_path=section_override,
            )

        images = load_images_manifest(
            images_json=images_json,
            section_dir=section_dir,
            section_path=section_override,
        )
        if images:
            _copy_images_to_bindata(work, images)
            _register_images_in_hpf(work / "Contents" / "content.hpf", images)
            print(f"  Images: {len(images)} files added to BinData/",
                  file=sys.stderr)

        # 5. Update metadata
        update_metadata(work / "Contents" / "content.hpf", title, creator)

        # 5.5. Apply dynamic property registry to header.xml
        if registry and registry.has_changes():
            header_xml = work / "Contents" / "header.xml"
            registry.apply(str(header_xml))
            stats = registry.get_stats()
            print(f"  Registry: +{stats['new_charPr']} charPr, "
                  f"+{stats['new_paraPr']} paraPr, "
                  f"+{stats['new_borderFill']} borderFill, "
                  f"+{stats['new_fonts']} fonts", file=sys.stderr)

        # 6. Validate all XML files
        for xml_file in work.rglob("*.xml"):
            validate_xml(xml_file)
        for hpf_file in work.rglob("*.hpf"):
            validate_xml(hpf_file)

        # 7. Pack
        pack_hwpx(work, output)

    # 8. Final validation
    errors = validate_hwpx(output)
    if errors:
        print(f"WARNING: {output} has issues:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
    else:
        print(f"VALID: {output}")
        print(f"  Template: {template or 'base'}")
        if header_override:
            print(f"  Header: {header_override}")
        if section_dir:
            print(f"  Sections: {section_dir}")
        elif section_override:
            print(f"  Section: {section_override}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build HWPX document from templates and XML overrides"
    )
    parser.add_argument(
        "--template", "-t",
        choices=AVAILABLE_TEMPLATES,
        help="Document type template to use as overlay",
    )
    parser.add_argument(
        "--header",
        type=Path,
        help="Custom header.xml to override",
    )
    parser.add_argument(
        "--section",
        type=Path,
        help="Custom section0.xml to override (단일 섹션)",
    )
    parser.add_argument(
        "--section-dir",
        type=Path,
        help="다중 섹션 디렉토리 (section0.xml, section1.xml, ...)",
    )
    parser.add_argument(
        "--title",
        help="Document title (updates content.hpf metadata)",
    )
    parser.add_argument(
        "--creator",
        help="Document creator (updates content.hpf metadata)",
    )
    parser.add_argument(
        "--images-json",
        type=Path,
        help="이미지 매니페스트 JSON (_images.json). 미지정 시 자동 탐색.",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Output .hwpx file path",
    )
    args = parser.parse_args()

    build(
        template=args.template,
        header_override=args.header,
        section_override=args.section,
        title=args.title,
        creator=args.creator,
        output=args.output,
        section_dir=getattr(args, 'section_dir', None),
        images_json=getattr(args, 'images_json', None),
    )


if __name__ == "__main__":
    main()
