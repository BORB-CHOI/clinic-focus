# 분류 스키마 확장 — 실측 기반 의사결정 (2026-05-27)

> 일회성 분석 노트. Phase A "분류 스키마 실 데이터 기반 확장" 작업의 산출물.
> phase C 본체 마이그레이션과 함께 ai/scratch 폴더 통째 삭제 시 같이 사라진다.
> 결론(권고안)은 ai/CLAUDE.md "분류 스키마" 박스에 박혀 본체로 살아남음.

상위 컨텍스트: [`docs/plans/task-queue.md`](../../docs/plans/task-queue.md) Phase A "분류 스키마 확장" 항목.

## 1. 배경

PR #29 (S3 1차 mirror) 머지로 강남 502개 crawl_data.json 이 AI 트랙 버킷에 도착했다. 현 ai/CLAUDE.md "분류 스키마" 박스는 강남 4과목 88개 PoC 기준 (피부·정형·이비인후·안과 + 각 4~6 세부). 502개 표본은 그 4과목으로 거의 안 잡힌다 — 확장 결정이 Phase C 룰 기반 분류기 구현 전 차단 요인.

## 2. 실측 데이터

### 2-1. HIRA 강남구 종별 분포 (`getHospBasisList` 1회)

- 전체 강남: **3128개**
- S3 mirror 표본: **502개** (전부 HIRA 강남 안에 있음, 누락 0)
- 표본 = HIRA 강남의 16% — BE 가 URL 보유·크롤 성공 기준으로 추렸기 때문

| 종별 (`clCdNm`) | 전체 강남 3128 | S3 표본 502 | 표본 점유율 |
|---|---:|---:|---:|
| 의원 | 2145 | 99 | 20% |
| 치과의원 | 524 | 206 | **41%** |
| 한의원 | 395 | 157 | **31%** |
| 병원 | 32 | 19 | 4% |
| 치과병원 | 12 | 6 | 1% |
| 한방병원 | 9 | 9 | 2% |
| 요양병원 | 6 | 3 | 1% |
| 종합병원 | 2 | 2 | <1% |
| 상급종합 | 2 | 0 | 0% |
| 보건소 | 1 | 1 | <1% |

**핵심 인사이트**:
- 표본의 **72% 가 치과·한의원** — 현 V1 4과목 PoC 가 전혀 못 잡는 영역.
- 양방 의원은 99개(20%)만. 표본 자체가 한방·치과 비중이 매우 높게 셋팅됨.

### 2-2. HIRA 응답 한계 — `getHospBasisList` 에 진료과목 필드 없음

`getHospBasisList` 응답 row 의 필드 목록 (실측):
```
XPos, YPos, addr, clCd, clCdNm, cmdcGdrCnt, cmdcIntnCnt, cmdcResdntCnt,
cmdcSdrCnt, detyGdrCnt, detyIntnCnt, detyResdntCnt, detySdrCnt, drTotCnt,
emdongNm, estbDd, hospUrl, mdeptGdrCnt, mdeptIntnCnt, mdeptResdntCnt,
mdeptSdrCnt, pnursCnt, postNo, sgguCd, sgguCdNm, sidoCd, sidoCdNm,
telno, yadmNm, ykiho
```

`dgsbjtCdNm` (진료과목명) 없음. 의원 종별의 양방 진료과목을 알려면 별도 엔드포인트(`MadmDtlInfoService2/getDgsbjtInfo*`) 필요. 1차 시도 시 HTTP 500 — 경로/버전 추정 잘못 가능성. 진료과목 정확치는 본 분석에서 보류.

> **`be/adapters/hira_adapter.py` `_get_specialists` 의 함정**: `getHospBasisList` 로 호출 후 `dgsbjtCdNm` 을 읽는데, 위 실측대로 그 필드 자체가 없으니 항상 빈 리스트 반환. 별도 PR 로 정정 필요 (be 트랙).

### 2-3. 본문 키워드 매칭 — 의원 99개의 양방 과목 추정

`measure_body_keywords.py` 로 의원 99개의 사이트 본문에 진료과목·시술 키워드 사전을 매칭, 최다 매칭 과목으로 대표과목 추정:

| 추정 양방 과목 | 카운트 |
|---|---:|
| 피부과 | 16 |
| 내과 | 10 |
| 안과 | 9 |
| 성형외과 | 9 |
| 정신건강의학과 | 6 |
| 외과 | 6 |
| 산부인과 | 5 |
| 정형외과 | 5 |
| 비뇨의학과 | 4 |
| 소아청소년과 | 3 |
| 가정의학과 | 2 |
| 재활의학과 | 1 |
| 신경과 | 1 |
| (매칭 0건) | 22 |
| **이비인후과** | **0** |

**핵심 인사이트**:
- **이비인후과 0건** — 현재 V1 PoC 4과목 중 하나인데 강남 의원 표본에 실질 없음.
- **다중 과목 매칭 68/99** — 의원 대부분이 여러 과목 신호를 본문에 노출. `primary_focus` 가 `list[str]` 인 게 정당화.
- **매칭 0건 22/99** — 키워드 사전 미흡 또는 사이트가 진료과목 키워드 거의 안 적음. 향후 4 시그널(블로그·후기·Vision) 보강 자리.

표본 추정 합산: V1 PoC 4과목(피부·정형·이비인후·안과) 만으로는 표본 502개 중 약 30개(6%) 커버. **확장 불가피.**

## 3. 외부 분류 체계 비교

