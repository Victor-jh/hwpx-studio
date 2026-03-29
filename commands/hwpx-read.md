---
name: hwpx-read
description: "HWPX 파일을 JSON으로 읽어 구조와 내용을 분석합니다."
argument-hint: "[hwpx-file]"
allowed-tools: Read, Bash
---

# /hwpx-read 커맨드

주어진 HWPX 파일을 JSON으로 역변환하여 구조와 내용을 분석한다.

## 실행 흐름

1. **파일 확인**: `$ARGUMENTS`로 전달된 `.hwpx` 파일 경로를 확인한다.
   파일이 없으면 경로를 다시 확인해 달라고 요청한다.

2. **JSON 역변환**: `read_document.py`를 호출해 HWPX → JSON 변환을 수행한다.

```bash
cd skills/hwpx/scripts && python read_document.py \
  --input <hwpx-file> \
  --pretty
```

3. **결과 분석**: 반환된 JSON에서 다음 정보를 요약한다.
   - 블록 수 및 타입별 분포
   - 제목(heading1/2/3) 목록
   - 표 개수 및 크기
   - 머리말·꼬리말 내용
   - 총 텍스트 분량 (단어 수 기준)

4. 분석 결과를 사용자에게 구조화된 형태로 제시한다.
   사용자가 추가 작업(편집·생성)을 원하면 해당 커맨드로 안내한다.

## 텍스트만 추출하는 경우

블록 구조 대신 순수 텍스트만 필요하면 `text_extract.py`를 사용한다.

```bash
python text_extract.py <hwpx-file> --format markdown
```

## 스크립트 경로

스크립트는 플러그인의 `skills/hwpx/scripts/` 디렉토리에 위치한다.
`SKILL.md`의 읽기 경로 섹션을 함께 참조한다.
