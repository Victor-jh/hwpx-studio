#!/usr/bin/env python3
"""create_document.py — 원커맨드 HWPX 문서 생성 파이프라인.

JSON 입력 + 스타일/템플릿 지정 → section0.xml 생성 → HWPX 빌드 → 검증까지 한 번에.

Usage:
    # KCUP 스타일로 문서 생성
    python3 create_document.py input.json --style kcup --output result.hwpx

    # 템플릿 지정 (style 미지정 시 template만 사용)
    python3 create_document.py input.json --template report --output result.hwpx

    # 검증 스킵
    python3 create_document.py input.json --style kcup --output result.hwpx --no-validate

내부 동작:
    1. JSON 로드
    2. section_builder.py로 section0.xml 생성
    3. build_hwpx.py로 HWPX 패키징
    4. validate.py로 구조 검증
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
# 패키지 모드: src/hwpx_studio/templates/, Skill 모드: scripts/../templates/
_PKG_TEMPLATES = SCRIPT_DIR / "templates"
_SKILL_TEMPLATES = SCRIPT_DIR.parent / "templates"
TEMPLATES_DIR = _PKG_TEMPLATES if _PKG_TEMPLATES.is_dir() else _SKILL_TEMPLATES

STYLE_TEMPLATE_MAP = {
    "kcup": "kcup",
    "gonmun": "gonmun",
    "report": "report",
    "minutes": "minutes",
    "proposal": "proposal",
}


def resolve_template(style=None, template=None):
    """style 또는 template에서 실제 템플릿 이름을 결정."""
    if style:
        tpl = STYLE_TEMPLATE_MAP.get(style)
        if tpl is None:
            avail = ", ".join(STYLE_TEMPLATE_MAP.keys())
            print(f"ERROR: Unknown style '{style}'. Available: {avail}",
                  file=sys.stderr)
            sys.exit(1)
        return tpl
    return template


def run_step(cmd, step_name):
    """서브프로세스 실행. 실패 시 에러 출력 후 종료."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FAIL at [{step_name}]:", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        sys.exit(1)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="JSON → HWPX 원커맨드 파이프라인")
    parser.add_argument("json_file", help="JSON 정의 파일 경로")
    parser.add_argument("--style", "-s",
                        help="스타일 이름 (kcup, gonmun, report 등)")
    parser.add_argument("--template", "-t",
                        help="템플릿 이름 (style 미지정 시 직접 지정)")
    parser.add_argument("--output", "-o", required=True,
                        help="출력 .hwpx 파일 경로")
    parser.add_argument("--base-section",
                        help="secPr 복사용 base section0.xml 경로")
    parser.add_argument("--title", help="문서 제목 메타데이터")
    parser.add_argument("--creator", help="작성자 메타데이터")
    parser.add_argument("--header",
                        help="KCUP header 매핑 이름 (cost, ref3, mtg2)")
    parser.add_argument("--no-validate", action="store_true",
                        help="validate 단계 스킵")
    args = parser.parse_args()

    json_path = Path(args.json_file).resolve()
    if not json_path.exists():
        print(f"ERROR: JSON not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output).resolve()
    template_name = resolve_template(args.style, args.template)

    # JSON에서 template fallback 읽기
    with open(json_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)
    if not template_name:
        json_template = json_data.get("template")
        if json_template and json_template != "base":
            template_name = json_template

    # base section 결정
    base_section = None
    if args.base_section:
        base_section = Path(args.base_section).resolve()
    elif template_name:
        candidate = TEMPLATES_DIR / template_name / "section0.xml"
        if candidate.exists():
            base_section = candidate
    is_multi = "sections" in json_data

    if is_multi:
        _run_multi_section(json_path, output_path, template_name,
                           base_section, args)
    else:
        _run_single_section(json_path, output_path, template_name,
                            base_section, args)


def _run_single_section(json_path, output_path, template_name,
                         base_section, args):
    """단일 섹션 파이프라인."""
    with tempfile.NamedTemporaryFile(
            suffix=".xml", prefix="section0_", delete=False) as tmp:
        section_tmp = Path(tmp.name)

    sb_cmd = [
        sys.executable, str(SCRIPT_DIR / "section_builder.py"),
        str(json_path),
        "-o", str(section_tmp),
    ]
    if template_name:
        sb_cmd += ["-t", template_name]
    if base_section:
        sb_cmd += ["--base-section", str(base_section)]
    if args.header:
        sb_cmd += ["--header", args.header]

    run_step(sb_cmd, "section_builder")

    # 이미지 매니페스트 자동 탐색
    images_json = section_tmp.parent / f"{section_tmp.stem}_images.json"

    try:
        bh_cmd = [
            sys.executable, str(SCRIPT_DIR / "build_hwpx.py"),
            "--section", str(section_tmp),
            "--output", str(output_path),
        ]
        if template_name:
            bh_cmd += ["--template", template_name]
        if args.title:
            bh_cmd += ["--title", args.title]
        if args.creator:
            bh_cmd += ["--creator", args.creator]
        if images_json.exists():
            bh_cmd += ["--images-json", str(images_json)]

        run_step(bh_cmd, "build_hwpx")

        if not args.no_validate:
            val_cmd = [
                sys.executable, str(SCRIPT_DIR / "validate.py"),
                str(output_path),
            ]
            run_step(val_cmd, "validate")

        print(f"✅ {output_path}", file=sys.stderr)
        info = []
        if args.style:
            info.append(f"style={args.style}")
        if template_name:
            info.append(f"template={template_name}")
        if images_json.exists():
            info.append("images=yes")
        if info:
            print(f"   {' '.join(info)}", file=sys.stderr)

    finally:
        section_tmp.unlink(missing_ok=True)
        if images_json.exists():
            images_json.unlink(missing_ok=True)


def _run_multi_section(json_path, output_path, template_name,
                        base_section, args):
    """다중 섹션 파이프라인."""
    with tempfile.TemporaryDirectory(prefix="sections_") as sec_dir:
        sec_dir = Path(sec_dir)

        sb_cmd = [
            sys.executable, str(SCRIPT_DIR / "section_builder.py"),
            str(json_path),
            "-o", str(sec_dir),
        ]
        if template_name:
            sb_cmd += ["-t", template_name]
        if base_section:
            sb_cmd += ["--base-section", str(base_section)]
        if args.header:
            sb_cmd += ["--header", args.header]

        run_step(sb_cmd, "section_builder (multi)")

        # 이미지 매니페스트 자동 탐색
        images_json = sec_dir / "_images.json"

        bh_cmd = [
            sys.executable, str(SCRIPT_DIR / "build_hwpx.py"),
            "--section-dir", str(sec_dir),
            "--output", str(output_path),
        ]
        if template_name:
            bh_cmd += ["--template", template_name]
        if args.title:
            bh_cmd += ["--title", args.title]
        if args.creator:
            bh_cmd += ["--creator", args.creator]
        if images_json.exists():
            bh_cmd += ["--images-json", str(images_json)]

        run_step(bh_cmd, "build_hwpx (multi)")

        if not args.no_validate:
            val_cmd = [
                sys.executable, str(SCRIPT_DIR / "validate.py"),
                str(output_path),
            ]
            run_step(val_cmd, "validate")

        sec_count = len(list(sec_dir.glob("section*.xml")))
        print(f"✅ {output_path} ({sec_count} sections)", file=sys.stderr)
        info = []
        if args.style:
            info.append(f"style={args.style}")
        if template_name:
            info.append(f"template={template_name}")
        if info:
            print(f"   {' '.join(info)}", file=sys.stderr)


if __name__ == "__main__":
    main()
