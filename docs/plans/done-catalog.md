# 수행 작업 카탈로그 (완료 누적)

> 완료된 작업의 한 줄 요약 누적 기록. 상세 잔여 작업은 [`task-queue.md`](task-queue.md),
> 함수 명세는 [`../API-BE-AI.md`](../API-BE-AI.md). 본 문서는 "무엇이 이미 됐나"의
> 단일 조회처 — task-queue 의 `[x]` 가 흩어져 있어 한곳에 모은다.
>
> 최초 작성: 2026-05-28 (전수 검사 정리 세션). 이후 작업은 아래에 한 줄씩 추가.

---

## 기반 (Phase A)

- **DDB V2 single-table 전환** — 7-table → `PK=hospital_id + SK=entity` 단일 어댑터(`be/adapters/dynamo_adapter.py`) 재작성, generic primitives + typed helper. 콘솔 수동 생성(`kmuproj-10-clinic-Main` ACTIVE, GSI 2개). PR #28
- **shared/models 4 시그널 + 외부 소스 모델 확장** — `KakaoPlace/Reviews/Blog`·`NaverPlace/Blog`·`GoogleReviews`·`ExternalSignalBundle` 등 (모두 `extra="ignore"`, PII 필드 없음). PR #34/#35
- **분류 스키마 22 진료과목 후보군 확정** — 강남 502 실측 + 민간 3사 비교, 표본 ~94% 커버. 분석노트 [`specialty-schema-analysis-2026-05-27.md`](specialty-schema-analysis-2026-05-27.md). PR #30
- **외부 API 키 발급·검증** — 카카오/구글 Places/네이버 검색 API + 개인계정 Sonnet 4.6 Vision(`.env` 실측). PR #30
- **BE 차단 이슈 머지** — `s3_adapter` boto3 전환, `crawl_all.py` single-table 정합(#23), `load_env` 인라인 주석 버그(#24)

## 외부 시그널 크롤러 (Phase B)

- **HTML 잡음 정제** — `be/core/crawler.py` `_denoise_pages`(페이지 간 반복 단락 검출) + 잡음 블랙리스트(비급여 제외). 이슈 #13
- **카카오 어댑터** — `be/adapters/kakao_place_adapter.py` 공식 `dapi.kakao.com`→place_id→`place-api` panel3/reviews/blog httpx 단발 + 순수 파서 + PII 제거. PR #34
- **네이버 플레이스 어댑터** — `be/adapters/naver_place_adapter.py` Playwright headless ncpt 토큰 자동 → graphql getVisitorReviews + `parse_place`(후기 본문 보존, 작성자 PII 미보존). PR #36
- **네이버 블로그 어댑터** — `be/adapters/naver_blog_adapter.py` 공식 `v1/search/blog` + `parse_naver_blog`(HTML 정제). PR #36
- **구글 Places 어댑터** — `be/adapters/google_places_adapter.py` Text Search→Details(reviews 5건) + `parse_google_reviews`(작성자·사진 PII 미보존). PR #35
- **외부 크롤 배치 골격** — `be/scripts/crawl_external_all.py` 기본 dry-run, `--confirm`/`--source` 가드. PR #35
- **probe 실측·본체화** — 네이버·카카오 비공식 엔드포인트 실측(사실 1~24, [`external-crawl-findings-2026-05-28.md`](external-crawl-findings-2026-05-28.md)), 샘플은 `be/tests/fixtures/{kakao,naver}` 로 본체화

## AI 본체 + 4 시그널 통합 (Phase C)

- **KB 경유 ingest/retrieve** — `ai/search/kb_store.py` `ingest_hospital`(시그널별 청크 S3 적재)·`retrieve_hospital`(KB Retrieve + 메타필터 + bounding box haversine) + 청크 빌더(`build_signal_chunks`·`build_ingest_metadata`). 옛 S3 Vectors `vector_store.py` 폐기. PR #34/#35
- **`classify_hospital` 룰 경로 + 외부 시그널** — `use_llm=False` 룰 단독(Bedrock 0회, 1만), 카카오 tags→자칭 보강, 카카오/네이버/구글 후기→`_analyze_reviews`, 도배 페널티, 룰 70 cap. PR #34/#35
- **`generate_description` 4 시그널 종합** — `detailed_signals` 종합, citations 강제 검증(규칙2 위반 에러), 의료법 5규칙, 재시도 MAX_RETRIES=2
- **`extract_services_and_doctors`** — services/excluded_services/equipment, Vision+public_data 기기 중복 제거
- **`find_related_hospitals`** — same_focus(KB+시군구)/fills_gap(excluded 순회)/haversine + `alternative_hospital_ids` in-place
- **`recompute_confidence`·`aggregate_feedback_stats`** — V2 single-table(PK+SK) 정합, 피드백 임계 감점/보너스. PR #35
- **분류 변경 자동 기록** — `_record_classification_change` primary_focus diff 시 `HISTORY#` INSERT. PR #35
- **Bedrock mock 의무화** — ai 단위 테스트 전부 mock, 실 호출 0
- **`ai/pipeline/vision.py` 본체** — `analyze_images` Bedrock Vision + MAX_VISION_IMAGES (활성화는 Marketplace 대기)

## BE FastAPI 4개 엔드포인트 (Phase D)

- **`GET /api/search`** — 자연어/위치 `retrieve_hospital`, 시군구 단독 DDB GSI, `_hospital_card` join, search_mode. PR #35
- **`GET /api/hospitals/{id}`** — 9영역 DDB join + 404 + completeness
- **`GET /api/hospitals/{id}/history`** — `load_recent_changes`
- **`POST /api/feedback`** — verdict 422→400, device_id+hospital_id 409, 임계 도달 시 `recompute_confidence` inline graceful. PR #35
- **응답 포맷·에러 코드** — `{data,meta}`/`{error}`, 표준 코드 매핑(400/404/409/502), CORS env 주입
- **`run_index_pipeline`** — demo=False 룰 베이스라인 / demo=True LLM·Vision, `load_external_signals` `**` 전개 + 변경 자동 기록

## 정리 세션 (2026-05-28)

- **scratch/ 제거** — 우회 스크립트·probe 일괄 삭제(샘플은 fixtures 본체화, 분석노트는 docs 이전)
- **폐기 S3 Vectors 잔재 제거** — `setup_vectors.py`·`get_s3vectors_client` (KB 경유 전환 완료)
- **문서 정합** — ai/CLAUDE.md 옛 시그니처 갱신, 죽은 scratch 링크 정리, TABLE_PREFIX 제거
- **task-queue 슬림화** — Phase B raw 노트(사실 1~24) → findings 문서 이전, 9차별 매트릭스 코드 정합 갱신
