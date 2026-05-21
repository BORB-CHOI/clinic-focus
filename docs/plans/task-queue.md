# clinic-focus 작업 큐

> 최종 업데이트: 2026-05-22

---

## 다음 PR 순서

### 1. `feat/ai/aws-clients`

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

### 2. `feat/be/test-fix`

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

### PR #9 — `feat/kiro-compat` (머지 완료)

- [x] `.kiro/steering/` 4개 파일 생성 (`inclusion: always`)
- [x] `docs/` 중립 위치로 4대 문서 이동 (`overview`, `dev-roadmap`, `API-FE-BE`, `API-BE-AI`)
- [x] 참조 경로 15개 파일 일괄 업데이트

### PR #8 — `feat/be/mangum-removal` (머지 완료)

- [x] `be/main.py` uvicorn 진입점 생성 (Mangum은 PR #6에서 이미 제거됨)

### PR #7 — `chore/task-docs` (머지 완료)

- [x] `docs/plans/task-queue.md` 작업 큐 문서 신규
- [x] 기존 `docs/superpowers/plans/` 삭제 (통합)

### PR #6 — `feature/be/ec2-setup` (머지 완료)

- [x] `be/api/search.py` — 파라미터 에러 422, 자연어 검색 note 반환
- [x] `.env.example` — 전체 버전 복원 + `KAKAO_REST_API_KEY` 추가
- [x] `be/adapters/dynamo_adapter.py` — float→Decimal, sigungu denormalize, 리전 us-east-1
- [x] `be/api/feedback.py` — 201/409, 응답 포맷 통일
- [x] `be/api/hospital.py`, `be/api/search.py` — `{"data": ...}` 포맷 통일
- [x] `ai/pipeline/classify.py`, `extract.py` — `public_data=None` null 가드
- [x] `shared/models.py` — `public_data: PublicData | None = None`
- [x] `be/adapters/kakao_adapter.py`, `naver_map_adapter.py` 신규
- [x] `deploy/` — systemd 서비스·셋업 스크립트·README

### 기타 (main 반영됨)

- [x] GitHub 이슈 #1·#2·#3 생성
- [x] `be/scripts/setup_dynamodb.py`, `ai/scripts/setup_vectors.py` 인프라 초기화 스크립트
