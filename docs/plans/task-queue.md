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

- **벡터 도구: Bedrock Knowledge Base 경유** (강사 제공 KB `kmuproj-team-03`, ID `GTBJ6HLFDK`). S3 Vectors 직접 호출 ❌ — `SafeRole-kmuproj-10`에 `s3vectors:*` 권한 없음이 확인됐고, 강사가 Titan v2로 셋팅한 KB를 쓰라는 가이드라 그대로 따름. KB가 내부적으로 storage로 쓰는 게 `bedrock-knowledge-base-1tvot3` S3 Vectors 버킷
- **검색 경로 이원화** (필수):
  - **자연어 검색**(예: "강남 사마귀 잘 보는 곳") → AI 모듈 → KB `Retrieve` API
  - **수동 탐색**(`sigungu=강남구 & specialty=피부과` 전체 목록) → BE 모듈 → **DynamoDB GSI 직접 조회**, AI 미경유. KB Retrieve는 빈 쿼리 텍스트로는 못 돌아서 카테고리 탐색에 부적합 (`numberOfResults` 최대 100 제한도 있음)
- **함수명·시그니처 재설계** (PR #1에서 처리):
  - `search_similar(SearchQuery)` → `retrieve_hospital(query_text, filter)` (KB 용어로)
  - `index_hospital(...)` → `ingest_hospital(...)` (KB DataSource S3 업로드 + `start-ingestion-job` 래핑)
  - `embed_text(text)` → 유지 (쿼리 단독 임베딩 디버깅·실험용)
- 임베딩: Titan v2 (KB가 자동 호출, 1024 dim, 지원 계정)
- **벡터 구성 비교 전략**: KB 1개 안에서 셋이 **순차로** 청킹 설정 바꿔가며 비교 (강사가 KB 1개만 줘서). 비교 시점은 BE 풀크롤링 + 정제 완료 후. 비교 축: `FIXED_SIZE` / `HIERARCHICAL` / `SEMANTIC` 청킹 모드, 임베딩 입력 텍스트(본문 raw vs 자칭 키워드 추출 vs 진료과목+자칭 결합)
- OCR: Bedrock Vision으로 흡수 (Textract 한국어 미지원으로 제거)
- 정제·크롤링: 전부 BE 책임 (잡음 제거 + 서울 1만 풀크롤링)
- 검색 시점 LLM 호출 0건 (KB Retrieve가 내부에서 Titan 임베딩 1회만 호출, Sonnet/Haiku 안 거침)
- 시연 10개 외 9990개는 `ai_description = null` (FE 차등 렌더링)
- 사업화 시 갱신: **병원 파일 단위 hash diff** (KB ingestion이 파일 단위라 페이지별 hash는 의미 낮아짐 — 변경된 병원만 DataSource S3에 덮어쓰고 ingestion job 트리거)
- AI 트랙 개발 환경: EC2 + VSCode Remote-SSH (로컬 VSCode가 EC2에 SSH 접속, 편집·터미널·Claude Code 전부 EC2에서 실행 — 인스턴스 프로파일 자동 인증). Cloud9 권한 미발급으로 EC2 임시 대체

---

## 다음 PR 순서

### 1. `feat/ai/aws-clients` (기존 항목 — 재재설계 필요)

담당: 최비성

> 2026-05-24 1차 재설계: "Bedrock·S3 Vectors·Textract 모두 개인 계정" → "S3 Vectors·Titan·Haiku/Nova는 지원 계정, Sonnet만 개인". **같은 날 2차 재설계 (이번 갱신)**: S3 Vectors 직접 호출 ❌ → **Bedrock KB (`bedrock-agent-runtime` / `bedrock-agent`) 경유**. 강사가 KB `kmuproj-team-03`(ID `GTBJ6HLFDK`, Titan v2 셋팅)을 만들어줬고, `SafeRole-kmuproj-10`에 `s3vectors:*` 권한이 없음이 확인됨. `ai/core/aws_clients.py`는 만들어졌으나 다시 재설계 필요.

- [ ] `ai/core/aws_clients.py` 재재설계
  - 지원 계정 클라이언트 팩토리:
    - `get_bedrock_runtime_support()` — Haiku/Nova/Titan invoke 용 (`bedrock-runtime`)
    - `get_bedrock_agent_runtime()` — KB Retrieve API 용 (`bedrock-agent-runtime`) ⭐ 신규
    - `get_bedrock_agent()` — KB DataSource 관리·Ingestion Job 트리거 용 (`bedrock-agent`) ⭐ 신규
    - `get_s3_client_support()` — KB DataSource S3 버킷 업로드 용
  - 개인 계정 클라이언트 팩토리: `get_bedrock_runtime_personal()` (Sonnet Vision 시연용, `AI_AWS_*` 환경변수)
  - 기존 `get_s3vectors_client()` 제거 (직접 호출 안 함)
  - 기존 Textract 클라이언트 함수 제거

- [ ] AI 모듈 함수 시그니처·구현 재설계
  - `ai/search/embed.py` — `embed_text()` 유지 (디버깅·실험용, 지원 계정 Titan 직접 호출)
  - `ai/search/vector_store.py` 폐기 → **`ai/search/kb_store.py` 신규**
    - `ingest_hospital(hospital_id, description_text, metadata)` — DataSource S3 객체 업로드 + `start_ingestion_job` 호출
    - `retrieve_hospital(query_text, filter, limit)` — KB Retrieve API 호출
    - 기존 `index_hospital` / `index_hospital_with_meta` / `search_similar` 제거
  - `ai/core/bedrock_client.py` — 트랙 B는 지원 / 트랙 C는 개인
  - `ai/pipeline/vision.py` — 개인 계정 Sonnet (Textract 호출 제거)

- [ ] `ai/search/feedback.py` — DynamoDB 지원 계정 팩토리로 교체

- [ ] `ai/__init__.py` — 변경된 export
  - 제거: `search_similar`, `index_hospital`
  - 추가: `retrieve_hospital`, `ingest_hospital`

- [ ] BE 호출부도 교체 필요 — `be/handlers/*` 에서 `index_hospital` / `search_similar` 호출 부분 새 함수로 갱신 (별도 PR `refactor/be/ai-kb-rename` 권장)

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

> 사업화 시 운영 비용 통제. PoC 단계에서 구조만 잡아두고 운영은 수동 트리거로 충분. **KB 경유 결정 이후 단위 변경**: 페이지별 hash → **병원 파일 단위 hash** (KB ingestion이 파일 단위라 페이지별로 잘게 비교해도 결국 파일 다시 업로드해야 함).

- [ ] `Hospitals` 테이블에 `content_hash` (병원 통합 본문 SHA-256), `crawled_at` 컬럼 추가
- [ ] 재크롤링 시 `content_hash` 비교 → 변경된 병원만 KB DataSource S3에 덮어쓰고 `start_ingestion_job` 트리거
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

> 최비성 개인용. PR로 안 올림. EC2 + VSCode Remote-SSH 환경에서 진행.

워크플로 (확정): **로컬 VSCode → Remote-SSH 확장으로 EC2 접속 → EC2 위에서 직접 편집·터미널·git·Claude Code 실행**. UI만 로컬, 실행 컨텍스트는 전부 EC2 (인스턴스 프로파일 자동 인증). git push/pull 왕복 없이 EC2에서 commit·push까지 한 번에. 로컬에선 지원 계정 자원 직접 호출 불가 (Role 한정, Access Key 발급 불가) — 그래서 코드 실행은 무조건 EC2에서.

> Cloud9 권한이 강사 계정에서 발급 안 됨. 추후 권한 받으면 동일 워크플로(브라우저 IDE + 인스턴스 프로파일)를 Cloud9로 이전 가능. 강사 요청 시 근거: (1) 로컬에서 지원 계정 자원 호출 불가 — Access Key 미발급, (2) EC2 SSH는 IDE 편의성 부족 — AI 트랙은 Bedrock 호출 반복 실험이 핵심, (3) Cloud9 인스턴스 프로파일은 EC2와 동일 권한 — 추가 권한 없음, (4) `t3.small` + 30분 idle timeout으로 비용 통제.

### Step 0 — VSCode Remote-SSH로 EC2 접속

- [x] BE 트랙이 띄운 EC2 인스턴스 정보 확보 (퍼블릭 IP, SSH 키, 사용자명 — Amazon Linux는 `ec2-user`, Ubuntu는 `ubuntu`)
- [x] 로컬 VSCode에 `Remote - SSH` 확장 설치 (Microsoft 공식)
- [x] `~/.ssh/config`에 호스트 등록:

  ```ssh-config
  Host clinic-focus-ec2
      HostName <ec2-public-ip>
      User ec2-user
      IdentityFile ~/.ssh/<key>.pem
  ```

- [x] VSCode `F1` → `Remote-SSH: Connect to Host` → `clinic-focus-ec2` → 새 창에서 좌하단 `SSH: clinic-focus-ec2` 확인
- [x] EC2 위에 레포 클론: `cd ~ && git clone https://github.com/BORB-CHOI/clinic-focus.git && cd clinic-focus`
- [x] 로컬에서 쓰던 Claude Code 확장을 원격에 설치 (확장 패널에서 "Install on SSH: clinic-focus-ec2" 버튼). CLI(`npm i -g @anthropic-ai/claude-code`)는 VSCode 확장만 쓸 거면 불필요

### Step 1 — 지원 계정 자원 가용성 확인

- [x] EC2 터미널에서 가용성 확인: (2026-05-24 완료)
  - [x] `aws sts get-caller-identity` → `Account=730335373015`, `SafeRole-kmuproj-10/i-0b6142523ec5b5383` 확인
  - [x] `aws s3vectors list-vector-buckets --region us-east-1` → **AccessDenied 확인**. S3V 직접 호출은 안 쓰기로 결정(KB 경유)했으므로 권한 요청 불필요
  - [x] `aws bedrock list-foundation-models ...` → Titan v2 (`amazon.titan-embed-text-v2:0`) · Haiku 4.5 · Nova 라인업 전부 가용
  - [x] `pip3 install --user boto3 --upgrade` → 1.43.14 설치 완료
- [x] Claude 4.x 가용성 확인 → Sonnet 4.5/4.6, Haiku 4.5, Opus 4.1/4.5/4.6/4.7 전부 ACTIVE. **Sonnet 4.5가 지원 계정에서도 보이지만 model access 활성화 여부는 별도 invoke 테스트 필요. 우선은 task-queue 원안대로 Sonnet=개인 계정 유지**
- [x] 강사 제공 KB 발견 (`aws bedrock-agent list-knowledge-bases`) — `kmuproj-team-03` (ID `GTBJ6HLFDK`), Titan v2 + S3 Vectors storage. KB Retrieve API 권한 OK (`bedrock-agent-runtime:retrieve` 호출 성공)

### Step 2 — Titan v2 임베딩 hello-world

- [ ] 짧은 한국어·영어 문장 임베딩 호출. 1024 dim 출력 확인
- [ ] 동일 문장 두 번 호출 시 같은 벡터 나오는지 (재현성)
- [ ] 의미 유사 문장 ("사마귀 치료" vs "심상성 우췌 냉동요법") 코사인 유사도 측정

### Step 3 — Bedrock KB Retrieve 왕복 (S3 Vectors 직접 호출 대체)

> 강사 제공 KB `kmuproj-team-03` (ID `GTBJ6HLFDK`). 내부 storage가 `bedrock-knowledge-base-1tvot3` S3 Vectors 버킷이지만 우리는 KB API만 호출.

- [x] KB 존재 확인: `aws bedrock-agent get-knowledge-base --knowledge-base-id GTBJ6HLFDK --region us-east-1` → status ACTIVE
- [x] DataSource 확인: `aws bedrock-agent list-data-sources --knowledge-base-id GTBJ6HLFDK --region us-east-1` → `main-datasource` (`PLC6QYALDU`)
- [ ] DataSource S3 버킷 이름·prefix 확인 (`aws bedrock-agent get-data-source --knowledge-base-id GTBJ6HLFDK --data-source-id PLC6QYALDU --region us-east-1`)
- [ ] 더미 텍스트 파일 1~3개를 DataSource S3에 업로드 + `metadata.json` 동봉 (메타필터 테스트용)
- [ ] `aws bedrock-agent start-ingestion-job --knowledge-base-id GTBJ6HLFDK --data-source-id PLC6QYALDU` → 상태 COMPLETE 확인
- [ ] `aws bedrock-agent-runtime retrieve --knowledge-base-id GTBJ6HLFDK --retrieval-query '{"text":"테스트"}'` → 결과 받기
- [ ] 메타필터 동작 확인 — `retrievalConfiguration.vectorSearchConfiguration.filter` 로 `sigungu`/`standard_specialty` 등 필터링

### Step 4 — DataSource S3 파일 포맷 + 메타데이터 스키마 설계

> 청크 전략·청크 ID는 KB가 관리. 우리가 설계할 것은 **DataSource에 올릴 파일 포맷과 metadata.json 스키마**.

- [ ] 병원 단위 파일 포맷 결정 — `{hospital_id}.txt` (또는 `.md`)
  - 내용 후보: AI 통합 설명 본문 / 룰 추출 자칭 키워드 / 원문 정제 텍스트 (셋 비교는 벡터 구성 비교 실험 시점에)
- [ ] metadata.json 스키마 — Bedrock KB metadata 사양 따름 (각 파일별로 `{hospital_id}.txt.metadata.json` 동봉)
  - 키: `hospital_id` / `standard_specialty` / `primary_focus` (list) / `sido` / `sigungu` / `confidence_score` (number, `>=` 필터용) / `lat` (number) / `lng` (number) / `last_updated`
  - 필터 가능 타입은 string / number / boolean / list[string]만 (KB 사양)
- [ ] DataSource S3 디렉토리 구조 결정 — flat (`s3://.../{hospital_id}.txt`) vs prefix (`s3://.../{sigungu}/{hospital_id}.txt`)
- [ ] 청크 전략 결정·비교는 **데이터 적재 후**로 보류 (BE 풀크롤링 완료 후)

### Step 5 — 개인 계정 Sonnet 4.5 Vision 연결

- [ ] 개인 계정 콘솔에서 Bedrock model access 활성화 (Claude Sonnet 4.5)
- [ ] IAM User `clinic-focus-ai` 생성 + `AmazonBedrockFullAccess` 부여
- [ ] Access Key 발급
- [ ] EC2 `~/.aws/credentials`에 named profile `personal`로 저장
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
