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
- 정제·크롤링: 전부 BE 책임 (잡음 제거 + 서울 1만 풀크롤링)
- 검색 시점 LLM 호출 0건 (Titan 임베딩만, 응답 ~200ms)
- 시연 10개 외 9990개는 `ai_description = null` (FE 차등 렌더링)
- 사업화 시 갱신: hash diff 기반 부분 재처리 (전국 7만 운영 시 월 ~$700)
- AI 트랙 개발 환경: AWS Cloud9 (지원 계정 인스턴스 프로파일 자동 인증 — 로컬에선 Access Key 없어 호출 불가)

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

> 의존성: BE의 서울 5개구 1만 풀크롤링(아래 #7) + 정제(#3) 가 끝나야 입력 데이터가 채워진다.

- [ ] `ai/pipeline/classify_rule.py` 신규 — 룰 기반 자칭 컨셉 추출
  - 진료과목별 키워드 사전 (피부과: "여드름", "아토피", "보톡스" 등)
  - 키워드 빈도 + 페이지 타입별 강조도 계산
  - 4시그널 중 자칭 + 블로그 + 공공데이터 룰 기반 처리
- [ ] 룰 기반 신뢰도 점수 산출 (LLM 결과보다 보수적)
- [ ] `classify_hospital(crawl_data, use_llm=False)` 분기 추가
- [ ] `ai/scripts/classify_all_rules.py` — BE가 적재한 1만 병원 크롤링 데이터 읽어서 AI 룰 분류 일괄 호출 (크롤링은 BE 책임 — #7 참조)

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

### 7. `feat/be/crawl-seoul-5gu-full` (신규 — 트랙 A 의존성)

담당: 김경재

> 트랙 A (AI 룰 분류 1만)의 입력 데이터를 채우는 BE 풀크롤링 작업. AI는 BE가 적재한 데이터를 읽어서 분류만 한다 — 크롤링 자체는 BE 영역.

선행 조건:

- #3 `feat/be/clean-noise` 정제 로직 완료 (안 그러면 크롤링 데이터에 잡음 60% 섞임)
- #6 `feat/be/hash-diff-foundation` 의 `body_hash` 컬럼 (있으면 재실행 시 변경분만 처리, 없어도 1회 풀크롤링은 가능)

작업:

- [ ] `be/scripts/crawl_all.py` 또는 `load_seoul_5gu.py` 로 서울 5개구(강남·서초·송파·성동·중구 등 협의) 1만 병원 풀크롤링
- [ ] 크롤링 결과를 S3에 적재 (각 병원당 `CrawlData` JSON)
- [ ] 실패 통계 리포트 (JS 렌더링 필요·URL 없음·timeout 등 사유별 카운트)
- [ ] 성공률 80% 이상 목표

---

## AI 트랙 AWS 세팅 todo (개인 워크북)

> 최비성 개인용. PR로 안 올림. Cloud9에서 진행.

워크플로 (확정): 로컬에서 코딩 (Claude Code 풀파워) → git push → **Cloud9 브라우저 터미널에서 `git pull && python ...` 실행**. Cloud9를 IDE로 안 쓰고 "원격 실행 환경"으로만 사용. 로컬에선 지원 계정 자원 직접 호출 불가 (Role 한정, Access Key 발급 불가).

### Step 1 — Cloud9 환경 + 지원 계정 자원 확인

- [ ] AWS 콘솔 → Cloud9 → 강사가 만들어줬으면 Open IDE, 없으면 Create environment
  - Name: `clinic-focus-ai`
  - Instance type: `t3.small` (시작), 필요 시 키움
  - Platform: Ubuntu Server 22.04 LTS
  - Timeout: 30분 (idle 자동 stop, 비용 절약)
- [ ] 하단 터미널에서 다음 4줄 실행:
  - `aws sts get-caller-identity` → `Account`에 `730335373015` 확인
  - `aws s3vectors list-vector-buckets --region us-east-1` → `bedrock-knowledge-base-1tvot3` 보이는지
  - `aws bedrock list-foundation-models --region us-east-1 --query "modelSummaries[?contains(modelId, 'titan-embed') || contains(modelId, 'haiku') || contains(modelId, 'nova')].modelId"` → Titan v2 + Haiku/Nova 가용성
  - `pip3 list | grep boto3` (없으면 `pip3 install boto3 --upgrade`)
- [ ] 4·6·7 트랙 4.x 가용성도 같이 확인: `aws bedrock list-foundation-models --region us-east-1 --query "modelSummaries[?contains(modelId, 'claude-sonnet-4') || contains(modelId, 'claude-haiku-4') || contains(modelId, 'claude-opus-4')].[modelId,modelLifecycle.status]" --output table`
- [ ] 레포 클론: `cd ~ && git clone https://github.com/BORB-CHOI/clinic-focus.git && cd clinic-focus`

### Step 2 — Titan v2 임베딩 hello-world

- [ ] 짧은 한국어·영어 문장 임베딩 호출. 1024 dim 출력 확인
- [ ] 동일 문장 두 번 호출 시 같은 벡터 나오는지 (재현성)
- [ ] 의미 유사 문장 ("사마귀 치료" vs "심상성 우췌 냉동요법") 코사인 유사도 측정

### Step 3 — S3 Vectors PutVectors + QueryVectors 왕복

- [ ] `bedrock-knowledge-base-1tvot3` 안에 인덱스 생성 또는 기존 인덱스 확인
- [ ] 더미 벡터 5개 PutVectors (메타데이터 포함)
- [ ] QueryVectors로 가장 가까운 벡터 검색 → 메타 필터 동작 확인

### Step 4 — Vector 스키마 설계

- [ ] ID 규칙: `hospital_id` 또는 `hospital_id#chunk_idx`
- [ ] 메타데이터 키 확정: `standard_specialty` / `primary_focus` (list) / `sido` / `sigungu` / `confidence_score` / `lat` / `lng` / `last_updated`
- [ ] 청크 전략: 병원당 1벡터(전체 요약) vs 페이지당 1벡터 결정

### Step 5 — 개인 계정 Sonnet 4.5 Vision 연결

- [ ] 개인 계정 콘솔에서 Bedrock model access 활성화 (Claude Sonnet 4.5)
- [ ] IAM User `clinic-focus-ai` 생성 + `AmazonBedrockFullAccess` 부여
- [ ] Access Key 발급
- [ ] Cloud9 `~/.aws/credentials`에 named profile `personal`로 저장
- [ ] boto3 `Session(profile_name="personal")` 로 Sonnet Vision 호출 — 한국어 이미지(병원 홍보 배너) 1장으로 OCR + 시각 해석 테스트

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
