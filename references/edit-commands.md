# 편집 명령 레퍼런스 (edit_document.py)

---

## CLI 사용법

```bash
source "$VENV"

# 텍스트 찾아 바꾸기
python3 "$SKILL_DIR/src/hwpx_studio/edit_document.py" doc.hwpx \
  --replace "원본텍스트" "새텍스트" -o edited.hwpx

# 정규식 찾아 바꾸기
python3 "$SKILL_DIR/src/hwpx_studio/edit_document.py" doc.hwpx \
  --replace "2024년 \d+월" "2025년 3월" --regex -o edited.hwpx

# 블록 삭제 (인덱스 5번)
python3 "$SKILL_DIR/src/hwpx_studio/edit_document.py" doc.hwpx \
  --delete-block 5 -o edited.hwpx

# 텍스트 블록 삽입 (인덱스 3 위치에)
python3 "$SKILL_DIR/src/hwpx_studio/edit_document.py" doc.hwpx \
  --insert-text 3 "새로 삽입할 문단" -o edited.hwpx

# JSON 편집 스크립트로 복합 작업
python3 "$SKILL_DIR/src/hwpx_studio/edit_document.py" doc.hwpx \
  --edit-json edit_commands.json -o edited.hwpx
```

---

## JSON 편집 스크립트 형식

```json
{
  "operations": [
    {"op": "replace_text", "find": "원본", "replace": "새것"},
    {"op": "replace_text", "find": "2024년 \\d+월", "replace": "2025년 3월", "regex": true},
    {"op": "insert_block", "index": 3, "block": {"type": "text", "text": "새 문단"}},
    {"op": "delete_block", "index": 5},
    {"op": "update_block_text", "index": 2, "text": "수정된 텍스트"},
    {"op": "update_block", "index": 4, "block": {"type": "heading", "text": "새 제목", "level": 2}},
    {"op": "reorder_blocks", "order": [0, 2, 1, 3, 4]},
    {"op": "update_header_footer", "target": "header", "text": "새 머리말", "align": "center"},
    {"op": "update_header_footer", "target": "footer", "text": "{{page}} / {{total_pages}}"}
  ]
}
```

---

## 지원 편집 작업 (7종)

### replace_text

```json
{"op": "replace_text", "find": "원본", "replace": "새것"}
{"op": "replace_text", "find": "\\d{4}년", "replace": "2026년", "regex": true}
```

| 필드 | 필수 | 설명 |
|------|------|------|
| find | Y | 검색 문자열 또는 정규식 패턴 |
| replace | Y | 교체 문자열 |
| regex | N | true면 정규식으로 처리 (기본 false) |

### insert_block

```json
{"op": "insert_block", "index": 3, "block": {"type": "text", "text": "새 문단"}}
{"op": "insert_block", "index": 0, "block": {"type": "heading", "text": "제목", "level": 1}}
```

`block`은 section_builder.py 블록 타입 스펙을 따름. 인덱스 위치 앞에 삽입.

### delete_block

```json
{"op": "delete_block", "index": 5}
```

`index`는 `read_document.py` 출력의 blocks 배열 순서와 일치.

### update_block_text

```json
{"op": "update_block_text", "index": 2, "text": "수정된 텍스트"}
```

서식(charPr/paraPr) 보존하며 텍스트 내용만 교체.

### update_block

```json
{"op": "update_block", "index": 4, "block": {"type": "heading", "text": "새 제목", "level": 2}}
```

블록 전체를 새 블록으로 대체.

### reorder_blocks

```json
{"op": "reorder_blocks", "order": [0, 2, 1, 3, 4]}
```

`order`: 새 순서로 재배치할 블록 인덱스 배열.

### update_header_footer

```json
{"op": "update_header_footer", "target": "header", "text": "새 머리말", "align": "center"}
{"op": "update_header_footer", "target": "footer", "text": "{{page}} / {{total_pages}}", "align": "right"}
```

| 필드 | 필수 | 설명 |
|------|------|------|
| target | Y | "header" 또는 "footer" |
| text | Y | 표시 텍스트. `{{page}}`, `{{total_pages}}` 치환 지원 |
| align | N | left/center/right (기본 left) |

---

## Python API

```python
from edit_document import HWPXEditor

editor = HWPXEditor("doc.hwpx")
editor.load()

editor.replace_text("원본", "새것", regex=False)
editor.insert_block(3, {"type": "text", "text": "삽입 문단"})
editor.delete_block(5)
editor.update_block_text(2, "수정 텍스트")
editor.update_header_footer("footer", "{{page}} / {{total_pages}}", align="right")

editor.save("edited.hwpx")  # mimetype ZIP_STORED 자동 보장
```

---

## 핵심 원칙

- **서식 100% 보존**: header.xml, BinData, META-INF 등 편집 대상 외 파일은 원본 그대로
- **mimetype ZIP_STORED**: 재패키징 시 mimetype은 반드시 ZIP_STORED(compress_type=0)
- **인덱스 기준**: `read_document.py` 출력의 blocks 배열 순서와 일치
- **insert_block**: 삽입 블록의 JSON은 section_builder.py 블록 타입 스펙을 따름
- **edit 불가 시**: 새 스타일 추가, secPr 변경, 이미지 삽입 등 ZIP 구조 변경이 필요한 경우 → `unpack.py → XML 직접 수정 → pack.py`
