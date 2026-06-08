# clinic-focus 작업 큐 — 남은 일만

> 최종 업데이트: 2026-06-01 · 상위 컨텍스트: [`../overview.md`](../overview.md) · [`../architecture.md`](../architecture.md)
>
> 이 문서는 **남은 작업 + 현재 데이터 상태 + 지켜야 할 제약**만 둔다.
> 완료 작업·아키텍처 = `../architecture.md` / overview / API 명세 / git PR 이력. 설계·근거는 각 트랙 CLAUDE.md / PR / [`../CATALOG.md`](../CATALOG.md).

---

## 현재 상태 (2026-06-01)

강남구 PoC. FE-BE 실연동·검색 랭킹(주력 강도)·페이지네이션·카테고리 탐색·지도 실연동까지 **as-built(main 머지 완료)**. 남은 건 thin-signal recall 개선과 표본 확장·통합 검증·인프라 마무리.

**적재됨 (강남 기준):**
- `META` 6117 (강남 3134 · 송파 1331 · 양천 705 · 중구 616 · 용산 331). **분류·KB 적재는 강남만.**
- `CLASSIFICATION` 강남 분류완료 **~3098** (룰 기반, LLM 0회, 4시그널 교차검증 → 과목·주력·confidence).
- 자체사이트 크롤 **정제본 2133** (S3 `kmuproj-10-clinic-focus-crawl`) — denoise + 페이지 단위 노이즈
  필터 적용(페이지 26,377→11,531 **56%↓**, blog RSS 79%↓). 재크롤 없이 기존 raw 재처리.
- 카카오 **place앵커** 후기/블로그 `KAKAO#REVIEWS` 641 · `KAKAO#BLOG` 347 (DDB, 회색지대).
- KB `kmuproj-team-03`(GTBJ6HLFDK, Titan Embed v2) 강남 적재 — 자연어 검색 retrieve 경로.

**시그널 귀속 (저자 기준 — 확정):**
- **자칭(self_claim, 25%)** = 병원이 쓴 것: 자체사이트(main/about/service) + 자체 blog 페이지 + 자체운영 블로그.
- **Vision(30%)** = 이미지 분석 시연(개인계정 Sonnet 4.6, 약 500개 한정).
- **블로그(20%)** = 외부 제3자 후기 블로그. **카카오 place앵커 blog 사용**(네이버 키워드 검색은
  교차오염 16.78%로 폐기, 카카오는 0.75%).
- **후기(25%)** = 플레이스 별점 후기(카카오맵 ✅ / 네이버지도 ⚠️미수집 / 구글 유료제외).

### ⚠️ 네이버 플레이스 후기 — 미수집 (의도적 보류)

지금은 **네이버 없이** PoC 를 완성한다(카카오 단독 후기로도 분류 성립). 안 한 이유와 재개 경로만 남겨둔다:
- **사유**: 네이버 place 후기는 공식 API가 없고 `pcmap-api.place.naver.com` graphql(회색지대)뿐 →
  Playwright + ncpt 토큰 필수라 **18~25초/건**(848개 ~5시간). EC2 데이터센터 IP는 네이버 차단
  표적이고 RAM 4GB 제약 → **로컬 PC 크롤로 분리**하는 게 안전.
- **준비됨(파일 다리)**: `be/scripts/crawl_naver_local.py`(로컬 PC, AWS 의존 0, 좌표앵커+이름확정
  매칭, raw JSON 저장) → scp → `be/scripts/ingest_naver_local.py`(EC2, parse+PII제거→`NAVER#PLACE#REVIEWS`).
  타깃: `be/data/naver_targets.json`(강남 3134, 카카오 미매칭 2608 우선).
- **합법성 결론**: 별점·후기·place앵커 블로그는 카카오/네이버 공식 무료 API가 **구조적으로 미제공** →
  회색지대 또는 유료(구글 5건 한도)뿐. 메타·위치·홈페이지URL은 공식 무료로 충분.
