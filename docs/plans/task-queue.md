# clinic-focus 작업 큐

> 최종 업데이트: 2026-05-24

---

## 진행 중인 결정사항 (2026-05-24 갱신)

**AI 트랙 전략 재편** — 지원 계정 Bedrock 제약(Haiku/Nova + 10개 한도) 확인에 따라 3트랙으로 분리.

| 트랙 | 대상 | 모델 | 계정 | 범위 |
|---|---|---|---|---|
| A. 룰 기반 분류 | 자칭 컨셉 추출 | 키워드/빈도 룰 (LLM 미사용) | — | 서울 5개구 1만 |
| B. LLM 텍스트 시연 | 자칭 추출 + `generate_description` | Haiku 4.5 / Nova | 지원 | 10개 |
| C. Vision 시연 | 이미지 분석 (OCR + 시각) | Sonnet 4.5 | 개인 | 10개 |

확정 사항:

- 벡터 도구: S3 Vectors 직접 호출 (KB 안 씀)
- 벡터 버킷: 지원 계정 `bedrock-knowledge-base-1tvot3`
- 임베딩: Titan v2 (지원 계정, 전체 1만)
- OCR: Bedrock Vision으로 흡수 (Textract 한국어 미지원으로 제거)
- 정제: BE 책임 (페이지 간 중복 단락 제거 + 의료 사이트 잡음 블랙리스트)
- 사업화 시 갱신: hash diff 기반 부분 재처리 (전국 7만 운영 시 월 ~$700)

---

## 다음 PR 순서

### 1. `feat/ai/aws-clients` (기존 항목 — 재설계 필요)

담당: 최비성

> 원본 계획이 "Bedrock·S3 Vectors·Textract 모두 개인 계정" 전제였으나, 2026-05-24 결정으로 **S3 Vectors·Titan·Haiku/Nova는 지원 계정**, Sonnet 4.5(Vision)만 개인 계정으로 변경. `ai/core/aws_clients.py` 는 만들어졌으나 재설계 필요.

- [ ] `ai/core/aws_clients.py` 재설계
  - 지원 계정 클라이언트 팩토리: `get_bedrock_runtime_support()` (Haiku/Nova/Titan), `get_s3vectors_client()` (인스턴스 프로파일)
  - 개인 계정 클라이언트 팩토리: `get_bedrock_runtime_personal()` (Sonnet Vision 시연용, `AI_AWS_*` 환경변수)
  - 기존 Textract 클라이언트 함수 제거

- [ ] AI 모듈 팩토리 호출 교체 (계정 분리 반영)
  - `ai/core/bedrock_client.py` — 트랙 B는 지원 / 트랙 C는 개인
  - `ai/search/embed.py` — 지원 계정 Titan
  - `ai/search/vector_store.py` — 지원 계정 S3 Vectors
  - `ai/pipeline/vision.py` — 개인 계정 Sonnet (Textract 호출 제거)

- [ ] `ai/search/feedback.py` — DynamoDB 지원 계정 팩토리로 교체

- [ ] `ai/search/vector_store.py` — `index_hospital` 시그니처 통합
  - `sido`, `sigungu`, `lat`, `lng` 파라미터 추가
  - `index_hospital_with_meta` 제거 (통합)

- [ ] `ai/__init__.py` — 업데이트된 시그니처 export

### 2. `feat/be/test-fix` (기존 항목, 변동 없음)

담당: 김경재

- [ ] `be/tests/harness/mock_adapters.py`
  - `h.sigungu` → `h.location.sigungu` 버그 수정
  - `ChangeRecord` → `ClassificationChange` import 명시화

- [ ] 미사용 import 정리
  - `be/api/search.py` — `SearchQuery` 제거
  - `be/adapters/dynamo_adapter.py` — `import json` 제거

- [ ] smoke_test — `import` 검증 추가

### 3. `feat/be/clean-noise` (신규 — BE에 정제 추가 요청)

담당: 김경재

> 근거: AI 트랙이 28개 샘플(`be/data/crawl_results/*.json`) 분석한 결과 잡음 60~70%. 룰 기반 분류 트랙 A의 정확도와 LLM 호출 비용 양쪽에 직접 영향.

핵심 발견:

- modoo 서비스 종료 안내 18회 반복 (네이버 modoo 사이트들)
- 같은 사이트 안에서 푸터/메뉴 9회 반복 (`<footer>` 태그 안 쓰는 사이트들)
- 404 페이지 6회 반복
- "개인정보취급방침", "환자권리장전" 등 의료 사이트 공통 법정 고지문

작업:

