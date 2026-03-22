#!/usr/bin/env python3
"""edit_document.py — HWPX 문서 편집기 (Phase 2).

기존 HWPX 문서의 section0.xml을 직접 수정하여 저장.
ZIP 내부의 XML을 in-place로 편집하므로 스타일/서식/이미지 등이 보존됨.

지원 편집 작업:
    1. replace_text   — 텍스트 찾아 바꾸기
    2. insert_block   — 지정 위치에 블록 삽입
    3. delete_block   — 인덱스로 블록 삭제
    4. update_block   — 인덱스로 블록 수정
    5. reorder_blocks — 블록 순서 변경
    6. update_header_footer — 머리말/꼬리말 수정

Usage:
    # 텍스트 찾아 바꾸기
    python edit_document.py doc.hwpx --replace "원본텍스트" "새텍스트" -o edited.hwpx

    # JSON 편집 스크립트 적용
    python edit_document.py doc.hwpx --edit-json edit_commands.json -o edited.hwpx

    # 블록 삭제 (인덱스 5번)
    python edit_document.py doc.hwpx --delete-block 5 -o edited.hwpx

편집 JSON 스크립트 형식:
    {
        "operations": [
            {"op": "replace_text", "find": "원본", "replace": "새것"},
            {"op": "insert_block", "index": 3, "block": {"type": "text", "text": "새 문단"}},
            {"op": "delete_block", "index": 5},
            {"op": "update_block", "index": 2, "text": "수정된 텍스트"},
            {"op": "update_header", "text": "새 머리말"}
        ]
    }
"""

import argparse
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional

from lxml import etree

# ── 네임스페이스 ────────────────────────────────────────────────
HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HS = "http://www.hancom.co.kr/hwpml/2011/section"
HC = "http://www.hancom.co.kr/hwpml/2011/core"
HH = "http://www.hancom.co.kr/hwpml/2011/head"

NSMAP = {
    "hp": HP, "hs": HS, "hc": HC, "hh": HH,
    "ha": "http://www.hancom.co.kr/hwpml/2011/app",
    "hp10": "http://www.hancom.co.kr/hwpml/2016/paragraph",
    "hhs": "http://www.hancom.co.kr/hwpml/2011/history",
    "hm": "http://www.hancom.co.kr/hwpml/2011/master-page",
    "hpf": "http://www.hancom.co.kr/schema/2011/hpf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "opf": "http://www.idpf.org/2007/opf/",
    "ooxmlchart": "http://www.hancom.co.kr/hwpml/2016/ooxmlchart",
    "hwpunitchar": "http://www.hancom.co.kr/hwpml/2016/HwpUnitChar",
    "epub": "http://www.idpf.org/2007/ops",
    "config": "urn:oasis:names:tc:opendocument:xmlns:config:1.0",
}


def _hp(tag: str) -> str:
    return f"{{{HP}}}{tag}"


def _hs(tag: str) -> str:
    return f"{{{HS}}}{tag}"


def _hc(tag: str) -> str:
    return f"{{{HC}}}{tag}"


def _hh(tag: str) -> str:
    return f"{{{HH}}}{tag}"


# ── HWPX ZIP 편집기 ──────────────────────────────────────────────