| 출처 | 분류 갯수 | 양방/한방/치과 그룹핑 | 비고 |
|---|---|---|---|
| NHIS 법정 분류 | 의과 26 + 치과 12 + 한방 9 | 3축 명시 | 가장 상세, 행정 표준 |
| 닥터나우 | 15 | "한의원"·"치과" 평탄화 | 진료과 그리드 |
| 굿닥 | 13 | "한의과"·"치과" 별도 1급 | 양방 12 + 한방 1 + 치과 1 |
| 모두닥 | 17 | "한의원/한방병원" 별도 | 양방 16 + 한방 1 + 치과 1 |

**민간 3사 공통 패턴**: standard_specialty 레벨에서 양방 진료과목 12~17개 + "한의원"·"치과" 는 1급 평탄화 (세부 분리 없음). NHIS 의 9개 한방·12개 치과 세부 분류는 민간 서비스에선 안 씀.

> **참고 URL** (사용자 지정, 2026-05-27 WebFetch):
> - NHIS: https://www.nhis.or.kr/nhis/healthin/retrieveMdcAdminSknsClinic.do
> - 닥터나우: https://doctornow.co.kr/hospitals
> - 굿닥: https://www.goodoc.co.kr/
> - 모두닥: https://www.modoodoc.com/

## 4. 권고안 — `standard_specialty` 후보군 22개

표본 적합 + 민간 3사 호환 + 행정 분류 일관성 모두 충족하는 후보군. 양방 16 + 한방 1 + 치과 1 + 기타 4 = 22.

### 양방 진료과목 (의원·병원·종합병원 종별 — 16개)

표본에서 1건 이상 추정된 과목 + 표본에 없지만 강남 외 풀커버 진입 시 등장 예상 + 민간 3사 공통:

1. **내과**
2. **소아청소년과**
3. **이비인후과** (표본 0건이지만 풀커버 시 필요)
4. **안과**
5. **피부과**
6. **성형외과**
7. **정형외과**
8. **신경외과**
9. **외과**
10. **산부인과**
11. **비뇨의학과**
12. **정신건강의학과**
13. **가정의학과**
14. **재활의학과**
15. **마취통증의학과** (강남 통증클리닉 다수 잠재)
16. **신경과**

### 평탄화 1급 항목 (2개)

17. **한의원** — 한의원·한방병원 합침 (NHIS 9개 세부는 도입 안 함). 표본 166개.
18. **치과** — 치과의원·치과병원 합침 (NHIS 12개 세부는 도입 안 함). 표본 212개.

### 기타 종별 (4개)

19. **종합병원** (종합병원·상급종합 합침)
20. **요양병원**
21. **보건소**
22. **기타** — 위에 못 잡힌 케이스 fallback. 룰 기반 분류기가 standard_specialty 미정인 경우 박는 default.

### 표본 커버율 (추정)

- 한의원·치과·종합·요양·보건소 = 종별 그대로 매핑 = 393개 / 502 (78%)
- 의원 99개 → 본문 키워드 매칭 77개 (78%) + 매칭 0건 22개 → "기타"
- **합산 약 470개 / 502 = 94%** 커버. 나머지 6% 는 본문 키워드 미흡으로 "기타" 박힘.

## 5. `primary_focus` 는 자율 유지

- shared/models.py `primary_focus: list[str]` (Literal 아님) — 그대로 유지.
- 상세페이지 ② 영역 태그 카드는 분류기가 추출한 자유 문자열을 그대로 렌더.
- ai/CLAUDE.md 옛 트리(피부과 ├ 미용 시술 ├ 일반 진료 …)는 자식 노드를 "예시" 표기로 격하. 본 분류 스키마는 부모(standard_specialty)만 강제.
- 룰 기반 분류기는 본문 명사구·TF-IDF·BM25 기반 키프레이즈 추출 + 자칭 단락 표현 그대로 박는 방식으로 자율적으로 `primary_focus` 생성. 사전 한정 셋이 없으면 풀커버 시 유연성↑.

## 6. shared/models.py 변경 여부

**권고: 변경 안 함 (현재 `str` 자유 유지).**

- 22개 `standard_specialty` 후보군은 ai/CLAUDE.md 의 "허용 값 목록" 으로 박고, 분류기·BE GSI 키는 그 값들을 약속으로 사용.
- Literal 강제하면 향후 새 종별 추가 시 BE·AI·FE·shared 동시 변경 필요 (PoC 평가 단계에서 부담).
- 오타·버그 방지는 분류기 단위 테스트 + medical-language-reviewer 검수로 대체.
- **단, BE GSI `sigungu_specialty` 값 종류는 22개로 한정** — BE 담당자에게 후보군 공유 + 인덱싱 시 검증 추가 요청 (별도 알림 필요).

## 7. 후속 작업 (이번 PR 범위 밖)

| 작업 | 담당 | 트리거 |
|---|---|---|
| be/adapters/hira_adapter.py `_get_specialists` 정정 — `getDgsbjtInfo*` 엔드포인트로 전환 | BE | 별도 PR |
| BE 담당자에 standard_specialty 후보군 22개 공유 + GSI 인덱싱 검증 추가 | AI → BE | 본 PR 머지 후 |
| FE 검색 필터 옵션 22개로 갱신 | AI → FE | BE GSI 갱신 후 |
| 룰 기반 분류기 키워드 사전 작성 — 22개 × 키워드 세트 | AI Phase C | 본 PR 머지가 차단 해제 |
| 풀커버(서울 5개구 1만) 진입 후 분포 재측정 | AI Phase F | 표본 확장 시점 |

## 8. 산출 파일

- `ai/scratch/measure_specialty_distribution.py` — 종별 분포 측정 스크립트
- `ai/scratch/measure_body_keywords.py` — 의원 99개 본문 키워드 매칭 스크립트
- `ai/scratch/specialty-distribution-2026-05-27.json` — 종별 카운트 raw
- `ai/scratch/body-keywords-2026-05-27.json` — 의원 본문 키워드 매칭 raw
- 본 노트
