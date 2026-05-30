# clinic-focus 작업 큐 — 남은 일만

> 최종 업데이트: 2026-05-30 · 상위 컨텍스트: [`../overview.md`](../overview.md) · [`../dev-roadmap.md`](../dev-roadmap.md)
>
> 이 문서는 **남은 작업 + 현재 데이터 상태 + 지켜야 할 제약**만 둔다.
> 완료 작업 = git PR 이력. 설계·근거는 각 트랙 CLAUDE.md / PR / [`../CATALOG.md`](../CATALOG.md).

---

## 현재 상태 (2026-05-30)

강남구 PoC. **네이버 플레이스 후기를 제외하고** 데이터 파이프라인을 끝까지 개발 중.

**적재됨:**
- `META` 6117 (강남 3134 · 송파 1331 · 양천 705 · 중구 616 · 용산 331)
- 자체사이트 크롤 **정제본 2133** (S3 `kmuproj-10-clinic-focus-crawl`) — denoise + 페이지 단위 노이즈
  필터 적용(페이지 26,377→11,531 **56%↓**, blog RSS 79%↓). 재크롤 없이 기존 raw 재처리.
- 카카오 **place앵커** 후기/블로그 `KAKAO#REVIEWS` 641 · `KAKAO#BLOG` 347 (DDB, 회색지대)
- 분류 = 자칭(정제) + 카카오 후기 + 카카오 place앵커 블로그 교차검증 → 신뢰도. (효과는 CATALOG)

**시그널 귀속 (저자 기준 — 확정):**
- **자칭(self_claim)** = 병원이 쓴 것: 자체사이트(main/about/service) + 자체 blog 페이지 + 자체운영 블로그.
- **블로그(20%)** = 외부 제3자 후기 블로그. **카카오 place앵커 blog 사용**(네이버 키워드 검색은
  교차오염 16.78%로 폐기, 카카오는 0.75%).
- **후기(25%)** = 플레이스 별점 후기(카카오맵 ✅ / 네이버지도 ⚠️미수집 / 구글 유료제외).

### ⚠️ 네이버 플레이스 후기 — 미수집 (의도적 보류, 2026-05-30)

지금은 **네이버 없이** 개발을 끝까지 진행한다. 안 한 이유와 재개 경로만 남겨둔다:
- **사유**: 네이버 place 후기는 공식 API가 없고 `pcmap-api.place.naver.com` graphql(회색지대)뿐 →
  Playwright + ncpt 토큰 필수라 **18~25초/건**(848개 ~5시간). EC2 데이터센터 IP는 네이버 차단
  표적이고 RAM 4GB 제약 → **로컬 PC 크롤로 분리**하는 게 안전.
- **준비됨(파일 다리)**: `be/scripts/crawl_naver_local.py`(로컬 PC, AWS 의존 0, 좌표앵커+이름확정
  매칭, raw JSON 저장) → scp → `be/scripts/ingest_naver_local.py`(EC2, parse+PII제거→`NAVER#PLACE#REVIEWS`).
  타깃: `be/data/naver_targets.json`(강남 3134, 카카오 미매칭 2608 우선).
- **합법성 결론**: 별점·후기·place앵커 블로그는 카카오/네이버 공식 무료 API가 **구조적으로 미제공** →
  회색지대 또는 유료(구글 5건 한도)뿐. 메타·위치·홈페이지URL은 공식 무료로 충분.
- **재개 시**: 로컬 raw 도착 → `ingest_naver_local --confirm` → 후기 시그널이 카카오+네이버 2종으로
  → 증분 재분류. (현재 분류는 카카오 단독 후기로도 성립)

---

## 남은 작업

### A. 데이터 마무리 (강남구, 네이버 제외)
- [ ] URL 발굴 재실행 `enrich_urls.py` — 카카오 1순위·`--sigungu`, 강남 website 보유율 ↑ → 재크롤·재분류
- [ ] `discover_official_blogs.py --confirm` — 자체운영 블로그(blog.naver.com/ID) 발굴 → website_url 승격 → 자칭 흡수
- [ ] Vision 활성화 — 개인계정 Sonnet Marketplace 구독 대기(사용자 트랙) → `analyze_images` → `classify_hospital` 연결
- [ ] hash diff 부분 재처리 — entity `content_hash` 비교, 재크롤 동일 시 KB re-ingest 스킵