class HWPXEditor:
    """HWPX 문서 편집기.

    ZIP 내부의 section XML을 직접 수정하고 다시 패키징.
    """

    def __init__(self, hwpx_path: str):
        self.path = Path(hwpx_path)
        self._zip_contents: dict[str, bytes] = {}
        self._section_paths: list[str] = []
        self._section_trees: dict[str, etree._ElementTree] = {}
        self._changes: list[str] = []  # 편집 로그

    def load(self) -> "HWPXEditor":
        """HWPX ZIP 전체를 메모리에 로드."""
        with zipfile.ZipFile(self.path, "r") as zf:
            for name in zf.namelist():
                self._zip_contents[name] = zf.read(name)

                # section XML 파싱
                if re.search(r'section\d+\.xml$', name) and "Contents" in name:
                    self._section_paths.append(name)
                    root = etree.fromstring(self._zip_contents[name])
                    self._section_trees[name] = etree.ElementTree(root)

        self._section_paths.sort()
        return self

    def save(self, output_path: str) -> None:
        """편집된 HWPX를 새 파일로 저장."""
        # section XML 업데이트
        for sec_path, tree in self._section_trees.items():
            root = tree.getroot()
            etree.indent(root, space="  ")
            self._zip_contents[sec_path] = etree.tostring(
                root, pretty_print=True, xml_declaration=True,
                encoding="UTF-8")

        # ZIP 재패키징 (원본과 동일한 순서 유지)
        out = Path(output_path)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in self._zip_contents.items():
                # mimetype은 반드시 ZIP_STORED (HWPX/OPF 스펙 요구사항)
                if name == "mimetype":
                    zf.writestr(name, data, compress_type=zipfile.ZIP_STORED)
                else:
                    zf.writestr(name, data)

        print(f"✅ {out}", file=sys.stderr)
        if self._changes:
            for ch in self._changes:
                print(f"   {ch}", file=sys.stderr)

    # ── 편집 작업들 ──────────────────────────────────────────────

    def _get_content_paragraphs(self, section_idx: int = 0
                                  ) -> tuple[etree._Element, list]:
        """섹션의 콘텐츠 문단들을 반환 (secPr/header-footer 제외).

        Returns: (root element, list of content paragraph elements)
        """
        sec_path = self._section_paths[section_idx]
        root = self._section_trees[sec_path].getroot()
        all_paras = root.findall(_hp("p"))

        content_paras = []
        for p in all_paras:
            # secPr 문단 건너뛰기
            if p.find(f".//{_hp('secPr')}") is not None:
                continue
            # header/footer 문단 건너뛰기
            if (p.find(f".//{_hp('header')}") is not None or
                    p.find(f".//{_hp('footer')}") is not None):
                continue
            content_paras.append(p)

        return root, content_paras

    def replace_text(self, find: str, replace: str,
                     section_idx: int = 0, regex: bool = False) -> int:
        """텍스트 찾아 바꾸기.

        모든 hp:t 요소에서 find → replace 수행.

        Args:
            find: 찾을 텍스트 (또는 정규식)
            replace: 바꿀 텍스트
            section_idx: 대상 섹션 인덱스
            regex: True면 정규식 사용

        Returns: 변경된 횟수
        """
        sec_path = self._section_paths[section_idx]
        root = self._section_trees[sec_path].getroot()

        count = 0
        for t_elem in root.iter(_hp("t")):
            if t_elem.text is None:
                continue
            if regex:
                new_text, n = re.subn(find, replace, t_elem.text)
            else:
                n = t_elem.text.count(find)
                new_text = t_elem.text.replace(find, replace)
            if n > 0:
                t_elem.text = new_text
                count += n

        if count > 0:
            self._changes.append(
                f"replace_text: '{find}' → '{replace}' ({count} occurrences)")
        return count

    def delete_block(self, index: int, section_idx: int = 0) -> bool:
        """인덱스로 블록(문단) 삭제.

        Args:
            index: 콘텐츠 문단 인덱스 (0-based, secPr/hf 제외)
            section_idx: 대상 섹션

        Returns: 성공 여부
        """
        root, content_paras = self._get_content_paragraphs(section_idx)

        if index < 0 or index >= len(content_paras):
            print(f"WARNING: Block index {index} out of range "
                  f"(0-{len(content_paras) - 1})", file=sys.stderr)
            return False

        target = content_paras[index]
        root.remove(target)
        self._changes.append(f"delete_block: index={index}")
        return True

    def insert_block(self, index: int, block_json: dict,
                     section_idx: int = 0) -> bool:
        """지정 위치에 새 블록 삽입.

        section_builder를 사용하여 블록 JSON → XML 변환 후 삽입.

        Args:
            index: 삽입 위치 (콘텐츠 문단 인덱스)
            block_json: 블록 정의 (section_builder 호환 JSON)
            section_idx: 대상 섹션
        """
        root, content_paras = self._get_content_paragraphs(section_idx)

        # section_builder로 임시 섹션 생성하여 문단 추출
        from section_builder import build_section, IDGen
        idgen = IDGen()
        temp_json = {"blocks": [block_json], "auto_spacing": False}
        temp_sec = build_section(temp_json)

        # temp_sec에서 secPr 문단 이후의 문단들 추출
        new_paras = []
        for p in temp_sec.findall(_hp("p")):
            if p.find(f".//{_hp('secPr')}") is not None:
                continue
            new_paras.append(p)

        if not new_paras:
            print("WARNING: No paragraphs generated from block_json",
                  file=sys.stderr)
            return False

        # 삽입 위치 결정
        all_paras = list(root)
        if index >= len(content_paras):
            # 끝에 추가
            insert_after = content_paras[-1] if content_paras else all_paras[-1]
            parent_idx = list(root).index(insert_after) + 1
        else:
            target = content_paras[index]
            parent_idx = list(root).index(target)

        for i, new_p in enumerate(new_paras):
            root.insert(parent_idx + i, new_p)

        self._changes.append(
            f"insert_block: index={index}, type={block_json.get('type', 'text')}")
        return True

    def update_block_text(self, index: int, new_text: str,
                          section_idx: int = 0) -> bool:
        """블록의 텍스트를 수정 (서식 유지).

        첫 번째 run의 hp:t 텍스트만 교체.
        """
        root, content_paras = self._get_content_paragraphs(section_idx)

        if index < 0 or index >= len(content_paras):
            print(f"WARNING: Block index {index} out of range",
                  file=sys.stderr)
            return False

        target = content_paras[index]
        # 첫 번째 run의 첫 번째 t 요소 수정
        for run in target.findall(_hp("run")):
            for t_elem in run.findall(_hp("t")):
                old_text = t_elem.text or ""
                t_elem.text = new_text
                self._changes.append(
                    f"update_block: index={index}, "
                    f"'{old_text[:30]}...' → '{new_text[:30]}...'")
                return True

        return False

    def update_block(self, index: int, block_json: dict,
                     section_idx: int = 0) -> bool:
        """블록을 완전 교체 (delete + insert).

        원본 블록의 서식 대신 block_json의 서식을 사용.
        """
        root, content_paras = self._get_content_paragraphs(section_idx)

        if index < 0 or index >= len(content_paras):
            return False

        # 원본 블록의 위치 확인
        target = content_paras[index]
        parent_idx = list(root).index(target)

        # 새 블록 생성
        from section_builder import build_section, IDGen
        idgen = IDGen()
        temp_json = {"blocks": [block_json], "auto_spacing": False}
        temp_sec = build_section(temp_json)

        new_paras = [
            p for p in temp_sec.findall(_hp("p"))
            if p.find(f".//{_hp('secPr')}") is None
        ]

        if not new_paras:
            return False

        # 원본 제거
        root.remove(target)

        # 새 블록 삽입
        for i, new_p in enumerate(new_paras):
            root.insert(parent_idx + i, new_p)

        self._changes.append(
            f"update_block: index={index}, new_type={block_json.get('type', 'text')}")
        return True

    def reorder_blocks(self, new_order: list[int],
                       section_idx: int = 0) -> bool:
        """블록 순서 변경.

        Args:
            new_order: 새 순서의 인덱스 배열 (예: [2, 0, 1, 3])
        """
        root, content_paras = self._get_content_paragraphs(section_idx)

        if sorted(new_order) != list(range(len(content_paras))):
            print("WARNING: new_order must be a permutation of all block indices",
                  file=sys.stderr)
            return False

        # 모든 콘텐츠 문단의 부모 내 위치를 기록
        all_children = list(root)
        first_content_idx = all_children.index(content_paras[0])

        # 콘텐츠 문단 제거
        for p in content_paras:
            root.remove(p)

        # 새 순서로 삽입
        for i, idx in enumerate(new_order):
            root.insert(first_content_idx + i, content_paras[idx])

        self._changes.append(f"reorder_blocks: {new_order}")
        return True

    def update_header_footer(self, hf_type: str = "header",
                              text: str = None,
                              section_idx: int = 0) -> bool:
        """머리말 또는 꼬리말의 텍스트를 수정.

        Args:
            hf_type: "header" 또는 "footer"
            text: 새 텍스트 ({{page}}, {{total_pages}} 플레이스홀더 지원)
        """
        if text is None:
            return False

        sec_path = self._section_paths[section_idx]
        root = self._section_trees[sec_path].getroot()

        hf_el = root.find(f".//{_hp(hf_type)}")
        if hf_el is None:
            print(f"WARNING: No {hf_type} found in section {section_idx}",
                  file=sys.stderr)
            return False

        # subList → p → run → t 수정
        sublist = hf_el.find(_hp("subList"))
        if sublist is None:
            return False

        inner_p = sublist.find(_hp("p"))
        if inner_p is None:
            return False

        # 기존 run 삭제
        for run in inner_p.findall(_hp("run")):
            inner_p.remove(run)

        # 새 run 생성 (autoNum 플레이스홀더 처리)
        charPr = "1"  # 기본 머리말/꼬리말 charPr
        run = etree.SubElement(inner_p, _hp("run"))
        run.set("charPrIDRef", charPr)

        # {{page}} / {{total_pages}} 파싱
        import re as _re
        pattern = r'\{\{(page|total_pages|page_count)\}\}'
        last_end = 0
        for m in _re.finditer(pattern, text):
            if m.start() > last_end:
                t = etree.SubElement(run, _hp("t"))
                t.text = text[last_end:m.start()]
            placeholder = m.group(1)
            ctrl = etree.SubElement(run, _hp("ctrl"))
            autonum = etree.SubElement(ctrl, _hp("autoNum"))
            autonum.set("num", "1")
            if placeholder == "page":
                autonum.set("numType", "PAGE")
            else:
                autonum.set("numType", "TOTAL_PAGE")
            fmt = etree.SubElement(autonum, _hp("autoNumFormat"))
            fmt.set("type", "DIGIT")
            fmt.set("userChar", "")
            fmt.set("prefixChar", "")
            fmt.set("suffixChar", "")
            fmt.set("supscript", "0")
            etree.SubElement(run, _hp("t"))
            last_end = m.end()
        if last_end < len(text):
            t = etree.SubElement(run, _hp("t"))
            t.text = text[last_end:]

        self._changes.append(f"update_{hf_type}: '{text[:50]}'")
        return True

    def get_block_count(self, section_idx: int = 0) -> int:
        """콘텐츠 블록 수 반환."""
        _, content_paras = self._get_content_paragraphs(section_idx)
        return len(content_paras)

    def get_block_text(self, index: int, section_idx: int = 0) -> str:
        """특정 블록의 텍스트 반환."""
        _, content_paras = self._get_content_paragraphs(section_idx)
        if index < 0 or index >= len(content_paras):
            return ""

        texts = []
        for t_elem in content_paras[index].iter(_hp("t")):
            if t_elem.text:
                texts.append(t_elem.text)
        return "".join(texts)

    def apply_operations(self, operations: list[dict]) -> int:
        """편집 명령 리스트를 순차 실행.

        Returns: 성공한 작업 수
        """
        success = 0
        for op in operations:
            op_type = op.get("op", "")
            sec = op.get("section", 0)

            if op_type == "replace_text":
                n = self.replace_text(
                    op["find"], op["replace"],
                    section_idx=sec, regex=op.get("regex", False))
                if n > 0:
                    success += 1

            elif op_type == "delete_block":
                if self.delete_block(op["index"], section_idx=sec):
                    success += 1

            elif op_type == "insert_block":
                if self.insert_block(op["index"], op["block"], section_idx=sec):
                    success += 1

            elif op_type == "update_block":
                if "text" in op and "block" not in op:
                    # 텍스트만 수정
                    if self.update_block_text(op["index"], op["text"],
                                               section_idx=sec):
                        success += 1
                elif "block" in op:
                    # 블록 전체 교체
                    if self.update_block(op["index"], op["block"],
                                          section_idx=sec):
                        success += 1

            elif op_type == "update_header":
                if self.update_header_footer("header", op.get("text"),
                                              section_idx=sec):
                    success += 1

            elif op_type == "update_footer":
                if self.update_header_footer("footer", op.get("text"),
                                              section_idx=sec):
                    success += 1

            elif op_type == "reorder_blocks":
                if self.reorder_blocks(op["order"], section_idx=sec):
                    success += 1

            else:
                print(f"WARNING: Unknown operation '{op_type}'",
                      file=sys.stderr)

        return success