- **재개 시**: 로컬 raw 도착 → `ingest_naver_local --confirm` → 후기 시그널이 카카오+네이버 2종으로
  → 증분 재분류.

### ⛔ LLM/Vision 추가 호출 동결 (2026-06-01~)

개인계정 쿼터 소진으로 **2026-06-01부터 추가 LLM/Vision 호출 금지.** 기존 적재분(시연 약 500개)은 정적으로만 사용. `generate_description`·`analyze_images` 신규 실행은 쿼터 복구 전까지 보류.

---

## 남은 작업

### A. thin-signal retrieval recall 개선 (랭킹 아님 — recall 후속 과제)

주력 강도 랭킹은 as-built(검증 완료, 아래 표 참조). 남은 한계는 **랭킹이 아니라 retrieval recall**이다.
- [ ] 호흡기·감기/예방접종/알레르기 등 **내과·소아 thin-signal 토픽** recall 개선. 이 토픽들은 병원 텍스트가
  빈약 → 임베딩 약함(코사인 ~0.41) → `KB_MIN_SCORE`(0.42) 컷에 막혀 top5 미진입. **주력 강도로도 안
  고쳐짐**(컷라인을 못 넘어서 애초에 후보에 안 들어옴). 접근 후보: 토픽별 동적 임계, 메타·과목 신호 보강,
  thin-signal 토픽 쿼리 확장.
- [ ] (선택) 자칭 도배 페널티 등 신호 보정 — 컷라인 진입 후 정밀도 영향 재측정.

### B. 데이터 마무리 (강남구, 네이버 제외)
- [ ] URL 발굴 재실행 `enrich_urls.py` — 카카오 1순위·`--sigungu`, 강남 website 보유율 ↑ → 재크롤·재분류
- [ ] `discover_official_blogs.py --confirm` — 자체운영 블로그(blog.naver.com/ID) 발굴 → website_url 승격 → 자칭 흡수
- [ ] hash diff 부분 재처리 — entity `content_hash` 비교, 재크롤 동일 시 KB re-ingest 스킵
- [ ] Vision 활성화 — 개인계정 Sonnet 쿼터 복구 대기(사용자 트랙) → `analyze_images` → `classify_hospital` 연결 (현재 동결)

### C. FE 상세 페이지 — 9영역 대부분 as-built, 남은 갭만 (2026-06-08 감사)

9영역 컴포넌트(`fe/src/components/hospital/`)는 대부분 구현됨 — ② 핵심진료·③ 의료진·
④ 신뢰도(4시그널 분해)·⑥ 피드백UI·⑦ 변경이력·⑧ 관련병원·⑨ 메타 = as-built. 단 ②·③은 크롤/LLM 추출분만 채워지고 심평원 공공 신고
데이터(전문의 수·비급여 항목)는 미연동 — 아래 ★ 참조. 남은 갭(작업량 S/M/L):
- [ ] **⑤ 운영시간(operating_hours)** [M] — `be/api/hospital.py:106` null 반환(구조화 미보유). 크롤
  파싱 → `HospitalMeta.operating_hours`(shared/models.py:472) 적재 + FE `BasicInfoSection` null 가드 해제.
  ⚠️ FE 타입(`domain.ts:89` DayHours: open/close…)과 BE 모델(weekday/saturday…) **구조 불일치 — 한쪽 정렬 필요**.
- [ ] **thumbnail_url 스크린샷 적재** [M] — `be/api/hospital.py:22` 스트리밍 엔드포인트는 있으나
  S3 `thumbnails/{id}.jpg` 적재가 일부만(카카오/네이버 외부 URL은 동작). 미수집 병원은 플레이스홀더 폴백.
