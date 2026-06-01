# clinic-focus 작업 큐 — 남은 일만

> 최종 업데이트: 2026-06-01 · 상위 컨텍스트: [`../overview.md`](../overview.md) · [`../dev-roadmap.md`](../dev-roadmap.md)
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
- **Vision(30%)** = 이미지 분석 시연(개인계정 Sonnet 4.6, 10개 한정).
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

개인계정 쿼터 소진으로 **2026-06-01부터 추가 LLM/Vision 호출 금지.** 기존 적재분(시연 10개)은 정적으로만 사용. `generate_description`·`analyze_images` 신규 실행은 쿼터 복구 전까지 보류.

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

### C. FE 상세 페이지 (검색·카테고리·지도는 as-built, 상세는 남음)
- [ ] `HospitalDetailPage.tsx` 9영역 컴포넌트 (`fe/src/components/hospital/`)
  - Headline(ai_description+출처배지) / CoreServices / Doctors / **Confidence(4시그널 분해 + `null`=회색 "수집 안 됨" 배지, `0`%=엇갈림 구분)**
  - Operating / Feedback(1-tap+localStorage device_id) / HistoryPreview / Related(same_focus + **gap_fill "안 다루는 분야"**) / Meta
- [ ] `ai_description==null` 차등 렌더(태그 카드 fallback) / `data_completeness<0.6` 경고 배너
- [ ] device_id 유틸(`fe/src/lib/device.ts`) / 변경 이력 전체 페이지 / 카카오맵 신뢰도 색 마커(확실=초록·추정=노랑·부족=회색)

### D. 표본 확장 + 통합 검증 (Phase F)
- [ ] 5개구 풀커버 → 풀크롤(자체+외부) → 룰 분류 일괄(트랙 A, LLM 0). 현재 분류·KB는 강남만.
- [ ] LLM/Vision/`generate_description` 시연 10개(트랙 B·C) — 같은 10개로 룰 대비 차별 시연 (쿼터 동결 해제 후)
- [ ] 자연어 검색 e2e 10건 / FE→BE→AI→KB→DDB 통합 E2E 5건
- [ ] 의료법 표현 전수 검수(`medical-language-reviewer`) / 비용 측정 → overview 보정
- [ ] `shared/models.py` BE·AI 동시 갱신(drift 0)

### E. 인프라·마무리 (Phase G)
- [ ] systemd 검증 / CloudFront+S3 sync 배포 / `.env.example` 정렬 / README 검수 / PR 단위 4리뷰어

---

## 참고: 주력 강도 랭킹 (as-built — 재작업 아님, 회귀 감시용 수치만)

검색 relevance 랭킹은 '최고 청크 코사인 1개' → '주력 강도'(`_focus_intensity`)로 교체 완료.
코드: `ai/search/kb_store.py`(`_aggregate_by_hospital`·`_focus_intensity`), 가중치 env `FOCUS_RANK_WPF`(0.06)·`FOCUS_RANK_WFREQ`(0.010)·`FOCUS_RANK_WCHUNK`(0.010), `RANK_MODE=cosine`로 옛 동작 A/B.
**BE `be/api/search.py`는 relevance 정렬에서 retrieve_hospital 순서를 보존**(여기서 similarity 재정렬하면 주력 랭킹을 덮어쓰므로 금지).

검증(회귀 감시 기준선):
- 강남 주력 토픽 84개 A/B (`be/scripts/focus_rank_eval.py`): P@1 0.571→**0.655** · P@5 0.562→**0.617** · MRR 0.675→**0.734**.
- 독립 92쿼리 retrieval eval (`be/scripts/_retrieval_eval.py`): 0.859/0.906→**0.891/0.921**(무회귀·개선).

---

## DDB 스키마 — single-table (be/CLAUDE.md 참조 단일 진실)

`PK=hospital_id (S)` · `SK=entity (S)`. AI=`kmuproj-10-clinic-Main`, BE=`kmuproj-02-team3-backend`.

**entity 분류 — raw(수집) ↔ 가공(산출) 구분** (현재 실적재 수치는 2026-06-01 강남 기준):

| 구분 | entity | 비고 / 현재 |
|---|---|---|
| **기준 데이터** | `META` | HIRA 종별·주소·좌표 + 카카오 보강. ✅ 6117 |
| **raw · 자체사이트** | `SITE#PAGES` · `SITE#IMAGES` | ⚠️ **본문은 DDB 아님 — S3** `crawl/{id}/crawl_data.json`(정제본 2133). DDB엔 안 둠 |
| **raw · 외부 수집** | `NAVER#PLACE` · `NAVER#PLACE#REVIEWS` · `NAVER#BLOG` · `KAKAO#PLACE` · `KAKAO#REVIEWS` · `KAKAO#BLOG` · `GOOGLE#PLACE` · `GOOGLE#REVIEWS` · `PUBLIC#DEVICES` · `PUBLIC#DOCTORS` | 플랫폼 수집 원본. ✅ KAKAO 641/641/347 · NAVER#BLOG 854 / 나머지 미수집 |
| **가공 · 룰 (전체 풀커버)** | `CLASSIFICATION` | 4시그널 교차검증 → 과목·주력·신뢰도. LLM 0회. ✅ 강남 ~3098 |
| **가공 · LLM·Vision (시연 10개)** | `VISION#RESULTS` · `DESCRIPTION` · `SERVICES` · `RELATED` | Vision 분석·`generate_description`·시술/의사 추출·연관병원. 시연 10개 적재분 정적 사용(추가 호출 동결) |
| **가공 · KB 적재** | `INGEST#STATE` | content_hash·last_ingested·KB object key(재적재 스킵용). ⚠️ KB **벡터·청크는 DDB 아님** — DataSource S3 `clinic-focus/prod/{id}/{signal}.txt` + KB 내부 인덱스 |
| **사용자·시스템** | `FEEDBACK#{device}#{ts}` · `FEEDBACK#STATS` · `HISTORY#{iso}` | 1-tap 피드백·집계·분류 변경 이력 |

> **헷갈림 정리**: ① 자체사이트 **본문**과 ② KB **벡터/청크**는 DDB가 아니라 **S3**에 있다(DDB는 메타·포인터만).
> raw = 외부에서 긁어온 것(자체사이트·플레이스·블로그·공공). 가공 = 그걸 파이프라인이 만든 것
> (룰=`CLASSIFICATION` 전수 / LLM·Vision=`DESCRIPTION`·`SERVICES`·`RELATED`·`VISION#RESULTS` 시연 10개 / KB=`INGEST#STATE`).

**GSI**: `sigungu-specialty-index`(PK=`sigungu#standard_specialty`, SK=`confidence_score`↓ — 카테고리 탐색 BE 직접) ·
`geo-index`(PK=`geohash_prefix`, SK=`lat#lng` — 지도 근처 검색).

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
