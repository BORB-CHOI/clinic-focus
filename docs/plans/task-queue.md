# clinic-focus 작업 큐

> 최종 업데이트: 2026-05-22  
> 참조: PR #6 리뷰 + `2026-05-21-infra-credential-split.md` (통합 후 삭제)

---

## 현재 진행 중 — PR #6 수정 후 머지

브랜치: `feature/be/ec2-setup` (열려 있음)

### 머지 전 필수 수정 (HIGH)

- [ ] `be/api/search.py` — 파라미터 에러 HTTP 200 → 422로 수정
- [ ] `be/api/search.py` — `q`만 있고 `sigungu` 없을 때 빈 결과 대신 명시적 note 반환
- [ ] `.env.example` — `KAKAO_REST_API_KEY` 추가

### 머지 후 별도 이슈 추적 (MEDIUM)

- [ ] `be/api/hospital.py` `_calc_completeness` — ⑥⑦⑧ 카운트 누락, 최대 0.78 버그
- [ ] `be/adapters/kakao_adapter.py`, `naver_map_adapter.py` — `httpx.Client` 미해제
- [ ] `shared/models.py` `ClassificationChange` — 명세서 기준으로 필드명 확정

---

## 다음 PR 순서

### 1. `feat/be/mangum-removal`

담당: 김경재

- [ ] `be/handlers/api.py` — Mangum import 및 `handler = Mangum(app)` 제거
- [ ] `be/main.py` 신규 생성 — uvicorn 진입점
- [ ] `requirements.txt` — `mangum>=0.17.0` 제거
- [ ] `.env.example` — 26줄 전체 버전 복원 (PR #6에서 4줄로 덮어써짐)

  복원 대상 변수:
  ```
  AWS_REGION, AI_AWS_ACCESS_KEY_ID, AI_AWS_SECRET_ACCESS_KEY,
  AI_AWS_SESSION_TOKEN, AI_AWS_PROFILE, AI_AWS_REGION,
  BEDROCK_LLM_MODEL_ID, BEDROCK_EMBED_MODEL_ID,
  S3_VECTOR_BUCKET, S3_VECTOR_INDEX, TABLE_PREFIX,
  CRAWL_S3_BUCKET, PORT, MAX_VISION_IMAGES,
  CONFIDENCE_THRESHOLD_HIGH, CONFIDENCE_THRESHOLD_LOW,
  KAKAO_REST_API_KEY, NAVER_MAP_CLIENT_ID, NAVER_MAP_CLIENT_SECRET,
  HIRA_API_KEY, CRAWL_DATA_DIR
  ```

---

### 2. `feat/kiro-compat`

담당: 최비성 또는 공통

**목표:** Kiro 사용자도 `.claude/` 컨텍스트를 동일하게 가져가도록.  
훅 실행·슬래시 커맨드는 Kiro 미지원이므로 제외. 컨텍스트 공유만.

- [ ] `docs/` 4개 파일 → `docs/` 루트로 이동
  - `overview.md`
  - `dev-roadmap.md`
  - `API-FE-BE.md`
  - `API-BE-AI.md`

- [ ] `docs/` 참조 경로 업데이트 (14개 파일)
  - `.claude/agents/` 8개
  - `ai/CLAUDE.md`, `ai/README.md`
  - `be/CLAUDE.md`, `fe/CLAUDE.md`, `shared/CLAUDE.md`
  - 루트 `CLAUDE.md`

- [ ] `.kiro/steering/` 생성 — 4개 파일
  - `00-project-context.md` — `docs/overview.md` + `docs/dev-roadmap.md` 통합
  - `01-coding-rules.md` — CLAUDE.md 핵심 (의료법 5규칙·Git 규칙·계정 분리·모듈 경계)
  - `02-agent-roles.md` — `.claude/agents/*.md` 역할 요약
  - `03-track-conventions.md` — be/fe/ai/shared CLAUDE.md 합본

  각 파일 프론트매터:
  ```yaml
  ---
  inclusion: always
  ---
  ```

- [ ] `docs/plans/task-queue.md` 경로 업데이트 (이 파일)

---

### 3. `feat/ai/aws-clients`

담당: 최비성

> 원본: `2026-05-21-infra-credential-split.md` Task 1·2·3·7

- [ ] `ai/core/aws_clients.py` 신규 — 계정별 boto3 세션 팩토리
  - 개인 계정: `AI_AWS_PROFILE=personal` 또는 `AI_AWS_ACCESS_KEY_ID` 환경변수
  - 지원 계정: EC2 인스턴스 프로파일 (기본 세션)

- [ ] AI 모듈 팩토리 교체 + 리전 `us-east-1` 통일
  - `ai/core/bedrock_client.py`
  - `ai/search/embed.py`
  - `ai/search/vector_store.py`
  - `ai/pipeline/vision.py`

- [ ] `ai/search/feedback.py` — DynamoDB 지원 계정 팩토리로 교체

- [ ] `ai/search/vector_store.py` — `index_hospital` 시그니처 통합
  - `sido`, `sigungu`, `lat`, `lng` 파라미터 추가
  - `index_hospital_with_meta` 제거 (통합)

- [ ] `ai/__init__.py` — 업데이트된 시그니처 export

---

### 4. `feat/be/test-fix`

담당: 김경재

> 원본: `2026-05-21-infra-credential-split.md` Task 6·13

- [ ] `be/tests/harness/mock_adapters.py`
  - `h.sigungu` → `h.location.sigungu` 버그 수정
  - `ChangeRecord` → `ClassificationChange` import 명시화

- [ ] 미사용 import 정리
  - `be/api/search.py` — `SearchQuery` 제거 (AI 모듈 제거 시 누락)
  - `be/adapters/dynamo_adapter.py` — `import json` 제거

- [ ] smoke_test — `import` 검증 추가
  - `from ai.core.aws_clients import get_bedrock_runtime_client`
  - `from be.handlers.api import app`
  - `from shared.models import ClassificationChange`
  - `from be.tests.harness.mock_adapters import MockDynamoAdapter`

---

## 완료된 작업

### PR #6 (`feature/be/ec2-setup`) — 머지 대기 중

- [x] `be/adapters/dynamo_adapter.py` — float→Decimal, sigungu/sido denormalize, 리전 us-east-1
- [x] `be/adapters/hira_adapter.py` — HospitalMeta 구조 정리 (location, contact 서브모델)
- [x] `be/api/feedback.py` — 중복 피드백 201/409, 응답 포맷 통일
- [x] `be/api/hospital.py`, `be/api/search.py` — `{"data": ...}` 응답 포맷 통일
- [x] `ai/pipeline/classify.py`, `ai/pipeline/extract.py` — `public_data=None` null 가드
- [x] `shared/models.py` — `public_data: PublicData | None = None`
- [x] `docs/API-BE-AI.md` — `index_hospital` 시그니처 문서 동기화
- [x] `be/adapters/kakao_adapter.py`, `naver_map_adapter.py` 신규
- [x] `deploy/` — systemd 서비스 파일·셋업 스크립트·README

### 이미 완료 (main 반영됨)

- [x] GitHub 이슈 #1·#2·#3 생성
- [x] `be/scripts/setup_dynamodb.py`, `ai/scripts/setup_vectors.py` 인프라 초기화 스크립트
