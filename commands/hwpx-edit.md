---
name: hwpx-edit
description: "기존 HWPX 파일을 인플레이스 편집합니다. 텍스트 교체, 블록 삽입/삭제, 머리말·꼬리말 변경."
argument-hint: "[hwpx-file] [instructions]"
allowed-tools: Read, Write, Edit, Bash
---

# /hwpx-edit 커맨드

기존 HWPX 파일에 인플레이스 편집을 수행한다. 원본 서식을 최대한 보존한다.

## 실행 흐름

1. **인자 파싱**: `$ARGUMENTS`에서 파일 경로와 편집 지시를 분리한다.
   - 예: `report.hwpx 3페이지 제목을 "2026 연간 보고서"로 변경`

2. **먼저 읽기**: `read_document.py`로 현재 구조를 파악한다.

```bash
cd skills/hwpx/scripts && python read_document.py --input <hwpx-file> --pretty
```

3. **편집 경로 선택**:
   - 텍스트 교체/블록 수정 → `edit_document.py` (우선)
   - ZIP 구조 변경 필요 시 → `unpack.py` → XML 직접 수정 → `pack.py`

```bash
# 텍스트 교체
python edit_document.py \
  --input <hwpx-file> \
  --output <output.hwpx> \
  --replace "기존 텍스트" "새 텍스트"

# unpack → 직접 수정 → pack
python office/unpack.py <hwpx-file> /tmp/hwpx-unpacked/
# ... XML 수정 ...
python office/pack.py /tmp/hwpx-unpacked/ <output.hwpx>
```

4. **검증**: 편집 완료 후 반드시 `validate.py`를 실행한다.

```bash
python validate.py <output.hwpx>
```

5. 결과 파일 경로와 변경 내역을 사용자에게 알린다.

## 편집 가능한 작업 목록

- 텍스트 찾아 바꾸기
- 특정 블록 삭제 또는 내용 수정
- 머리말·꼬리말 텍스트 변경
- 블록 순서 변경

## 편집 불가 → 생성 경로 전환 기준

아래 경우에는 `/hwpx-create`(레퍼런스 모드)로 전환을 권장한다.
- 내용을 전면 재작성
- 새 스타일/테마 적용
- 이미지 삽입 등 ZIP 구조 대규모 변경

## 스크립트 경로

스크립트는 플러그인의 `skills/hwpx/scripts/` 디렉토리에 위치한다.
`SKILL.md`의 편집 경로 섹션을 함께 참조한다.
