# HWPX Skill CHANGELOG

## 현재 상태
- 버전: v1.2 (KCUP 스타일 + 원커맨드 파이프라인)
- Git: https://github.com/Victor-jh/hwpxskill (forked from Canine89/hwpxskill)
- Cowork 경로: ~/HWPX Skill Dev
- 스크립트: build_hwpx.py, analyze_template.py, section_builder.py, create_document.py, diff_docs.py, validate.py, page_guard.py, text_extract.py, office/unpack.py, office/pack.py
- 템플릿: base, gonmun, report, minutes, proposal, **kcup**
- JSON 타입: 11 기본 + 16 KCUP 전용 = 27개

## 2026-03-21 (Cowork 세션 #2) — KCUP 스타일 구현
### KCUP 블록 타입 추가 (section_builder.py)
- 16개 KCUP 전용 타입 구현 — 팀장 대응용 보고서 스타일(v1.1 스펙)
  - kcup_box (□항목 제목), kcup_o (o항목 키워드+본문), kcup_o_plain, kcup_o_heading
  - kcup_dash (-항목), kcup_dash_plain, kcup_numbered (번호항목)
  - kcup_note (※주석), kcup_attachment (붙임), kcup_pointer (▶가리킴)
  - kcup_mixed_run (다중 run 직접 지정)
  - spacing 변형: kcup_box_spacing, kcup_o_spacing, kcup_o_heading_spacing, kcup_dash_spacing
- KCUP_CP / KCUP_PP 상수 딕셔너리 — charPr/paraPr ID 매핑
- BODY_WIDTH_MAP — 템플릿별 본문 폭 (kcup=48190, 기본=42520)
- multi-run 지원: 하나의 paragraph에 서로 다른 charPr을 가진 복수 `<hp:run>` 생성

### auto_spacing 자동 간격줄 삽입
- 블록 타입 전이 규칙 기반 state machine 구현
  - box→다음 항목: box_spacing (14pt, 160%)
  - mid/detail→다음 항목: o_spacing (10pt, 100%)
  - mid_heading→mid_heading: heading_spacing (14pt, 100%)
  - note/signature 등: passthrough (간격 삽입 안 함)
- JSON `"auto_spacing": true` 플래그로 활성화
- 수동 spacing 141줄 → auto_spacing 67줄 (53% 감소)

### create_document.py 원커맨드 파이프라인 (신규 작성)
- 레거시 python-hwpx 버전 완전 교체
- JSON → section_builder.py → build_hwpx.py → validate.py 한 번에 실행
- `--style kcup` / `--template` 옵션으로 스타일·템플릿 지정
- STYLE_TEMPLATE_MAP으로 스타일↔템플릿 자동 매핑

### KCUP 템플릿 (templates/kcup/)
- header.xml — 38 charPr, 32 paraPr, 3 borderFill, 5 fonts
- section0.xml — secPr (A4, 20mm 여백, body_width=48190)

### header.xml 16건 수정 (렌더링 오류 수정)
- fontCnt: 2→5 (7개 lang category 모두)
- charPr 15/17/18: `<hh:bold/>` 누락 추가
- paraPr 26: intent=-2319 (o항목 hanging indent)
- paraPr 28: left=252 (□항목 좌측 마진)
- paraPr 30: intent=-3103 (-항목 hanging indent)
- paraPr 31: lineSpacing 160→100% (간격줄)

### 검증 통과
- 기존 11개 타입 회귀 테스트 ✅
- KCUP 16개 타입 빌드·구조검증 ✅
- auto_spacing=false / auto_spacing=true 비교 ✅
- mid_heading 연속 spacing 테스트 ✅
- 원커맨드 파이프라인 end-to-end ✅
- **한컴독스 렌더링 정상 확인** ✅

### 산출물
- kcup_report_v3_fixed.hwpx — header.xml 수정 반영, 한컴독스 렌더링 확인
- kcup_report_v4_auto.hwpx — auto_spacing 적용 최종본
- kcup_report_auto.json — auto_spacing용 간결 JSON (67줄)

## 2026-03-21 (Cowork 세션 #1) — 기반 복원
### 복원/추가
- section_builder.py 재작성 — JSON → section0.xml 동적 생성 (11개 타입)
  - text, empty, heading, bullet, numbered, indent, note, table, label_value, signature, pagebreak
  - 다중 run, colRatios, 셀 병합(colSpan/rowSpan), 셀 내 다중 문단 지원
- diff_docs.py 재작성 — 텍스트 unified diff + --structure 구조 비교

### 검증 통과
- section_builder.py 전체 11개 타입 → build_hwpx.py → validate.py ✅
- diff_docs.py 텍스트 diff + 구조 비교 ✅

### TODO
- [x] Git commit + push ✅ (8d63b9e, dca6c9b)
- [x] SKILL.md 업데이트 ✅ (원커맨드, KCUP 블록 타입, auto_spacing 문서화)
- [x] .gitignore 추가 ✅
- [ ] 표 셀 병합 실무 문서 추가 검증
- [ ] 다중 섹션 지원 (L2 돌파)
- [ ] 이미지 삽입 (L3 돌파)
- [ ] StyleProfile 분리 (기존 템플릿으로 검증 후)
- [ ] 플러그인 패키징

## v1.1
### 주요 기능
- XML-first 워크플로우
- 레퍼런스 복원 우선 모드 (99% 구조 복원 + 쪽수 동일 필수)
- page_guard.py 필수 게이트
- 5개 템플릿 (base/gonmun/report/minutes/proposal)
- linesegarray 자동 strip (build_hwpx.py)
- --reference 옵션 BinData 이미지 복사

## 동기화 원칙
- Victor-jh fork = Single Source of Truth
- upstream 반영: GitHub Sync fork
- Cowork 로컬 = Git working directory (직접 수정 → commit → push)
