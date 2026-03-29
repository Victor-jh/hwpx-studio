# XML 구조 레퍼런스

section0.xml 핵심 구조와 OWPML 태그 사용법.

---

## HWPX 파일 내부 구조

```
document.hwpx (ZIP)
├── mimetype                # "application/hwpml+zip" (ZIP_STORED, 첫 엔트리)
├── META-INF/
│   ├── container.xml
│   ├── container.rdf
│   └── manifest.xml
├── version.xml
├── settings.xml
├── Contents/
│   ├── header.xml          # 스타일 정의 (charPr, paraPr, borderFill, font)
│   ├── section0.xml        # 본문 (메인)
│   ├── section1.xml        # 추가 섹션 (다중 섹션 시)
│   └── content.hpf         # 섹션 목록 매니페스트
└── Preview/
    ├── PrvImage.png
    └── PrvText.txt
```

---

## 네임스페이스

```xml
xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"
xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"
xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core"
```

---

## section0.xml 기본 구조

```xml
<?xml version='1.0' encoding='UTF-8'?>
<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"
        xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">

  <!-- 첫 문단: secPr + colPr 필수 포함 -->
  <hp:p id="1000000001" paraPrIDRef="0" styleIDRef="0"
        pageBreak="0" columnBreak="0" merged="0">
    <hp:run charPrIDRef="0">
      <hp:secPr ...>
        <hp:paperSz width="59528" height="84186" orientation="PORTRAIT"/>
        <hp:paperMargin left="8504" right="8504" top="8504" bottom="8504"
                        header="4252" footer="4252" gutter="0"/>
        <!-- 각주/미주 설정 등 -->
      </hp:secPr>
      <hp:ctrl>
        <hp:colPr id="1" type="NEWSPAPER" layout="LEFT"
                  colCount="1" sameSz="1" sameGap="0"/>
      </hp:ctrl>
    </hp:run>
    <hp:run charPrIDRef="0"><hp:t/></hp:run>
  </hp:p>

  <!-- 일반 문단 -->
  <hp:p id="1000000002" paraPrIDRef="0" styleIDRef="0"
        pageBreak="0" columnBreak="0" merged="0">
    <hp:run charPrIDRef="0">
      <hp:t>본문 내용</hp:t>
    </hp:run>
  </hp:p>

  <!-- 빈 줄 -->
  <hp:p id="1000000003" paraPrIDRef="0" styleIDRef="0"
        pageBreak="0" columnBreak="0" merged="0">
    <hp:run charPrIDRef="0"><hp:t/></hp:run>
  </hp:p>

</hs:sec>
```

---

## 문단 (hp:p)

```xml
<hp:p id="고유ID" paraPrIDRef="문단스타일ID" styleIDRef="0"
      pageBreak="0" columnBreak="0" merged="0">
  <hp:run charPrIDRef="글자스타일ID">
    <hp:t>텍스트</hp:t>
  </hp:run>
</hp:p>
```

- **id**: `1000000001`부터 순차 증가. 문서 내 고유.
- **paraPrIDRef**: header.xml `<hh:paraPr id=N>` 참조
- **charPrIDRef**: header.xml `<hh:charPr id=N>` 참조
- **pageBreak="1"**: 이 문단 앞에서 페이지 나누기

---

## 혼합 런 (서식 혼합)

```xml
<hp:p id="1000000010" paraPrIDRef="0" styleIDRef="0"
      pageBreak="0" columnBreak="0" merged="0">
  <hp:run charPrIDRef="0"><hp:t>일반 텍스트 </hp:t></hp:run>
  <hp:run charPrIDRef="7"><hp:t>볼드 텍스트</hp:t></hp:run>
  <hp:run charPrIDRef="0"><hp:t> 다시 일반</hp:t></hp:run>
</hp:p>
```

---

## 표 (hp:tbl)

