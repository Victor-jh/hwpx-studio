#!/usr/bin/env python3
"""diff_docs.py — 두 HWPX 문서 비교.

기본: 텍스트 unified diff
--structure: 구조 비교 (문단 수, 표 수, pageBreak 수, 총 글자 수)
"""

import argparse
import difflib
import sys
import zipfile
from io import BytesIO

from lxml import etree

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def extract_text(hwpx_path):
    """HWPX에서 section0.xml의 텍스트를 줄 단위 리스트로 추출."""
    lines = []
    with zipfile.ZipFile(hwpx_path, "r") as zf:
        for name in zf.namelist():
            if "section" in name.lower() and name.endswith(".xml"):
                data = zf.read(name)
                tree = etree.parse(BytesIO(data))
                for t_elem in tree.iter(f"{{{HP}}}t"):
                    text = t_elem.text
                    if text:
                        lines.append(text)
                    else:
                        lines.append("")  # 빈 줄
    return lines


def extract_structure(hwpx_path):
    """HWPX에서 구조 정보 추출."""
    info = {
        "paragraphs": 0,
        "tables": 0,
        "page_breaks": 0,
        "total_chars": 0,
        "runs": 0,
        "sections": 0,
    }

    with zipfile.ZipFile(hwpx_path, "r") as zf:
        for name in zf.namelist():
            if "section" in name.lower() and name.endswith(".xml"):
                info["sections"] += 1
                data = zf.read(name)
                tree = etree.parse(BytesIO(data))

                for p_elem in tree.iter(f"{{{HP}}}p"):
                    info["paragraphs"] += 1
                    pb = p_elem.get("pageBreak", "0")
                    if pb == "1":
                        info["page_breaks"] += 1

                for _ in tree.iter(f"{{{HP}}}tbl"):
                    info["tables"] += 1

                for _ in tree.iter(f"{{{HP}}}run"):
                    info["runs"] += 1

                for t_elem in tree.iter(f"{{{HP}}}t"):
                    if t_elem.text:
                        info["total_chars"] += len(t_elem.text)

    return info


def text_diff(file_a, file_b):
    """두 HWPX의 텍스트를 unified diff로 비교."""
    lines_a = extract_text(file_a)
    lines_b = extract_text(file_b)

    diff = difflib.unified_diff(
        lines_a, lines_b,
        fromfile=file_a, tofile=file_b,
        lineterm=""
    )
    return list(diff)


def structure_diff(file_a, file_b):
    """두 HWPX의 구조 정보 비교."""
    struct_a = extract_structure(file_a)
    struct_b = extract_structure(file_b)

    result = []
    result.append(f"{'항목':<20} {'A':>10} {'B':>10} {'차이':>10}")
    result.append("-" * 52)

    for key in struct_a:
        va = struct_a[key]
        vb = struct_b[key]
        diff_val = vb - va
        marker = "" if diff_val == 0 else f"({'+' if diff_val > 0 else ''}{diff_val})"
        label = {
            "paragraphs": "문단 수",
            "tables": "표 수",
            "page_breaks": "pageBreak 수",
            "total_chars": "총 글자 수",
            "runs": "run 수",
            "sections": "섹션 수",
        }.get(key, key)
        result.append(f"{label:<20} {va:>10} {vb:>10} {marker:>10}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="두 HWPX 문서 비교 (텍스트 diff + 구조 비교)")
    parser.add_argument("file_a", help="비교 대상 A (.hwpx)")
    parser.add_argument("file_b", help="비교 대상 B (.hwpx)")
    parser.add_argument("--structure", "-s", action="store_true",
                        help="구조 비교 모드 (문단 수, 표 수, pageBreak 수, 총 글자 수)")
    parser.add_argument("--both", "-b", action="store_true",
                        help="텍스트 diff + 구조 비교 모두 출력")
    args = parser.parse_args()

    if args.both or args.structure:
        print("=== 구조 비교 ===")
        for line in structure_diff(args.file_a, args.file_b):
            print(line)
        if args.both:
            print()

    if args.both or not args.structure:
        print("=== 텍스트 Diff ===")
        diff_lines = text_diff(args.file_a, args.file_b)
        if diff_lines:
            for line in diff_lines:
                print(line)
        else:
            print("(동일)")


if __name__ == "__main__":
    main()
