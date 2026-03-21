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
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATES_DIR = SKILL_DIR / "templates"

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
    parser.add_argument("--no-validate", action="store_true",
                        help="validate 단계 스킵")
    args = parser.parse_args()

    json_path = Path(args.json_file).resolve()
    if not json_path.exists():
        print(f"ERROR: JSON not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output).resolve()
    template_name = resolve_template(args.style, args.template)

    # base section 결정
    base_section = None
    if args.base_section:
        base_section = Path(args.base_section).resolve()
    elif template_name:
        candidate = TEMPLATES_DIR / template_name / "section0.xml"
        if candidate.exists():
            base_section = candidate

    # ── Step 1: section_builder.py ──
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

    run_step(sb_cmd, "section_builder")

    try:
        # ── Step 2: build_hwpx.py ──
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

        run_step(bh_cmd, "build_hwpx")

        # ── Step 3: validate.py ──
        if not args.no_validate:
            val_cmd = [
                sys.executable, str(SCRIPT_DIR / "validate.py"),
                str(output_path),
            ]
            result = run_step(val_cmd, "validate")

        # 결과 출력
        print(f"✅ {output_path}", file=sys.stderr)
        info = []
        if args.style:
            info.append(f"style={args.style}")
        if template_name:
            info.append(f"template={template_name}")
        if info:
            print(f"   {' '.join(info)}", file=sys.stderr)

    finally:
        section_tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