```xml
<hp:p id="1000000020" paraPrIDRef="0" styleIDRef="0"
      pageBreak="0" columnBreak="0" merged="0">
  <hp:run charPrIDRef="0">
    <hp:tbl id="1000000021" zOrder="0" numberingType="TABLE"
            textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES"
            lock="0" dropcapstyle="None" pageBreak="CELL"
            repeatHeader="0" rowCnt="2" colCnt="3"
            cellSpacing="0" borderFillIDRef="3" noAdjust="0">
      <hp:sz width="42520" widthRelTo="ABSOLUTE"
             height="5600" heightRelTo="ABSOLUTE" protect="0"/>
      <hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1"
              allowOverlap="0" holdAnchorAndSO="0"
              vertRelTo="PARA" horzRelTo="COLUMN"
              vertAlign="TOP" horzAlign="LEFT"
              vertOffset="0" horzOffset="0"/>
      <hp:outMargin left="0" right="0" top="0" bottom="0"/>
      <hp:inMargin left="0" right="0" top="0" bottom="0"/>
      <hp:tr>
        <hp:tc name="" header="0" hasMargin="0" protect="0"
               editable="0" dirty="1" borderFillIDRef="4">
          <hp:subList id="1000000022" textDirection="HORIZONTAL"
                     lineWrap="BREAK" vertAlign="CENTER"
                     linkListIDRef="0" linkListNextIDRef="0"
                     textWidth="0" textHeight="0"
                     hasTextRef="0" hasNumRef="0">
            <hp:p paraPrIDRef="21" styleIDRef="0"
                  pageBreak="0" columnBreak="0" merged="0" id="1000000023">
              <hp:run charPrIDRef="9"><hp:t>헤더 셀</hp:t></hp:run>
            </hp:p>
          </hp:subList>
          <hp:cellAddr colAddr="0" rowAddr="0"/>
          <hp:cellSpan colSpan="1" rowSpan="1"/>
          <hp:cellSz width="14173" height="2800"/>
          <hp:cellMargin left="0" right="0" top="0" bottom="0"/>
        </hp:tc>
        <!-- 나머지 셀 반복 -->
      </hp:tr>
    </hp:tbl>
  </hp:run>
</hp:p>
```

**표 크기 계산**:
- 열 너비 합 = 본문폭 (기본 42520, kcup 48190)
- 3열 균등: 14173 + 14173 + 14174 = 42520
- 2열 1:4: 8504 + 34016 = 42520
- 행 높이 기본: 2800~3600

---

## 머리말/꼬리말 (header/footer)

```xml
<hp:p id="..." paraPrIDRef="0" styleIDRef="0"
      pageBreak="0" columnBreak="0" merged="0">
  <hp:run charPrIDRef="0">
    <hp:ctrl>
      <hp:header id="..." applyPageType="BOTH">
        <hp:subList id="..." textDirection="HORIZONTAL" lineWrap="BREAK"
                   vertAlign="TOP" linkListIDRef="0" linkListNextIDRef="0"
                   textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">
          <hp:p id="..." paraPrIDRef="20" styleIDRef="0"
                pageBreak="0" columnBreak="0" merged="0">
            <hp:run charPrIDRef="0">
              <hp:autoNum numType="PAGE" numFormat="ARABIC"/>
            </hp:run>
          </hp:p>
        </hp:subList>
      </hp:header>
    </hp:ctrl>
  </hp:run>
</hp:p>
```

- `applyPageType`: BOTH / EVEN / ODD
- `hp:autoNum numType="PAGE"`: 현재 쪽 번호
- `hp:autoNum numType="TOTAL_PAGE"`: 전체 쪽수

---

## 하이퍼링크

```xml
<hp:p id="..." paraPrIDRef="0" styleIDRef="0"
      pageBreak="0" columnBreak="0" merged="0">
  <hp:run charPrIDRef="0">
    <hp:fieldBegin id="..." fieldType="HYPERLINK" hasResult="0">
      <hp:parameters>https://example.com</hp:parameters>
    </hp:fieldBegin>
  </hp:run>
  <hp:run charPrIDRef="0"><hp:t>링크 텍스트</hp:t></hp:run>
  <hp:run charPrIDRef="0">
    <hp:fieldEnd id="..."/>
  </hp:run>
</hp:p>
```

---

## ID 규칙

- 문단 id, 표 id, subList id 등 **모든 id는 문서 내 고유**
- `section_builder.py`는 `_IDGenerator`로 `1000000001`부터 순차 할당
- 수동 작성 시: 범위를 크게 잡아 충돌 방지 (예: 표 id는 9000000001부터)

---

## secPr 필수 속성 (KCUP 기준)

```xml
<hp:secPr masterPageIDRef="0" hasHeader="0" hasFooter="0"
          hasFootnote="0" hasEndnote="0"
          fnRestart="EACH_PAGE" fnStartNum="1"
          enRestart="EACH_SECTION" enStartNum="1"
          fnNumType="ARABIC" enNumType="ARABIC"
          textDirection="HORIZONTAL" spaceColumns="1134">
  <hp:paperSz width="59528" height="84186" orientation="PORTRAIT"/>
  <hp:paperMargin left="5669" right="5669" top="5669" bottom="5669"
                  header="4252" footer="4252" gutter="0"/>
  <hp:pageBorderFill borderFillIDRef="1" page="BOTH"
                     header="INCLUDE" footer="INCLUDE"/>
  <hp:masterPage pageType="BOTH" masterPageIDRef="0"/>
</hp:secPr>
```
