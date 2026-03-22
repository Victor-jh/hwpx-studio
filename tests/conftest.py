"""공통 fixture — 모든 테스트에서 사용."""

import json
import sys
import tempfile
from pathlib import Path

import pytest

# scripts/ 를 import 경로에 추가
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = SKILL_DIR / "templates"


@pytest.fixture
def tmp_dir(tmp_path):
    """각 테스트에 격리된 임시 디렉토리 제공."""
    return tmp_path


@pytest.fixture
def minimal_json(tmp_path):
    """최소 JSON — paragraph 1개."""
    data = {"blocks": [{"type": "paragraph", "text": "테스트 문단입니다."}]}
    p = tmp_path / "minimal.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture
def multi_block_json(tmp_path):
    """다양한 블록 타입을 포함한 JSON."""
    data = {
        "blocks": [
            {"type": "heading", "level": 1, "text": "제목"},
            {"type": "paragraph", "text": "본문 텍스트"},
            {"type": "bullet", "text": "글머리 항목"},
            {"type": "numbered", "text": "번호 항목"},
            {"type": "table", "rows": [
                [{"text": "A1"}, {"text": "B1"}],
                [{"text": "A2"}, {"text": "B2"}],
            ]},
            {"type": "note", "text": "주의사항"},
            {"type": "indent", "text": "들여쓰기 텍스트"},
            {"type": "pagebreak"},
            {"type": "paragraph", "text": "두 번째 페이지"},
        ]
    }
    p = tmp_path / "multi.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture
def hyperlink_json(tmp_path):
    """하이퍼링크 블록."""
    data = {
        "blocks": [
            {"type": "hyperlink", "text": "구글 링크", "url": "https://google.com"},
        ]
    }
    p = tmp_path / "hyperlink.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture
def footnote_json(tmp_path):
    """각주 블록."""
    data = {
        "blocks": [
            {"type": "text_footnote", "text": "본문 텍스트", "footnote": "각주 내용"},
        ]
    }
    p = tmp_path / "footnote.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture
def bookmark_json(tmp_path):
    """북마크 블록."""
    data = {
        "blocks": [
            {"type": "bookmark", "name": "test_bm", "text": "북마크된 텍스트"},
        ]
    }
    p = tmp_path / "bookmark.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture
def label_value_json(tmp_path):
    """label_value 블록."""
    data = {
        "blocks": [
            {"type": "label_value", "label": "담당자", "value": "홍길동"},
        ]
    }
    p = tmp_path / "label_value.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture
def kcup_json(tmp_path):
    """KCUP 전용 블록들."""
    data = {
        "blocks": [
            {"type": "kcup_box", "text": "박스 텍스트"},
            {"type": "kcup_o", "text": "O 항목"},
            {"type": "kcup_dash", "text": "대시 항목"},
            {"type": "kcup_numbered", "number": "1", "text": "번호 항목"},
            {"type": "kcup_note", "text": "비고 사항"},
        ]
    }
    p = tmp_path / "kcup.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p
