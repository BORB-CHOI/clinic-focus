# clinic-focus 작업 큐 — V2 sprint

> 최종 업데이트: 2026-05-26 · 상위 컨텍스트: [`../overview.md`](../overview.md), [`../dev-roadmap.md`](../dev-roadmap.md)

이 문서는 **V2(본 서비스 9가지 차별점 모두 동작)까지 남은 작업**을 한 곳에 모은 단일 큐다. 트랙 분담·완료 히스토리·운영 메모도 같이 포함. 별도 `be-aws-wiring.md`·`task-queue-cleanup-handoff.md`는 본 문서로 흡수 후 삭제(2026-05-26).

---

## 0. 지금 사실 (Snapshot, 2026-05-26)

| 영역 | 상태 |
|---|---|
| AI dev e2e (강남구 4과목 88개 → 분류 14개 → KB ingest → 자연어 검색) | ✅ scratch 우회로 통과 (PR [#25](https://github.com/BORB-CHOI/clinic-focus/pull/25)) |
| AI 트랙 자기 계정 DDB·S3·KB ingest 권한 | ✅ 전부 통과 |
| AI 트랙 본체 함수 (`ingest_hospital` / `retrieve_hospital`) | ❌ scratch만 있고 본체 미구현 |
| BE 본체 코드 (s3_adapter boto3 / crawl_all TABLE_PREFIX) | ⏳ 이슈 [#23](https://github.com/BORB-CHOI/clinic-focus/issues/23) 위임 |
| BE FastAPI 4개 엔드포인트 실데이터 동작 | ❌ skeleton 수준, AI 호출·DDB 적재 미연결 |
| FE 검색·상세·지도 화면 | △ 화면 골격 OK (PR [#14](https://github.com/BORB-CHOI/clinic-focus/pull/14)), 실 API 미연결 |
| Vision 시그널 (트랙 C) | ❌ 개인 계정 Marketplace 구독 미완료로 fallback |
| 블로그·후기 시그널 | ❌ 크롤러 자체 부재 (이슈 [#18](https://github.com/BORB-CHOI/clinic-focus/issues/18)) |
| 분류 변경 자동 기록·피드백 자기교정 | ❌ 미구현 |
| HTML 잡음 정제·hash diff | ❌ 이슈 [#13](https://github.com/BORB-CHOI/clinic-focus/issues/13) 위임 |

---

## 1. V2 매트릭스 — 9가지 차별점 vs 현 상태

`overview.md` 4·5절과 `dev-roadmap.md` Phase 1·2의 핵심 기능. **이 표가 V2의 정의**.

| # | 기능 | 출처 | 현 상태 | 남은 일 |
|---|---|---|---|---|
| 1 | 자연어 검색 (KB Retrieve) | [overview 4-5](../overview.md#4-5-검색-동작-원리--semantic-search--사전-증거-평가) | ✅ scratch 4쿼리 통과 | `ai/scratch/retrieve_test.py` → `ai.retrieve_hospital` 본체로 |
| 2 | 상세 페이지 9개 영역 | [overview 4-4](../overview.md#4-4-ai-통합-상세-설명--본-서비스의-진짜-차별점), [API-FE-BE §2](../API-FE-BE.md#2-병원-상세) | ❌ FE/BE 골격만 | FE 9영역 컴포넌트 + BE 통합 응답 + AI `extract_services_and_doctors` 실측 |
| 3 | AI 통합 설명 (`generate_description`) | [overview 4-4](../overview.md#4-4-ai-통합-상세-설명--본-서비스의-진짜-차별점) | △ 14개 동작, 신뢰도 약점 2건 | `primary_focus=[]` + `confidence=100` 케이스 수정 (`ai/scratch/run-log-2026-05-26.md` 참조) |
| 4 | 4 시그널 교차 검증 | [overview 5-1](../overview.md#5-1-자기-파괴-방지--4-시그널-교차-검증) | △ 자칭만, Vision/블로그/후기 0% | 개인 계정 Sonnet Marketplace 구독 + 이슈 [#18](https://github.com/BORB-CHOI/clinic-focus/issues/18) 외부 시그널 크롤러 |
| 5 | 신뢰도 + 피드백 자기교정 | [overview 5-2](../overview.md#5-2-ai-분류-신뢰도-시스템) | ❌ | `recompute_confidence`·`aggregate_feedback_stats` 본체 |
| 6 | 분류 변경 이력 자동 기록 | [overview 10-3](../overview.md#10-3-변경-이력--사용자-가치-전환), [API-FE-BE §3](../API-FE-BE.md#3-분류-변경-이력) | ❌ 테이블만 | hash diff → `ChangeHistory` INSERT 로직 |
| 7 | 피드백 (디바이스ID 중복방지) | [API-FE-BE §4](../API-FE-BE.md#4-피드백-제출) | ❌ | `POST /api/feedback` 본체 + FE 1-tap UI |
| 8 | 관련 병원 추천 | [API-FE-BE §2](../API-FE-BE.md#2-병원-상세) (영역 ⑧) | △ 코드, 실측 X | `find_related_hospitals` 실측 |
| 9 | 카테고리 이중 색인 (다루지 않는 분야) | [overview 4-2](../overview.md#4-2-분류-체계--카테고리-이중-색인) | △ 코드, 실측 X | `extract_services_and_doctors` 실측 |

---

## 2. V2 sprint — 트랙별 잔여 작업

### AI 트랙 (최비성)

**A. 본체 마이그레이션 (이슈 #23 머지 후 진입)**

- [ ] `ai/search/kb_store.py` 신규 — `ingest_hospital(hospital_id, content_text, metadata, trigger_ingestion=False)` 본체. scratch `kb_ingest.py` 로직 흡수 + 실측 함정(metadata dict 형식 / 빈 list 거절 / `team_id` 필수) 반영
- [ ] `ai/search/kb_store.py` — `retrieve_hospital(query: SearchQuery) -> list[SearchResult]` 본체. scratch `retrieve_test.py` 로직 흡수
- [ ] `ai/__init__.py` export: `ingest_hospital`, `retrieve_hospital` 추가 / `index_hospital`, `search_similar` 제거
- [ ] `ai/scratch/` 통째 삭제 (PR 분리 권장 — 본체 마이그레이션 PR 검증 후)

**B. 시그널 보강·신뢰도**

- [ ] 신뢰도 약점 수정 — `primary_focus=[]` + `confidence=100` 케이스 (`ai/scratch/run-log-2026-05-26.md` 참조)
- [ ] 개인 계정 Bedrock Sonnet 4.6 AWS Marketplace 구독 완료 → Vision 시그널 활성화
- [ ] `extract_services_and_doctors` 실측 — "다루지 않는 분야" 정확도
- [ ] `find_related_hospitals` 실측

**C. 자기교정 루프**

- [ ] `recompute_confidence(hospital_id, recent_feedback) -> Confidence` 본체
- [ ] `aggregate_feedback_stats(hospital_id) -> FeedbackStats` 본체

**D. 표본 확장 (선택)**

- [ ] 강남구 4과목 88개 → 서울 5개구 4과목 ~1000개 (BE 풀크롤링 완료 후)

### BE 트랙 (김경재)

**E. AWS 본체 연동 (이슈로 위임됨)**

- [ ] [이슈 #23](https://github.com/BORB-CHOI/clinic-focus/issues/23) `be/adapters/s3_adapter.py` 로컬 FS → boto3 + `be/scripts/crawl_all.py:35` `TABLE_PREFIX` 적용
- [ ] [이슈 #24](https://github.com/BORB-CHOI/clinic-focus/issues/24) `be/scripts/_utils.load_env` 인라인 주석 버그
- [ ] [이슈 #13](https://github.com/BORB-CHOI/clinic-focus/issues/13) HTML 잡음 정제 + hash diff (`content_hash` 컬럼)
- [ ] [이슈 #18](https://github.com/BORB-CHOI/clinic-focus/issues/18) 병원 목록 소스 전략 + 블로그·후기 외부 시그널 크롤러

**F. FastAPI 4개 엔드포인트 본체 구현**

- [ ] `GET /api/search` — KB Retrieve 호출 + DynamoDB 신뢰도 조회 + 정렬 ([API-FE-BE §1](../API-FE-BE.md#1-검색))
- [ ] `GET /api/hospitals/{id}` — 9개 영역 통합 응답 ([API-FE-BE §2](../API-FE-BE.md#2-병원-상세))
- [ ] `GET /api/hospitals/{id}/history` — `ChangeHistory` 조회 ([API-FE-BE §3](../API-FE-BE.md#3-분류-변경-이력))
- [ ] `POST /api/feedback` — 디바이스ID 중복 방지 + 201/409 응답 ([API-FE-BE §4](../API-FE-BE.md#4-피드백-제출))

**G. DDB·CORS·환경 마무리**

- [ ] ⭐ **0순위 결정 — DDB 형태 통일.** BE는 single-table(`kmuproj-02-team3-backend`, PK=`hospital_id`+SK=`entity`, 3124 items) 가동 중인데 `be/scripts/setup_dynamodb.py`+`be/adapters/dynamo_adapter.py`는 7-table 가정. FastAPI 4개 엔드포인트가 어느 어댑터를 쓰는지 확정 안 됨. 택1: (a) AI도 single-table로 전환 / (b) `dynamo_adapter.py`를 single-table로 교체하고 AI 7-table 유지하려면 별도 어댑터 / (c) 양쪽 가정 동시 지원. 이거 정해야 §F 본체 진입 가능
- [ ] `ChangeHistory` 자동 INSERT 로직 (`classify_hospital` 결과 변경 시) — 위 결정 따라 single-table entity 또는 별 테이블에 적재
- [ ] `be/handlers/api.py` CORS `allow_origins=["*"]` → CloudFront 도메인 + `localhost:5173` 한정
- [ ] `.env.example` BE 자기 계정 변수 (`TABLE_PREFIX=kmuproj-02-clinic-` 또는 single-table 이름, `S3_CRAWL_BUCKET=kmuproj-02-clinic-focus-crawl`) 주석 갱신

### FE 트랙 (하재원)

**I. 화면·API 통합**

- [ ] OpenAPI → TS 타입 자동 생성 동기화 (`openapi-typescript`)
- [ ] `SearchPage.tsx` 실 API 연결 (TanStack Query). Mock 제거
- [ ] `HospitalDetailPage.tsx` 9개 영역 컴포넌트 완성 (헤드라이너/핵심진료/의료진/신뢰도/운영/피드백/이력/관련/메타)
- [ ] `MapPage.tsx` 카카오맵 + 신뢰도 색 마커 — `lat`/`lng` 메타필터 검색과 결합
- [ ] 1-tap 피드백 UI (👍/👎) + localStorage 디바이스ID + 중복 방지 처리
- [ ] 분류 변경 이력 표시 컴포넌트

**J. 차등 렌더링**

- [ ] `ai_description == null` 케이스 태그 카드 fallback ([API-FE-BE §2](../API-FE-BE.md#2-병원-상세) 프론트 렌더링 가이드)

### 공통

- [ ] 의료법 회색지대 표현 전수 검수 (`medical-language-reviewer` 서브에이전트)
- [ ] `shared/models.py` 모델 변경 시 BE·AI 동시 갱신 확인
- [ ] 통합 e2e — FE 검색창 → BE → AI → KB → 응답 → 상세 페이지 9영역 렌더 (M3 데모)

---

## 3. 마일스톤 (~3주)

| 주 | AI | BE | FE |
|---|---|---|---|
| 1 | scratch → 본체 (`ingest_hospital`/`retrieve_hospital`) | 이슈 #23/#24 머지 + API 4개 skeleton | 검색 결과 페이지 API 연결 |
| 2 | `extract_services_and_doctors`·`find_related_hospitals` 실측 + 신뢰도 약점 수정 | API 4개 본체 + DDB 적재 로직 + `ChangeHistory` INSERT | 상세 페이지 9영역 |
| 3 | 시그널 보강 (Vision Marketplace + 이슈 #18 머지 후 블로그/후기) + `recompute_confidence` | 이슈 #13 정제·hash diff | 피드백 UI + 변경 이력 + 의료법 검수 |

---

## 4. AI 트랙 AWS 워크북 (개인 진행 기록)

> 재현 가이드는 [`../setup/aws-onboarding.md`](../setup/aws-onboarding.md). 이 섹션은 최비성 개인 진행 체크리스트.

| Step | 내용 | 상태 |
|---|---|---|
| 0 | VSCode Remote-SSH → EC2 접속 | ✅ |
| 1 | 지원 계정 자격증명·Bedrock 모델 가용성 (Titan v2 / Haiku / Nova / KB `GTBJ6HLFDK`) | ✅ |
| 2 | Titan v2 임베딩 hello-world (1024 dim, 비트 단위 재현성) | ✅ |
| 3 | KB Retrieve 왕복 — DataSource S3 ingest 권한 | ✅ 2026-05-25 강사 권한 부여 후 통과 |
| 4 | DataSource S3 파일 포맷 + metadata 스키마 (`team_id` 필수, dict 형식, 빈 list 거절) | ✅ |
| 5 | 개인 계정 Sonnet 4.6 Vision (서울, Global cross-region, 3-ARN IAM) | ✅ Marketplace 구독은 미완료로 fallback |
| 6 | DDB 7테이블 수동 생성 + S3 버킷 생성 + 88개 HIRA 적재 + 14개 크롤 + 14개 분류·설명 + KB ingest + 자연어 검색 4쿼리 | ✅ PR [#25](https://github.com/BORB-CHOI/clinic-focus/pull/25) |

상세 진행 기록·실측 응답은 [`../setup/aws-onboarding.md`](../setup/aws-onboarding.md) Step 1~6, [`ai/scratch/run-log-2026-05-26.md`](../../ai/scratch/run-log-2026-05-26.md) 참조.

---

## 5. 완료된 PR (최근순)

| PR | 제목 |
|---|---|
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

## 6. 운영 메모

### 계정 분리 (2026-05-25 확정)
BE(`kmuproj-02`)와 AI(`kmuproj-10`)가 각자 DynamoDB·S3 따로 운영. 데이터 공유 없음. 발표 정본은 **BE 계정 풀커버**, AI 계정 미니 표본은 개발·튜닝용.

### KB 공유 운영 규약 (강사 정책)
KB `kmuproj-team-03`(ID `GTBJ6HLFDK`) DataSource S3 `kmuproj-02-vector`는 02·10·11팀 공유.

- **Prefix 분리 필수** — `clinic-focus/prod/`, `clinic-focus/probe/`
- **Delete 운영 코드에서 호출 금지** — soft-delete(`metadata.status="closed"`)로 우회
- **`team_id="clinic-focus"` 메타 필수** — Retrieve 필터로 격리

### Bedrock 모델 라우팅 (2026-05-26 확정)
- 텍스트 LLM (Haiku 4.5) → **개인 계정 `ap-northeast-2`** (지원 계정은 us-east-2/us-west-2 inference profile 라우팅이 explicit deny)
- Vision (Sonnet 4.6) → **개인 계정 `ap-northeast-2`** (Global cross-region inference profile)
- Titan Embed v2 → **지원 계정 `us-east-1`** (KB가 자동 호출)

자세한 건 [`../../CLAUDE.md`](../../CLAUDE.md) "AWS 계정·인프라 구조" 섹션.

### `be/data/crawl_results/` 28개 처리
BE 계정 ykiho 기반이라 AI 계정 데이터와 매핑 불가. **버리고 새로 시작** — 이슈 #13 정제 검증 끝나면 `.gitignore` + 삭제 (2026-05-26 결정).

### main 브랜치 직접 수정 금지
`.claude/settings.json` PreToolUse hook이 main에서 Edit/Write 차단. `.git/hooks/pre-commit`이 main 직접 커밋 차단. 모든 작업은 `feat/` / `fix/` / `refactor/` / `docs/` 접두사 feature 브랜치.