# ── CLI ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="HWPX 문서 편집기")
    parser.add_argument("input", help="입력 HWPX 파일 경로")
    parser.add_argument("--output", "-o", required=True,
                        help="출력 HWPX 파일 경로")

    # 단일 편집 작업들
    parser.add_argument("--replace", nargs=2, metavar=("FIND", "REPLACE"),
                        help="텍스트 찾아 바꾸기")
    parser.add_argument("--regex", action="store_true",
                        help="--replace에 정규식 사용")
    parser.add_argument("--delete-block", type=int, metavar="INDEX",
                        help="블록 삭제 (인덱스)")
    parser.add_argument("--insert-text", nargs=2,
                        metavar=("INDEX", "TEXT"),
                        help="텍스트 블록 삽입 (인덱스, 텍스트)")

    # JSON 편집 스크립트
    parser.add_argument("--edit-json", metavar="JSON_FILE",
                        help="편집 명령 JSON 파일 경로")

    args = parser.parse_args()

    if not Path(args.input).is_file():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    editor = HWPXEditor(args.input)
    editor.load()

    # 단일 작업 실행
    if args.replace:
        editor.replace_text(args.replace[0], args.replace[1],
                           regex=args.regex)
    if args.delete_block is not None:
        editor.delete_block(args.delete_block)
    if args.insert_text:
        idx = int(args.insert_text[0])
        text = args.insert_text[1]
        editor.insert_block(idx, {"type": "text", "text": text})

    # JSON 스크립트 실행
    if args.edit_json:
        json_path = Path(args.edit_json)
        if not json_path.is_file():
            print(f"Error: Edit JSON not found: {json_path}",
                  file=sys.stderr)
            sys.exit(1)
        with open(json_path, "r", encoding="utf-8") as f:
            edit_data = json.load(f)
        ops = edit_data.get("operations", [])
        success = editor.apply_operations(ops)
        print(f"Applied {success}/{len(ops)} operations", file=sys.stderr)

    editor.save(args.output)


if __name__ == "__main__":
    main()
