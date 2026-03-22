# HWPX Skill CHANGELOG

## 현재 상태
- 버전: v1.4 (P1: 머리말/꼬리말 + 하이퍼링크 + 각주/미주)
- Git: https://github.com/Victor-jh/hwpxskill (forked from Canine89/hwpxskill)
- Cowork 경로: ~/HWPX Skill Dev
- 스크립트: build_hwpx.py, analyze_template.py, section_builder.py, create_document.py, property_registry.py, diff_docs.py, validate.py, page_guard.py, text_extract.py, office/unpack.py, office/pack.py
- 템플릿: base, gonmun, report, minutes, proposal, **kcup**
- JSON 타입: 15 기본 + 16 KCUP 전용 = 31개
- 동적 서식: charPr/paraPr/borderFill을 JSON dict로 인라인 지정 가능

## 2026-03-22 (Cowork 세션 #4) — P1: 머리말/꼬리말 + 하이퍼링크 + 각주/미주

### 머리말/꼬리말 (header/footer)
- JSON 최상위 `"header"` / `"footer"` 키로 정의
- `{{page}}` → `hp:autoNum numType="PAGE"` (현재 쪽 번호)
- `{{total_pages}}` → `hp:autoNum numType="TOTAL_PAGE"` (전체 쪽수)
- align: left/center/right (동적 paraPr 레지스트리 연동)
- applyPageType: BOTH/EVEN/ODD (기본 BOTH)
- 다중 섹션에서도 섹션별 또는 전역 header/footer 지원
- XML 구조: `hp:ctrl > hp:header/footer > hp:subList > hp:p` (hp 네임스페이스)

### 하이퍼링크 (hyperlink)
- `hyperlink` 블록 타입 추가 (기본 타입 12→13개)
- `url`: 대상 URL (필수)
- `text`: 표시 텍스트 (생략 시 URL 표시)
- `prefix` / `suffix`: 링크 앞뒤 일반 텍스트
- XML 구조: `hp:fieldBegin type="HYPERLINK"` + `hp:parameters` + `hp:fieldEnd`
- Command 파라미터: URL 내 콜론 자동 이스케이프 (`\:`)

### 각주/미주 (footnote/endnote)
- `text_footnote` / `text_endnote` / `footnote` 블록 타입 추가 (기본 타입 13→15개)
- `text`: 본문 텍스트 (각주 마커가 끝에 붙음)
- `footnote` / `endnote`: 주석 내용
- 번호 자동 증가 (문서 내 순차 매김)
- XML 구조: `hp:ctrl > hp:footNote/endNote > hp:subList > hp:p` (autoNum FOOTNOTE/ENDNOTE)
- styleIDRef=14 (각주) / styleIDRef=15 (미주) 자동 매핑

### 검증 통과
- 머리말/꼬리말 빌드 + validate ✅
- 하이퍼링크 3개 (prefix/suffix 포함) 빌드 + validate ✅
- 각주 2개 + 미주 1개 빌드 + validate ✅
- P1 통합 테스트 (header+footer+hyperlink+footnote+endnote) ✅
- 기존 블록 회귀 테스트 ✅

### 산출물
- p1_full_test.hwpx — P1 통합 테스트 문서
- 한컴독스 렌더링 검증 완료 ✅ (머리말/꼬리말, 하이퍼링크, 각주/미주 모두 정상)

## 2026-03-22 (Cowork 세션 #3) — 이미지 삽입 + 동적 서식 레지스트리 + 다중 섹션

### 이미지 삽입 (section_builder.py + build_hwpx.py)
- `image` 블록 타입 신규 추가 (기본 타입 11→12개)
  - `src`: 이미지 파일 경로 (PNG/JPEG/GIF/BMP)
  - `width`, `height`: mm 단위 크기 지정 (생략 시 원본 비율 자동 계산)
  - `align`: 정렬 (`left`/`center`/`right`)
- Pillow 없이 순수 Python으로 PNG/JPEG/GIF/BMP 헤더에서 해상도 추출
- BinData 연동: 이미지 파일 → BinData/ 폴더 복사, content.hpf manifest 등록
- 이미지 사이드카 JSON (`_images.json`) 자동 생성/전달
- `hc:img` + `hp:shapeObject` + `hp:pic` + `hp:inMargin` XML 생성

### PropertyRegistry — 동적 charPr/paraPr/borderFill 레지스트리 (property_registry.py 신규)
- LLM JSON에서 `"charPr": {"bold": true, "size": 14, "color": "#FF0000"}` 형태로 인라인 서식 지정
- 템플릿 header.xml의 기존 ID를 자동 탐색 → 충돌 없는 새 ID 동적 할당
- 스펙 정규화 + 캐싱: 동일 스펙은 같은 ID 재사용 (중복 방지)
- charPr 지원 속성: size, bold, italic, color, fontRef, spacing, underline, strikeout, shadeColor, height
- paraPr 지원 속성: align, lineSpacing, lineSpacingType, margin (dict), indent, left, right, prev, next
  - hp:switch/case/default 패턴 자동 생성 (한컴 호환)
  - hc 네임스페이스 마진 요소 (intent/left/right/prev/next) 생성
- borderFill 지원 속성: bg, border, borderWidth, borderColor, 개별 사이드 보더
- `resolve_font(face)`: 새 폰트 자동 등록 (7개 언어 카테고리)
- JSON 사이드카 직렬화 (`_registry.json`): section_builder → build_hwpx 파이프라인 연동
- `apply(header_path)`: header.xml에 동적 엔트리 삽입, itemCnt 자동 업데이트
- **한컴독스 렌더링 교차검증 완료** ✅

### 다중 섹션 지원 (create_document.py + build_hwpx.py)
- JSON `"sections"` 키로 다중 섹션 정의 가능
- section_builder.py: `--output-dir` 모드로 section0.xml, section1.xml, ... 개별 생성
- build_hwpx.py: `--section-dir` 모드로 다중 섹션 빌드
- content.hpf manifest/spine 동적 등록 (`_register_sections_in_hpf()`)

### 기타 개선
- build_hwpx.py: `.DS_Store`, `Thumbs.db` 등 비문서 파일 자동 제외
- section_builder.py: `hc` 네임스페이스 추가 (이미지/레지스트리 공용)
- section_builder.py: 모든 블록 핸들러에 `_resolve_cp()`, `_resolve_pp()`, `_resolve_bf()` 통합

### 검증 통과
- 이미지 삽입 end-to-end (PNG 파일 → HWPX → 한컴독스 렌더링) ✅
- 동적 charPr 5종 (빨강볼드14pt, 파란이탤릭12pt, 초록밑줄11pt, 혼합run 2종) ✅
- 동적 paraPr 2종 (가운데정렬+줄간격200%, 왼쪽여백3000) ✅
- 스펙 캐싱 (동일 스펙 → 동일 ID 재사용) ✅
- 다중 섹션 빌드 구조 검증 ✅
- **한컴독스 Web 에디터 렌더링 정상 확인** ✅

### 산출물
- property_registry.py — 700+ 라인, 동적 서식 레지스트리 핵심 모듈
- 동적서식_검증.hwpx — 동적 서식 교차검증용 테스트 문서

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
- [x] 이미지 삽입 ✅ (image 블록 타입 + BinData 연동)
- [x] 동적 서식 레지스트리 ✅ (PropertyRegistry, 한컴독스 교차검증 완료)
- [x] 다중 섹션 지원 ✅ (sections JSON + section-dir 빌드)
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