- [ ] `be/core/crawler.py` — 페이지 간 중복 단락 자동 검출·제거 로직 (한 사이트의 여러 페이지에서 N회 이상 반복되는 단락을 푸터/메뉴로 판정)
- [ ] 잡음 키워드 블랙리스트 단락 제거 (modoo 안내, 개인정보취급방침, 환자권리장전, 이용약관, 비급여 진료비용 고지문, 404, Copyright 등)
- [ ] 정제 후 텍스트 100자 미만 → "정보 부족"으로 분류 대상에서 제외
- [ ] `be/data/crawl_results` 28개로 정제 효과 비교 테스트 (정제 전/후 토큰 수)

### 4. `feat/ai/track-a-rule-classifier` (신규 — 트랙 A)

담당: 최비성

- [ ] `ai/pipeline/classify_rule.py` 신규 — 룰 기반 자칭 컨셉 추출
  - 진료과목별 키워드 사전 (피부과: "여드름", "아토피", "보톡스" 등)
  - 키워드 빈도 + 페이지 타입별 강조도 계산
  - 4시그널 중 자칭 + 블로그 + 공공데이터 룰 기반 처리
- [ ] 룰 기반 신뢰도 점수 산출 (LLM 결과보다 보수적)
- [ ] `ai/scripts/classify_all_rules.py` — 서울 1만 일괄 처리 스크립트
- [ ] `classify_hospital(crawl_data, use_llm=False)` 분기 추가

### 5. `feat/ai/track-bc-llm-vision-demo` (신규 — 트랙 B·C)

담당: 최비성

- [ ] 시연 대상 10개 병원 선정 (강남구, 진료과목 다양, 사이트 풍부)
- [ ] 트랙 B: 지원 계정 Haiku/Nova로 자칭 추출 + `generate_description`
- [ ] 트랙 C: 개인 계정 Sonnet 4.5 Vision으로 이미지 분석
- [ ] 룰 기반 결과 vs LLM 결과 비교 출력 (발표 자료용)
- [ ] `MAX_LLM_DEMO_HOSPITALS` 환경변수로 한도 강제

### 6. `feat/be/hash-diff-foundation` (신규 — 사업화 갱신 전략 기반)

담당: 김경재

> 사업화 시 운영 비용 통제의 핵심. PoC 단계에서 구조만 잡아두고 운영은 수동 트리거로 충분.

- [ ] `Hospitals` 테이블에 `body_hash` (페이지별), `crawled_at` 컬럼 추가
- [ ] 재크롤링 시 페이지 본문 hash 비교 → 변경된 페이지만 다시 AI 큐에 적재
- [ ] 변경 이력 자동 기록 (`ChangeHistory` 테이블 — 이미 스키마 있음)

---

## AI 트랙 AWS 세팅 todo (개인 워크북)

> 최비성 개인용. PR로 안 올림. Cloud9에서 진행.

- [ ] **Step 1**: Cloud9 환경 만들거나 열기 + 지원 계정 자원 확인
  - `aws sts get-caller-identity` → 계정 ID `730335373015` 확인
  - `aws s3vectors list-vector-buckets --region us-east-1` → `bedrock-knowledge-base-1tvot3` 보이는지
  - `aws bedrock list-foundation-models --region us-east-1 --query "modelSummaries[?contains(modelId, 'titan-embed') || contains(modelId, 'haiku') || contains(modelId, 'nova')].modelId"` → Titan + Haiku/Nova 가용성
  - `pip3 install boto3 --upgrade`
- [ ] **Step 2**: Titan v2 임베딩 호출 hello-world
- [ ] **Step 3**: S3 Vectors `PutVectors` + `QueryVectors` 왕복 테스트 (1024차원 더미 벡터 5개)
- [ ] **Step 4**: Vector 스키마 설계 (ID 규칙 + 메타데이터 키 확정)
- [ ] **Step 5**: 개인 계정 Sonnet 4.5 Access Key 발급 + Vision 호출 테스트 (Bedrock model access 활성화 → IAM User 생성 → Access Key 발급 → Cloud9 `~/.aws/credentials`에 named profile로 저장 → boto3 `Session(profile_name="personal")`)

---

## be/data/crawl_results 처리

> 28개 크롤링 결과 파일 (성북구 요양/대학병원 위주). AI 트랙이 정제 효과 검증용으로 사용 중.

- [ ] 김경재 양해 후 `feat/be/clean-noise` 완료 시점에 정제 효과 검증 끝나면 `.gitignore`에 `be/data/crawl_results/` 추가하고 삭제

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
- [x] `ai/core/aws_clients.py` 신규 (단, 2026-05-24 결정으로 재설계 필요 — PR #1에서 처리)