### B. FE ↔ BE 연결 (다음 큰 단계 — Phase E)
- [ ] `openapi-typescript` 로 TS 타입 자동 생성 (`fe/src/types/api.ts`) — 수동 동기화 금지
- [ ] Mock 어댑터(`fe/src/mocks/`) 제거 또는 dev 전용 분리 → `SearchPage.tsx` 실 API 연결
  (자연어+위치 토글+카카오맵, TanStack Query 캐싱, 결과 카드: 표준과목+주력+신뢰도+요약+거리)
- [ ] `HospitalDetailPage.tsx` 9영역 컴포넌트 (`fe/src/components/hospital/`)
  - Headline(ai_description+출처배지) / CoreServices / Doctors / **Confidence(4시그널 분해 + `null`=회색 "수집 안 됨" 배지, `0`%=엇갈림 구분)**
  - Operating / Feedback(1-tap+localStorage device_id) / HistoryPreview / Related(same_focus + **gap_fill "안 다루는 분야"**) / Meta
- [ ] `ai_description==null` 차등 렌더(태그 카드 fallback) / `data_completeness<0.6` 경고 배너
- [ ] device_id 유틸(`fe/src/lib/device.ts`) / 변경 이력 전체 페이지 / 카카오맵 신뢰도 색 마커(확실=초록·추정=노랑·부족=회색)

### C. 표본 확장 + 통합 검증 (Phase F)
- [ ] 5개구 풀커버 → 풀크롤(자체+외부) → 룰 분류 일괄(트랙 A, LLM 0)
- [ ] LLM/Vision/`generate_description` 시연 10개(트랙 B·C) — 같은 10개로 룰 대비 차별 시연
- [ ] 자연어 검색 e2e 10건 / FE→BE→AI→KB→DDB 통합 E2E 5건
- [ ] 의료법 표현 전수 검수(`medical-language-reviewer`) / 비용 측정 → overview 보정
- [ ] `shared/models.py` BE·AI 동시 갱신(drift 0)

### D. 인프라·마무리 (Phase G)
- [ ] systemd 검증 / CloudFront+S3 sync 배포 / `.env.example` 정렬 / README 검수 / PR 단위 4리뷰어

---

## DDB 스키마 — single-table (be/CLAUDE.md 참조 단일 진실)

`PK=hospital_id (S)` · `SK=entity (S)`. AI=`kmuproj-10-clinic-Main`, BE=`kmuproj-02-team3-backend`.

**entity 종류**: `META` · `SITE#PAGES`/`SITE#IMAGES`(자칭/Vision) · `NAVER#PLACE`/`NAVER#PLACE#REVIEWS`/`NAVER#BLOG` ·
`KAKAO#PLACE`/`KAKAO#REVIEWS`/`KAKAO#BLOG` · `GOOGLE#PLACE`/`GOOGLE#REVIEWS` · `PUBLIC#DEVICES`/`PUBLIC#DOCTORS` ·
`VISION#RESULTS` · `CLASSIFICATION` · `DESCRIPTION` · `SERVICES` · `RELATED` · `INGEST#STATE` ·
`FEEDBACK#{device}#{ts}` / `FEEDBACK#STATS` · `HISTORY#{iso}`.

**GSI**: `sigungu-specialty-index`(PK=`sigungu#standard_specialty`, SK=`confidence_score`↓ — 카테고리 탐색 BE 직접) ·
`geo-index`(PK=`geohash_prefix`, SK=`lat#lng` — 지도 근처 검색).

---

## 제약 (절대 어기지 말 것)

- **main 직접 수정 금지** — PreToolUse + pre-commit hook 양쪽 차단. 모든 작업 feature 브랜치.
- **KB 공유 운영** — DataSource S3 `kmuproj-02-vector` 는 02·10·11팀 공유. prefix `clinic-focus/prod/`,
  `team_id="clinic-focus"` 메타 필수, **delete 금지**(soft-delete `metadata.status="closed"`).
- **의료법 §56** — 후기 본문 raw 는 DDB 저장·임베딩 입력만, **화면 노출은 키워드 빈도만**. AI 설명 인용도
  "후기 키워드 빈도 ~%"(출처 배지 `[후기]`), "호평" 같은 평가형 어조 금지.
- **회색지대(카카오/네이버 place)** = 시연 표본 한정·천천히(차단방지). EC2 RAM 4GB → 크롤 순차, Playwright 1개·병원마다 닫기.
- **Bedrock 라우팅** — Titan Embed v2 = 지원계정(KB 자동) / Haiku·Sonnet Vision = 개인계정 `ap-northeast-2`.
