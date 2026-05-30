# clinic-focus 작업 큐 — V2 완전 서비스

> 최종 업데이트: 2026-05-28 · 상위 컨텍스트: [`../overview.md`](../overview.md), [`../dev-roadmap.md`](../dev-roadmap.md)
>
> 연관 문서: 분류 스키마 근거 → [`../../ai/CLAUDE.md`](../../ai/CLAUDE.md) "분류 스키마" 박스(결정 근거 흡수) · 완료 작업 = git PR 이력(§7) · 외부 크롤 실측 → [`../dev-roadmap.md` 김경재 트랙](../dev-roadmap.md#김경재-트랙--데이터--백엔드)

이 문서는 clinic-focus 의 **남은 작업**을 모은 큐다. V2 정의·9 차별점 매트릭스·표본
분할은 [`../overview.md` §10-5](../overview.md), 트랙·Phase 매핑은
[`../dev-roadmap.md`](../dev-roadmap.md) 에 있고(중복 방지), 여기는 그 위에서 실제로
손댈 항목만 둔다.

---

## 0. 배경 — 설명 문서로 이전됨 (중복 제거)

작업 큐 슬림화(2026-05-28)로 아래 "설명"은 설명 문서로 옮겼다. 여기는 남은 작업만:

- **V2 정의 · 9 차별점 현 상태 매트릭스 · 표본 분할(비용 통제)** → [`../overview.md` §10-5](../overview.md)
- **외부 4 소스(자칭/Vision/블로그/후기) · 크롤 실측 · 합법/회색지대** → [`../dev-roadmap.md` 김경재 트랙](../dev-roadmap.md#김경재-트랙--데이터--백엔드)
- **트랙별 Phase A~G 매핑 · 진척** → [`../dev-roadmap.md` Phase 1 단계 분해](../dev-roadmap.md#phase-1-m03--v2-완전-서비스-단계-분해)

한 줄 요약: PoC 시연(14개, PR [#25](https://github.com/BORB-CHOI/clinic-focus/pull/25)) 위에
4 외부 소스 + DDB single-table + KB 임베딩 통합으로 9 차별점을 실가동시키는 게 V2.
비용 통제 위해 **룰·외부 API 시그널은 1만 풀커버, LLM·Vision 은 시연 10개 한정**.

---

## 3. DDB 스키마 — single-table

single-table 전환 완료(PR [#28](https://github.com/BORB-CHOI/clinic-focus/pull/28)): `PK=hospital_id`+`SK=entity`. 4 시그널을 켜면 entity 종류가 폭증해 옛 7-table 로는 관리 불가라 통일. BE=`kmuproj-02-team3-backend`, AI=`kmuproj-10-clinic-Main`. 아래는 entity·GSI 규약 (be/CLAUDE.md 가 참조하는 단일 진실).

### 3-1. 단일 테이블 스키마

테이블 이름: `kmuproj-XX-clinic-{Hospitals|Main}` (이름은 마이그레이션 시 결정).
PK = `hospital_id` (S)
SK = `entity` (S)

### 3-2. entity 종류

| SK 값 | 내용 | 시그널 | 출처 |
|---|---|---|---|
| `META` | 이름·주소·위경도·시도·시군구·전화·표준 진료과목·website_url | — | HIRA + 카카오 |
| `SITE#PAGES` | 자체 사이트 크롤링 결과 (`CrawlData.pages[*]`) | 자칭 | 자체 사이트 |
| `SITE#IMAGES` | 자체 사이트 이미지 메타·URL | Vision | 자체 사이트 |
| `NAVER#PLACE` | 네이버 플레이스 정보 (영업시간·전화·사진 URL·총 방문자 수 등) | 후기 보조 | 네이버 |
| `NAVER#PLACE#REVIEWS` | 네이버 플레이스 방문자 리뷰 키워드 빈도 | 후기 | 네이버 |
| `NAVER#BLOG` | 네이버 블로그 검색 결과 + 본문 추출 (상위 N개) | 블로그 | 네이버 |
| `KAKAO#PLACE` | 카카오 로컬 API 장소 정보 | 후기 보조 | 카카오 |
| `KAKAO#REVIEWS` | 카카오맵 리뷰 키워드 빈도 | 후기 | 카카오 |
| `GOOGLE#PLACE` | Google Places `place_id` + 기본 정보 | 후기 보조 | 구글 |
| `GOOGLE#REVIEWS` | Google Places 리뷰 키워드 빈도 | 후기 | 구글 |
| `PUBLIC#DEVICES` | 심평원 의료기기 신고 목록 | 기기 | 심평원 |
| `PUBLIC#DOCTORS` | 심평원 의료진 전문의 자격 | 의료진 | 심평원 |
| `VISION#RESULTS` | Vision 이미지 분류 결과 (시술·기기 식별) | Vision | Bedrock |
| `CLASSIFICATION` | `Classification` (standard_specialty·primary_focus·confidence·signals) | — | AI |
| `DESCRIPTION` | `HospitalDescription` (headline·paragraphs·citations·generator_model) | — | AI |
| `SERVICES` | `ServicesAndDoctors` (services·excluded_services·equipment·prices·doctors) | — | AI |
| `RELATED` | `find_related_hospitals` 결과 (same_focus·gap_fill) | — | AI |
| `INGEST#STATE` | `content_hash` · `last_ingested_at` · `kb_data_source_object_key` (hash diff 용) | — | AI |
| `FEEDBACK#{device_id}#{timestamp}` | 1-tap 피드백 1건 (verdict·primary_focus 평가 대상) | — | FE |
| `FEEDBACK#STATS` | 집계 (total/agree/disagree/agree_ratio/last_feedback_at) | — | AI 갱신 |
| `HISTORY#{changed_at_iso}` | 분류 변경 이력 1건 (from_focus→to_focus·reason·signal_source) | — | AI 자동 |

### 3-3. GSI

| GSI | PK | SK | 용도 |
|---|---|---|---|
| `sigungu-specialty-index` | `sigungu#standard_specialty` (META 항목만) | `confidence_score` (Number, 내림차순) | 카테고리 탐색 (BE 직접 조회, AI 미경유) |
| `geo-index` | `geohash_prefix` (META 항목만) | `lat#lng` | 지도 근처 검색 (필요 시) |

---

## 4. V2 sprint — 단계별 잔여 작업

### Phase A — 기반 재설계 ✅ 완료

shared/models 4 시그널+외부 소스 모델 / DDB single-table 마이그레이션(PR [#28](https://github.com/BORB-CHOI/clinic-focus/pull/28), 콘솔 생성·연결 확인) / 분류 스키마 22 후보군 확정(PR [#30](https://github.com/BORB-CHOI/clinic-focus/pull/30)) / 외부 API 키 발급(`.env` 실측) / BE 차단 이슈 [#23](https://github.com/BORB-CHOI/clinic-focus/issues/23)·[#24](https://github.com/BORB-CHOI/clinic-focus/issues/24). 강남 502 S3 mirror.

남은 것:
- [ ] 검증: 1만 데이터 적재 후 자연어 검색 4쿼리 회귀 (데이터 적재 후)
- [ ] BE PutObject 시점 양쪽 버킷 mirror 자동화 — BE 협조, 풀커버 진입 전 합의
- [ ] **후속 정정**: `be/adapters/hira_adapter.py` `_get_specialists` — `getHospBasisList` 응답에 `dgsbjtCdNm` 없어 항상 빈 리스트 반환 / FE 검색 필터 22개 갱신 / BE GSI `sigungu_specialty` 검증

### Phase B — 외부 시그널 크롤러 4종 (BE) — 어댑터 완성, 크롤 실행 잔여

> **크롤 실측·합법/회색지대 요약은 [`../dev-roadmap.md` 김경재 트랙](../dev-roadmap.md#김경재-트랙--데이터--백엔드)** 으로 이전.
> 핵심: Vision 입력 = 자체 사이트 한정 / 네이버·카카오 후기는 회색지대(robots Disallow + 약관)라
> 실제 크롤 실행은 운영자 결정 / 구글 Places·네이버 블로그 공식 API 는 합법 / 후기 본문 raw 는
> §56③ 상 임베딩 입력만, 화면 노출은 키워드 빈도만.

✅ 완료(어댑터·정제): `be/core/crawler.py` HTML 잡음 정제(`_denoise_pages`, 블랙리스트, 비급여 보존) /
어댑터 4종 — `naver_place_adapter`(Playwright+ncpt graphql) · `naver_blog_adapter`(공식 `v1/search/blog`) ·
`kakao_place_adapter`(httpx panel3) · `google_places_adapter`(Places API New). 모두 순수 파서 + PII 미보존,
`classify`/`build_signal_chunks` 가 소비. 배치 골격 `crawl_external_all.py`(기본 dry-run + 회색지대 가드).

남은 것 (실제 크롤 실행 = 운영자 결정):
- [ ] 네이버 플레이스 크롤 → `NAVER#PLACE#REVIEWS` 적재 (회색지대, Playwright 1건 18~25초)
- [ ] 네이버 블로그 크롤 → `NAVER#BLOG` 적재 (공식 API, 합법)
- [ ] 카카오 크롤 → `KAKAO#PLACE`/`KAKAO#REVIEWS` 적재 (회색지대)
- [ ] 구글 크롤 → `GOOGLE#PLACE` 적재 (공식 API, 합법)
- [ ] `crawl_external_all.py` 실제 1,084 실행 — 구글만이면 합법, 카카오 포함은 회색지대+rate-limit 미실측
- [ ] **hash diff 부분 재처리** — entity 에 `content_hash` 추가, 재크롤 시 동일하면 KB 재ingest 스킵 (설계는 [`../dev-roadmap.md` Phase 2 변경 감지](../dev-roadmap.md))
- [ ] 의료법 후기 처리 룰 — raw 는 DDB 저장 + 임베딩 입력만, 화면 노출은 키워드 빈도·태그만 (개별 후기 본문 노출 금지)

### Phase C — AI 본체화 + 4 시그널 통합 ✅ 대부분 완료

임베딩·분류·설명 분리 결정(검색 임베딩 = **시그널별 원본 청크**로 풀커버 / DESCRIPTION 은
벡터 미포함·시연 10개 / CLASSIFICATION 은 청크 metadata 로만)은 `ai/search/kb_store.py` +
[`../API-BE-AI.md` §4·§5](../API-BE-AI.md) 에 반영. §56③: 후기·블로그 raw 는 임베딩 입력 OK,
검색 결과 화면엔 정제 필드만.

완료: kb_store(`ingest_hospital`/`retrieve_hospital` + 청크 빌더, 옛 S3 Vectors 폐기) /
`classify_hospital` 룰 경로 + 외부 시그널 통합(도배 페널티·후기 키워드) /
`generate_description` 4시그널 + citations 강제 / `extract_services_and_doctors` /
`find_related_hospitals` / `recompute_confidence` / `aggregate_feedback_stats` /
분류 변경 자동 기록 / Bedrock mock 의무화 /
**신뢰도 시그널 결손 처리 보정**(결손은 점수 제외·근거 종류 수로 등급 천장·
`SignalContributions` `int|None` 으로 "수집 안 됨"=`null` 과 엇갈림=`0` 구분,
2026-05-30 — 결정 파라미터 2종/근거수통일/베이스라인0/CAP70·LOW70·HIGH95).

남은 것:
- [ ] `ai/pipeline/vision.py` Vision **활성화** — 본체 완성(analyze_images·MAX_VISION_IMAGES), 개인계정 Sonnet Marketplace 구독만 남음(사용자 트랙)
- [ ] `vision_results` 입력 통합 — Vision 활성화 후 `classify_hospital` 에 연결

### Phase D — BE FastAPI 4개 엔드포인트 ✅ 대부분 완료

4 엔드포인트 본체 완료: `GET /api/search`(자연어/위치 `retrieve_hospital` + 시군구 GSI, `_hospital_card` join) /
`GET /api/hospitals/{id}`(9영역 join + 404 + completeness) / `GET /.../history` / `POST /api/feedback`
(verdict 422→400, device_id+hospital_id 409, 임계 시 `recompute_confidence` inline graceful).
응답 포맷·에러 코드·CORS(env) 정합. `run_index_pipeline`(demo 분기 + `**external` 전개 + 변경 자동 기록).

남은 것:
- [ ] OpenAPI 자동 생성 검증 — `/openapi.json` ↔ 명세 정합 (FE TS 타입 생성 시점)
- [ ] (선택) `be/handlers/index_hospital.py` → `ingest_hospital.py` 파일명 정합 — 미적용

### Phase E — FE 9영역 + 4 시그널 시각화

- [ ] `openapi-typescript` 로 TS 타입 자동 생성 — `fe/src/types/api.ts`
- [ ] Mock 어댑터 (`fe/src/mocks/`) 제거 또는 dev 전용으로 분리
- [ ] `SearchPage.tsx` 실 API 연결
  - 자연어 입력 + 위치 토글 + 카카오맵 결합
  - TanStack Query `useSearch(q, filters)` 캐싱
  - 결과 카드: 표준 진료과목 + 실제 주력 + 신뢰도 + `one_line_summary` + 거리
  - 검색 결과 ↔ 지도 뷰 토글
- [ ] `HospitalDetailPage.tsx` 9개 영역 컴포넌트 — `fe/src/components/hospital/` 아래 분리
  - `HeadlineSection` — `ai_description` 자연어 단락 + 출처 배지 클릭→④ 스크롤
  - `CoreServicesSection` — services / excluded_services / equipment / prices
  - `DoctorsSection` — doctors 리스트 + 의사별 전공
  - `ConfidenceSection` — 신뢰도 게이지 + **4 시그널 기여도 분해 차트** + 펼침 메뉴 (자칭 원문·Vision 분포·블로그 토픽·후기 키워드). `SignalContributions` 값이 `null` 인 시그널은 회색 **"수집 안 됨"** 배지로 렌더 — `0`%(수집됐으나 주력과 엇갈림)과 시각적으로 구분
  - `OperatingSection` — 주소(지도) + 전화(탭 가능) + 운영시간 + 야간/주말 + 주차 + 예약
  - `FeedbackSection` — 1-tap 👍/👎 (localStorage 디바이스ID) + 누적 통계 + 분류 오류 신고
  - `HistoryPreviewSection` — 최근 변경 1~2건 + 전체 이력 페이지 링크
  - `RelatedHospitalsSection` — same_focus 카드 + **"안 다루는 분야" gap_fill 카드 별도**
  - `MetaSection` — last_updated + data_sources + completeness 미만 시 경고 배너
- [ ] `ai_description == null` 차등 렌더링 — 태그 카드 fallback ([API-FE-BE §2](../API-FE-BE.md#2-병원-상세) 프론트 렌더링 가이드)
- [ ] `excluded_services[].alternative_hospital_ids` → ⑧ 영역 링크 (안 다루는 분야 옆에 "동네 대안: △△의원")
- [ ] `metadata.warning` 배너 / `data_completeness < 0.6` 시 빈 영역 "정보 부족" 표시
- [ ] 디바이스 ID 유틸 (`fe/src/lib/device.ts`) — localStorage `app_device_id` 키, 최초 방문 시 `crypto.randomUUID()` 생성
- [ ] **변경 이력 전체 페이지** (`/hospitals/{id}/history`) — `HistoryPreviewSection` 의 "전체 이력" 링크 도착지
- [ ] 카카오맵 SDK 마커 색상 — 신뢰도 등급(확실=초록 / 추정=노랑 / 정보 부족=회색)

### Phase F — 표본 확장 + 통합 검증

- [ ] HIRA → 서울 5개구 풀커버 (이슈 [#18](https://github.com/BORB-CHOI/clinic-focus/issues/18) 의 "병원 목록 소스" 부분)
  - 강남 4과목 88개 → 5개구(강남·서초·송파·성동·중구) 4과목 ~1000개 → 5개구 전체 진료과목 ~1만
- [ ] **풀크롤링 (1만 전체)** — 자체 사이트 + 외부 4소스(네이버 플레이스·블로그·카카오·구글). LLM·Vision 미사용
- [~] **룰 기반 분류 일괄 (트랙 A, 1만)** — 배치 스크립트 `be/scripts/run_classification.py` 준비 완료: DDB 순회 → `db.load_external_signals` 로 카카오/네이버/구글 entity 로드 → `classify_hospital(use_llm=False, **external)` → 분류 저장 + `build_signal_chunks(**external)` ingest, 마지막 1회 trigger. **실제 1만 실행은 외부 크롤 일괄 후** (외부 entity 적재돼 있으면 4 시그널 교차검증, 없으면 자체 사이트만 — graceful)
- [ ] **LLM 시연 분류 (트랙 B, 10개)** — `MAX_LLM_DEMO_HOSPITALS=10` 환경변수 강제. 풀커버 결과 중 발표용 10개 선정 (강남, 진료과목 다양, 사이트 풍부)
- [ ] **Vision 시연 (트랙 C, 같은 10개)** — `MAX_VISION_IMAGES=10` 환경변수 강제. Marketplace 구독 완료 전제. 같은 10개에 대해 트랙 B 결과와 비교 출력 (발표 자료용)
- [ ] **`generate_description` 시연 (10개)** — 트랙 B·C 결과 합쳐 자연어 통합 설명 생성. 9990개는 `ai_description=null` 그대로 (FE 차등 렌더링)
- [ ] `ingest_hospital` 일괄 — KB 에 1만개 본문 적재. 본문 합성 시 LLM 설명은 10개만 박히고, 나머지는 룰 기반 태그·외부 시그널 키워드 빈도로 본문 구성
- [ ] 자연어 검색 e2e — 다양한 쿼리(시술명·증상·지역+시술 조합) 10건 검증
- [ ] 의료법 표현 전수 검수 — `medical-language-reviewer` 서브에이전트 (특히 후기 키워드 노출 형태, AI 통합 설명, FE 카피)
- [ ] `shared/models.py` 변경분 BE·AI 동시 갱신 확인 (스키마 drift 0)
- [ ] FE→BE→AI→KB→DDB→9영역 응답 통합 E2E 시나리오 5건
- [ ] 비용 측정 — 1만개 처리 LLM·Vision·임베딩 실비용 → `overview.md` 10-1 추정치 보정

### Phase G — 인프라·운영 마무리

- [ ] systemd `clinicfocus.service` 검증 (PR #8 이미 있음)
- [ ] CloudFront + S3 정적 호스팅 — FE 빌드 → `aws s3 sync` → invalidation
- [ ] EC2 모니터링 — CloudWatch 기본 로그 (별도 인프라 X)
- [ ] `.env.example` 최종 정렬 — 누락 키 0
- [ ] README.md 최종 검수
- [ ] PR-단위 의료법·코드 리뷰 (`medical-language-reviewer`·`python-reviewer`·`typescript-reviewer`·`security-reviewer`)

---

## 5. 의존성 그래프

```
Phase A (기반 재설계)
  ├─ DDB 단일 테이블
  ├─ shared/models.py 확장
  ├─ 외부 API 키 발급
  └─ BE 차단 이슈 #23/#24
        │
        ▼
Phase B (외부 시그널 크롤러 4종)
  ├─ 자체 사이트 정제 (#13)
  ├─ 네이버 플레이스 + 블로그
  ├─ 카카오 (확장)
  └─ 구글 Places
        │
        ▼
Phase C (AI 본체화 + 4 시그널 통합)
  ├─ ai/scratch → ai/ 본체
  ├─ classify_hospital 재설계
  ├─ generate_description 4 시그널 종합
  ├─ Vision 활성화 (Marketplace 의존)
  ├─ extract / related / recompute / aggregate / 변경이력 자동 기록
        │
        ▼
Phase D (BE 4개 엔드포인트 본체)
  ├─ /api/search (자연어 + 지도)
  ├─ /api/hospitals/{id} (9영역)
  ├─ /api/hospitals/{id}/history
  └─ /api/feedback
        │
        ▼
Phase E (FE 9영역 + 시그널 시각화)
  ├─ 9개 컴포넌트 분리
  ├─ ai_description 차등 렌더링
  └─ 카카오맵 신뢰도 색 마커
        │
        ▼
Phase F (표본 확장 + 통합 검증)
  ├─ 88 → 1000 → 1만
  ├─ 의료법 전수 검수
  └─ 통합 E2E
        │
        ▼
Phase G (인프라·운영 마무리)
```

병렬 진행 가능:
- Phase A 내부 4 항목 병렬
- Phase B 의 4 크롤러 병렬 (소스별 독립)
- Phase C·D 의 인터페이스 합의 후 동시 진행
- Phase E 는 Phase D `/api/*` skeleton 만 있어도 진입 (Mock 가능)

---

## 6. AI 트랙 AWS 워크북 (개인 진행 기록)

| Step | 내용 | 상태 |
|---|---|---|
| 0 | VSCode Remote-SSH → EC2 | ✅ |
| 1 | 지원 계정 자격증명·Bedrock 모델 가용성 | ✅ |
| 2 | Titan v2 임베딩 hello-world | ✅ |
| 3 | KB Retrieve 왕복 + S3 ingest 권한 | ✅ |
| 4 | DataSource 파일·metadata 스키마 | ✅ |
| 5 | 개인 계정 Sonnet 4.6 Vision (Marketplace 구독 대기) | △ |
| 6 | DDB 7테이블 + 88개 적재 + 14개 분류·설명·KB ingest·자연어 검색 | ✅ PR [#25](https://github.com/BORB-CHOI/clinic-focus/pull/25) (V2 전환과 함께 옛 7-table·14개 폐기) |
| 7 | single-table 재설계 — 어댑터 재작성 + 옛 7-table 폐기 + 콘솔 수동 V2 생성 | ✅ 2026-05-27 |
| 8 | **외부 3소스 (네이버·카카오·구글) 적재** | ⏳ Phase B |
| 9 | **4 시그널 본문 합쳐 재 ingest** | ⏳ Phase C |

상세 진행 기록은 [`../setup/aws-onboarding.md`](../setup/aws-onboarding.md) 참조 (Step 6 의 옛 7-table·14개 dev 검증은 PR [#25](https://github.com/BORB-CHOI/clinic-focus/pull/25), scratch 제거됨).

---

## 7. 완료된 PR (최근순)

| PR | 제목 |
|---|---|
| [#36](https://github.com/BORB-CHOI/clinic-focus/pull/36) | 네이버 어댑터 2종 + HTML 정제 + alt_ids — V2 미개발 해소 |
| [#35](https://github.com/BORB-CHOI/clinic-focus/pull/35) | 외부 시그널 4종 통합 + Phase A/C/D 정합 (검색·피드백·분류 연동) |
| [#34](https://github.com/BORB-CHOI/clinic-focus/pull/34) | 카카오 어댑터 + AI 룰 분류·KB 시그널 청크 본체 + 정합 정리 |
| [#30](https://github.com/BORB-CHOI/clinic-focus/pull/30) | feat: 분류 스키마 22 후보군 확정 + 외부 API 키 변수 추가 |
| [#28](https://github.com/BORB-CHOI/clinic-focus/pull/28) | refactor(be): DDB V2 single-table 어댑터 재작성 |
| [#25](https://github.com/BORB-CHOI/clinic-focus/pull/25) | feat(ai): scratch/ 우회로 dev e2e 검증 — HIRA → 분류 → KB → 자연어 검색 |
| [#22](https://github.com/BORB-CHOI/clinic-focus/pull/22) | docs: DDB 선택 근거 + 7-table ERD 박기 |
| [#21](https://github.com/BORB-CHOI/clinic-focus/pull/21) | feat: URL 보강 크롤링 파이프라인 (Playwright + 쿼리 다변화) |
| [#20](https://github.com/BORB-CHOI/clinic-focus/pull/20) | docs(env): `AI_AWS_SESSION_TOKEN`·`CRAWL_DATA_DIR` 코멘트 명확화 |
| [#19](https://github.com/BORB-CHOI/clinic-focus/pull/19) | docs(ai): dev 계정 e2e Step 6 추가 + DDB 콘솔 수동 생성 절차 |
| [#17](https://github.com/BORB-CHOI/clinic-focus/pull/17) | docs(be): BE AWS 연결 작업 큐 + 의존성 매트릭스 |
| [#16](https://github.com/BORB-CHOI/clinic-focus/pull/16) | docs(ai): AWS 온보딩 Step 2·5 완료 + Vision Sonnet 4.6 전환 |
| [#15](https://github.com/BORB-CHOI/clinic-focus/pull/15) | docs(ai): 벡터 검색 KB 경유 전환 + AWS 온보딩 가이드 |
| [#14](https://github.com/BORB-CHOI/clinic-focus/pull/14) | feat(fe): FE 디자인 — 검색·상세·지도 화면 골격 |
| [#12](https://github.com/BORB-CHOI/clinic-focus/pull/12) | docs(ai): AI 트랙 전략 재편 + EC2/VSCode Remote-SSH 개발환경 확정 |
| #11 | feat(fe): 지도 검색 페이지 카카오맵 + 신뢰도 색 마커 |
| #9 | feat: Kiro 컨텍스트 공유 (`.kiro/steering/`) + docs/ 위치 통일 |
| #8 | feat(be): uvicorn EC2 진입점 (`be/main.py`) |
| #6 | feat(be): EC2 셋업 — `S3Adapter` 로컬 FS, `kakao_adapter`, systemd, FastAPI 응답 포맷 |

---

## 8. 운영 메모

### 계정 분리 (2026-05-25)
BE(`kmuproj-02`)·AI(`kmuproj-10`) 각자 자기 자원. 발표 정본은 BE 풀커버, AI 미니 표본은 개발용 — 단 single-table 재설계 후 이 분리도 재검토 필요 (양쪽이 같은 single-table 스키마면 데이터 이관 가능성).

### KB 공유 운영 규약 (강사 정책)
KB `kmuproj-team-03`(ID `GTBJ6HLFDK`) DataSource S3 `kmuproj-02-vector` 는 02·10·11팀 공유.

- Prefix 분리: `clinic-focus/prod/` · `clinic-focus/probe/`
- Delete 운영 코드 금지 (soft-delete: `metadata.status="closed"`)
- `team_id="clinic-focus"` 메타 필수 (Retrieve 필터 격리)

### Bedrock 모델 라우팅 (2026-05-26)
- 텍스트 LLM (Haiku 4.5) → 개인 계정 `ap-northeast-2` (지원 계정 inference profile 라우팅 deny)
- Vision (Sonnet 4.6) → 개인 계정 `ap-northeast-2` (Global cross-region inference profile)
- Titan Embed v2 → 지원 계정 `us-east-1` (KB 자동 호출)

### 의료법 §56 회피 — 후기 데이터 처리 (외부 시그널 시 절대 어기지 말 것)

| 항목 | 허용 | 금지 |
|---|---|---|
| 후기 본문 저장 | DDB 에 raw 저장 (내부 분석용) | — |
| 후기 본문 사용자 노출 | — | 개별 후기 본문 그대로 화면에 표시 ❌ |
| 후기 키워드 노출 | "친절·아토피·여드름·꼼꼼 키워드 빈도 N건" | — |
| AI 통합 설명에서 인용 | "후기 키워드 빈도 ~%" (출처 배지 `[후기]`) | "후기에서 호평" 같은 평가형 어조 ❌ |

### main 브랜치 직접 수정 금지
PreToolUse hook + pre-commit hook 양쪽 차단. 모든 작업은 feature 브랜치.