- [ ] **① ai_description==null 차등 렌더 강화** [S] — 현재 안내 텍스트만 → 표준과목+주력태그 카드 모드(`HeadlinerSection`).
- [ ] **② Vision 샘플이미지 갤러리** [L] — `sample_image_urls` 항상 `[]`. Vision 이미지 URL 저장 + `CoreServicesSection` 갤러리 활성화.
- [ ] **⑥ 피드백/프로필 엔드포인트 BE** [L] — `/api/feedback/{id}/stats`·`/api/analytics/profile` 미구현(FE는 try-catch로 무시 중).
- [ ] **⑨ data_sources 동적 산출** [S] — `hospital.py` 현재 `["public_registry"]` 하드코딩 → 실제 시그널 출처 탐지.
- [ ] **신뢰도 라벨·'자칭'·태그 숫자 카피 개선** [S] (UX, 같은 FE 묶음) — `ConfidenceBadge`의 "여러 출처 일치/
  일부 출처 확인/자칭만 확인" + "자칭 컨셉" 용어가 비전문가에 모호. 중립·직관 표현으로(예: "병원 정보만 확인") +
  태그 옆 숫자(= `confidence.score` 0~100 근거점수) 의미 명확화 또는 정리. ★ medical-language-reviewer 검수 필수.

**★ 심평원 공공 신고 데이터 — code path 구현 완료(2026-06-08, `feat/hira-public-signals`), 키 승인+재적재만 남음.**
엔드포인트 실측 확정(403=경로 정확·키 미승인): 전문의 `MadmDtlInfoService2.7/getDgsbjtInfo2.7`(`dgsbjtPrSdrCnt`),
비급여 `nonPaymentDamtInfoService/getNonPaymentItemHospDtlList`. 분류 스키마(M1 동결) 불변 — `PublicData`
확장(`specialists_by_dept`·`total_doctors`·`nonpay_items`) + 상세표시·검색필터만으로 구현:
- [x] ③ 의료진 — `PublicData.specialists_by_dept` 적재·상세응답·`DoctorsSection` "심평원 신고 기준 ○○과 전문의 N명"
  (간판-진실성: 0명도 사실 노출). 검색 필터 `has_specialist`/`specialist_dept`(GSI 경로). medical-language 검수 통과.
- [x] ② 비급여 — `PublicData.nonpay_items` 적재·상세 비급여 영역(출처 `public_data`). AI 의도정렬 일반화
  (미용 하드코딩 `_COSMETIC_FOCUS` → 심평원 `nonpay_ratio` soft 강등, 하드코딩 fallback 유지·도수 hard제외 제외).
