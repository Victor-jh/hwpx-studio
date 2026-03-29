#!/usr/bin/env python3
"""Extract text from an HWPX document.

Uses zipfile + lxml to read section XML files directly — no external HWP libraries needed.

Usage:
    python text_extract.py document.hwpx
    python text_extract.py document.hwpx --format markdown
    python text_extract.py document.hwpx --include-tables
"""

import argparse
import sys
import zipfile
from pathlib import Path

from lxml import etree

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HS = "http://www.hancom.co.kr/hwpml/2011/section"


def _iter_sections(zf: zipfile.ZipFile) -> list[str]:
    """Return sorted list of section XML entry names in the ZIP."""
    names = zf.namelist()
    sections = sorted(
        n for n in names if n.startswith("Contents/section") and n.endswith(".xml")
    )
    return sections


def _para_text(para_el: etree._Element) -> str:
    """Extract concatenated text from a single hp:p element."""
    parts = []
    for t in para_el.iter(f"{{{HP}}}t"):
        if t.text:
            parts.append(t.text)
    return "".join(parts)


def _is_table(para_el: etree._Element) -> bool:
    """Return True if the paragraph contains a table (hp:tbl)."""
    return para_el.find(f".//{{{HP}}}tbl") is not None


def extract_plain(hwpx_path: str, *, include_tables: bool = False) -> str:
    """Extract plain text from HWPX file."""
    lines: list[str] = []

    with zipfile.ZipFile(hwpx_path, "r") as zf:
        for section_name in _iter_sections(zf):
            xml_bytes = zf.read(section_name)
            root = etree.fromstring(xml_bytes)

            for para in root.iter(f"{{{HP}}}p"):
                # Skip paragraphs inside tables unless include_tables is set
                parent = para.getparent()
                in_table = False
                node = parent
                while node is not None:
                    if node.tag == f"{{{HP}}}tbl":
                        in_table = True
                        break
                    node = node.getparent()

                if in_table and not include_tables:
                    continue

                text = _para_text(para)
                if text.strip():
                    lines.append(text)

    return "\n".join(lines)


def extract_markdown(hwpx_path: str) -> str:
    """Extract text as Markdown with section separators and table formatting."""
    sections_output: list[list[str]] = []

    with zipfile.ZipFile(hwpx_path, "r") as zf:
        for section_name in _iter_sections(zf):
            xml_bytes = zf.read(section_name)
            root = etree.fromstring(xml_bytes)

            section_lines: list[str] = []

            # Process top-level paragraphs and tables in document order
            sec_el = root if root.tag == f"{{{HS}}}sec" else root.find(f"{{{HS}}}sec")
            if sec_el is None:
                sec_el = root

            for child in sec_el:
                if child.tag == f"{{{HP}}}p":
                    text = _para_text(child)
                    if text.strip():
                        section_lines.append(text)
                    elif section_lines and section_lines[-1] != "":
                        section_lines.append("")

                elif child.tag == f"{{{HP}}}p" and _is_table(child):
                    # table embedded in paragraph
                    pass

                # hp:tbl at section level — render as Markdown table
                else:
                    for tbl in child.iter(f"{{{HP}}}tbl") if child.tag != f"{{{HP}}}tbl" else [child]:
                        rows: list[list[str]] = []
                        for tr in tbl.iter(f"{{{HP}}}tr"):
                            row_cells: list[str] = []
                            for tc in tr:
                                if tc.tag != f"{{{HP}}}tc":
                                    continue
                                cell_parts = []
                                for para in tc.iter(f"{{{HP}}}p"):
                                    t = _para_text(para)
                                    if t.strip():
                                        cell_parts.append(t.strip())
                                row_cells.append(" ".join(cell_parts))
                            if row_cells:
                                rows.append(row_cells)

                        if rows:
                            col_count = max(len(r) for r in rows)
                            # Pad rows
                            for r in rows:
                                while len(r) < col_count:
                                    r.append("")

                            def _md_row(cells: list[str]) -> str:
                                return "| " + " | ".join(cells) + " |"

                            section_lines.append(_md_row(rows[0]))
                            section_lines.append(
                                "| " + " | ".join(["---"] * col_count) + " |"
                            )
                            for r in rows[1:]:
                                section_lines.append(_md_row(r))
                            section_lines.append("")

            if section_lines:
                sections_output.append(section_lines)

    result_parts: list[str] = []
    for i, sec_lines in enumerate(sections_output):
        if i > 0:
            result_parts.append("")
            result_parts.append("---")
            result_parts.append("")
        result_parts.extend(sec_lines)

    return "\n".join(result_parts)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract text from an HWPX document"
    )
    parser.add_argument("input", help="Path to .hwpx file")
    parser.add_argument(
        "--format", "-f",
        choices=["plain", "markdown"],
        default="plain",
        help="Output format (default: plain)",
    )
    parser.add_argument(
        "--include-tables",
        action="store_true",
        help="Include text from tables (plain mode)",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)",
    )
    args = parser.parse_args()

    if not Path(args.input).is_file():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    if args.format == "markdown":
        result = extract_markdown(args.input)
    else:
        result = extract_plain(args.input, include_tables=args.include_tables)

    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
        print(f"Extracted to: {args.output}", file=sys.stderr)
    else:
        print(result)


if __name__ == "__main__":
    main()