**★승인 현황(2026-06-08 키 수령 후 실측)**: 비급여 15001700 **승인·동작 ✅** / 전문의 **15001699 여전히 403 미승인 ❌**
(별도 데이터셋 — `data.go.kr/data/15001699` 활용신청 누락. 의료기관별상세정보서비스). **핵심: 전문의가 의원 타깃의
간판진실성 절반인데 그게 막힘.** 사용자 결정 = **전문의 15001699 승인까지 보류 후 전문의+비급여 일괄 적재.**
- [ ] **15001699(전문의) 활용신청 승인 대기** → 승인 시 `be/scripts/_verify_hira_detail.py` 로 getDgsbjtInfo2.7 403→200 확인.
- [ ] **승인 후 일괄 적재**: `LOAD_PUBLIC_DATA=true .venv/bin/python be/scripts/load_seoul_5gu.py`(전문의+비급여 → PUBLIC#DOCTORS/NONPAY)
  → `run_classification --sigungu 강남구`(룰, LLM0) 재ingest(nonpay_ratio·specialist 메타 KB 진입). 그 전까지 403/빈값 graceful.
- **★실측 데이터 한계(우리가 못 고침)**: 비급여 **의원 커버리지 0%**(강남 의원 158/158 totalCount=0), 병원급↑ 100%
  (광동병원 130·강남세브란스 764). 비급여 영역은 병원급에서만 채워짐 — 의원의 가치는 전문의(간판진실성)에서 나옴.
  FE 는 빈 비급여 영역 graceful 숨김. (실측 파서 정합: `items=""` 빈문자열·category=npayKorNm 첫 세그먼트, 커밋 40cf5c0.)

> 다음 세션 우선순위: 필수 ⑤·thumbnail(M) → 중요 ①·⑥. **★ 공공 신고: 비급여 승인됨(병원급만)·전문의 15001699
> 신청 누락 → 승인 후 일괄.** 근거: 2026-06-08 9영역 감사 + 심평원 2종 연동·키 수령 실측.

### D. 표본 확장 + 통합 검증 (Phase F)
- [ ] 5개구 풀커버 → 풀크롤(자체+외부) → 룰 분류 일괄(트랙 A, LLM 0). 현재 분류·KB는 강남만.
- [ ] LLM/Vision/`generate_description` 시연 약 500개(트랙 B·C) — 같은 약 500개로 룰 대비 차별 시연 (쿼터 동결 해제 후)
- [ ] 자연어 검색 e2e 10건 / FE→BE→AI→KB→DDB 통합 E2E 5건
- [ ] 의료법 표현 전수 검수(`medical-language-reviewer`) / 비용 측정 → overview 보정
- [ ] `shared/models.py` BE·AI 동시 갱신(drift 0)

### E. 인프라·마무리 (Phase G)
- [ ] systemd 검증 / CloudFront+S3 sync 배포 / `.env.example` 정렬 / README 검수 / PR 단위 4리뷰어

---

## 참고 — 회귀 감시 기준선

**주력 강도 랭킹**(as-built, 재작업 아님): relevance 1순위를 코사인→`_focus_intensity`로 교체. 계산식·
코드·BE 순서보존 규칙 상세 = [`../architecture.md`](../architecture.md) §5-1. 회귀가 나는지 감시할 기준 수치:
- 84토픽 A/B (`be/scripts/focus_rank_eval.py`): P@1 .571→**.655** · P@5 .562→**.617** · MRR .675→**.734**.
- 92쿼리 eval (`be/scripts/_retrieval_eval.py`): 0.859/0.906→**0.891/0.921**.

---

## DDB 스키마

`PK=hospital_id`·`SK=entity` single-table (GSI: 카테고리 `sigungu-specialty-index` · 지도 `geo-index`).
entity 종류·raw(수집)↔가공(산출) 구분·본문(S3)/벡터(KB)/메타(DDB) 3층 구조 상세 =
[`../architecture.md`](../architecture.md) §1 · [`../../be/CLAUDE.md`](../../be/CLAUDE.md). 적재 현황 수치는 위 "현재 상태".

---

## 제약 (절대 어기지 말 것)

- **main 직접 수정 금지** — PreToolUse + pre-commit hook 양쪽 차단. 모든 작업 feature 브랜치.
- **검색 경로 이원화 + 검색시 LLM 0회** — 자연어=AI retrieve_hospital(KB Retrieve, Titan Embed v2) / 카테고리(sigungu·specialty)=BE DDB GSI 직접 / 위치=KB lat·lng bbox + haversine. 검색 시점 LLM 호출 0.
- **KB 공유 운영** — DataSource S3 `kmuproj-02-vector` 는 02·10·11팀 공유. prefix `clinic-focus/prod/`,
  `team_id="clinic-focus"` 메타 필수, **delete 금지**(soft-delete `metadata.status="closed"`).
- **의료법 §56 — 주체 명시·평가 금지** — 우리는 평가/추천 안 하고 병원이 자기를 어떻게 표현했는지만 보여준다.
  confidence='근거 강도'(독립 출처 일치도)이지 품질평가 아님. 후기 본문 raw 는 DDB 저장·임베딩 입력만,
  **화면 노출은 키워드 빈도만**. AI 설명 인용도 "후기 키워드 빈도 ~%"(출처 배지 `[후기]`), "호평" 같은 평가형 어조 금지.
- **회색지대(카카오/네이버 place)** = 시연 표본 한정·천천히(차단방지). EC2 RAM 4GB → 크롤 순차, Playwright 1개·병원마다 닫기.
- **Bedrock 라우팅** — Titan Embed v2 = 지원계정(KB 자동) / Haiku·Sonnet Vision = 개인계정 `ap-northeast-2`.
