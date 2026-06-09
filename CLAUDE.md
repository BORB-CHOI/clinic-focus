# clinic-focus

병원 검색 서비스. **표준 진료과목 카테고리 너머, 병원이 실제로 무엇에 집중하는지를 알려준다.**

## 무엇보다 먼저 읽어야 할 문서

작업 들어가기 전에 관련 문서를 먼저 본다. 이 CLAUDE.md는 요약·포인터일 뿐이고 진실은 아래 문서에 있다.

- `docs/overview.md` — 서비스 기획·문제 정의·의료법 대응·수익 모델·평가 4요소 매핑
- `docs/architecture.md` — 데이터·분류·검색 아키텍처 (저장 3층·주력 강도 랭킹 §5-1)
- `docs/API-FE-BE.md` — 프론트 ↔ 백엔드 인터페이스
- `docs/API-BE-AI.md` — 백엔드 ↔ AI 모듈 함수 명세
- 남은 작업은 `docs/plans/task-queue.md`

## 성격 — 평가용 PoC

사업 운영용 인프라는 **만들지 않는다**. 다음 항목은 명시적으로 제외:

- Docker / CI·CD / 로드밸런싱
- 인증·로그인 (모든 API public)
- SEO·SSR·다크모드·완전한 반응형
- B2B SDK, 자동 갱신 파이프라인
- 자체 호스팅 오픈소스 인프라 (Elasticsearch·Airflow·Redis 등)

이 제약을 어기는 제안은 평가 목적을 흐린다. 추가 인프라가 필요해 보이면 먼저 사용자에게 확인.

## 모듈 경계

```
clinic-focus/
├── fe/         # 하재원 — React + Vite + TS + Tailwind + shadcn/ui + TanStack Query + 카카오맵 SDK
├── be/         # 김경재 — FastAPI + uvicorn + Pydantic + boto3 + httpx + BS4 (EC2 운영)
├── ai/         # 최비성 — 룰 기반 분류(서울 1만) + Bedrock LLM/Vision 시연(약 500개) + Bedrock Knowledge Base (강사 제공 `kmuproj-team-03`) + Titan Embed v2
├── shared/     # 공유 Pydantic 모델. BE·AI 양쪽에서 import. FE는 OpenAPI에서 TS 타입 자동 생성
└── .claude/
    ├── docs/       # 4대 문서
    ├── agents/     # 트랙 리더 3 + ai/ 서브 4 + 리뷰어 5 (자세한 건 멀티 에이전트 섹션)
    ├── commands/   # 슬래시 커맨드
    ├── skills/     # gstack (git submodule)
    └── settings.json
.mcp.json          # Context7 MCP
```

각 트랙 폴더에는 자체 `CLAUDE.md`가 있고, 그 폴더에서 작업할 때만 자동으로 로드된다. 트랙 전담 컨텍스트는 그 안에 둔다.

## BE ↔ AI 호출 모델

같은 EC2 인스턴스의 단일 Python 프로세스에서 돈다. BE는 AI 함수를 Python `import`로 직접 호출 (HTTP 호출 아님). 인터페이스는 `shared/models.py`의 Pydantic 모델로 정의.

```python
from ai import classify_hospital, generate_description
from shared.models import CrawlData
```

## Git 브랜치 규칙 (절대 어기지 말 것)

**main 브랜치에서 직접 코드 작성 금지.** 모든 작업은 feature 브랜치에서 시작한다.

```bash
# 새 작업 시작 시 항상
git checkout main && git pull origin main
git checkout -b feat/<작업명>     # 기능: feat/aws-client-factory
git checkout -b fix/<버그명>      # 버그: fix/region-hardcode
git checkout -b refactor/<영역>   # 리팩터: refactor/dynamo-adapter
```

- `.claude/settings.json`의 PreToolUse hook이 main에서 Edit/Write를 차단한다
- `.git/hooks/pre-commit`이 main 직접 커밋을 차단한다
- 이 제약은 `/ship` 워크플로우(PR 생성)의 전제 조건이기도 하다

## 글로벌 코딩 원칙

- **한국어 응답.** 도메인이 한국 의료라 UI 카피·로그 메시지·주석 모두 한국어가 자연스러우면 한국어로. 코드 식별자만 영어.
- **shared/ 의 Pydantic 모델이 단일 진실.** BE·AI 한쪽에서 모델 바꾸면 다른 쪽도 동시에 따라간다. 분류 스키마는 M1 시점 동결.
- **FastAPI OpenAPI → FE TS 타입 자동 생성.** `openapi-typescript`로. 수동 동기화 금지.
- **수동 배포.** FE는 `aws s3 sync` (S3+CloudFront), BE+AI는 EC2에 `git pull` 후 프로세스 재시작. CI/CD 없음.

## Git 커밋 컨벤션

- **Conventional Commits 타입은 영어, 제목·본문은 한국어.**
  - 타입: `feat` `fix` `docs` `chore` `refactor` `test` `build` `ci` `perf` `style`
  - 스코프로 트랙·영역 명시: `feat(ai):` `fix(be):` `feat(fe):` `refactor(shared):` `chore(claude):` `docs(api):`
  - 예: `feat(ai): generate_description 의료법 5규칙 강제 프롬프트 추가`
- **제목 50자 이내, 명령형 어조.** "추가했음" 아닌 "추가" / "수정". 마침표 X
- **본문은 72자 줄바꿈, "왜"에 초점.** "무엇"은 diff가 말함. 결정의 이유·트레이드오프·관련 이슈를 적음
- **한 커밋엔 하나의 논리적 변경.** 트랙 섞이거나 무관한 수정 같이 들어가면 분할. `git add -p`로 부분 스테이징 활용
- **푸시 전 점검**: `main` 브랜치 직접 푸시는 본인 결정. force push 금지(특히 main)

## 의료법 회색지대 — 주체 명시 원칙 (절대 어기지 말 것)

> **우리는 평가하지 않는다. 병원이 자기 자신을 어떻게 표현했는지를 보여줄 뿐이다.**

| 잘못된 표현 | 적법 표현 |
|---|---|
| "이 병원은 아토피를 잘 본다" | "이 병원이 자기 사이트에서 아토피 진료를 메인으로 표시함" |
| "여기 사마귀 냉동치료기 있음" | "이 병원이 공식 신고한 의료기기 목록에 냉동치료기 포함됨" |
| "이 의사는 탈모 처방을 잘함" | "이 의사가 자기 블로그에서 M자 탈모 처방 사례를 다룸" |

`ai/`의 `generate_description` 프롬프트와 `fe/`의 UI 카피, `be/`의 자동 생성 메시지 전부 이 규칙을 따른다. 표현이 애매하면 `medical-language-reviewer` 서브에이전트에 검수 위임.

## AWS 계정·인프라 구조

AWS 계정이 둘로 나뉜다. 어느 서비스가 어느 계정에 있는지 항상 의식할 것.

| 계정 | 서비스 | 리전 | 자격증명 |
|---|---|---|---|
| **지원 계정** | EC2 · RDS · DynamoDB · S3 · **Bedrock Knowledge Base (`kmuproj-team-03`, 강사 제공)** · Bedrock(Titan Embed v2 + 텍스트 **on-demand**: Claude 3 Haiku·Nova) · API Gateway · Amplify · SQS · SNS | `us-east-1` | IAM Role만 (Access Key 발급 불가). EC2=`SafeInstanceProfile-{username}` |
| ~~**개인 계정**~~ | ~~Bedrock Sonnet 4.6 (Vision 시연)~~ — **제거됨(없어진 지 오래)**. 검색 런타임 LLM(재랭커)은 지원 계정 on-demand 로 이전. `.env` 의 `AI_AWS_*` 는 데드 자격증명(레거시). | ~~`ap-northeast-2`~~ | — |

### 권한 정책 (절대 어기지 말 것)

> **지원 계정 권한 = 현재 `SafeRole-{username}` 인스턴스 프로파일 + 강사가 미리 만든 자원(KB·KB DataSource S3 버킷·EC2 인스턴스)이 전부.** 추가 IAM 발급·정책 변경·신규 권한 부여는 없다.

- **자원 생성·삭제는 AWS 콘솔에서만.** `dynamodb:CreateTable` / `s3:CreateBucket` / `iam:*` 등 자원 생성 액션이 SafeRole 에 들어있지 않다 — boto3/aws-cli 호출 시 `AccessDeniedException`. **코드/스크립트로 자원 생성 제안 금지.** 이미 만들어진 자원에 대한 데이터 조작(PutItem/GetItem/Query/PutObject/GetObject)만 코드로.
- **DynamoDB 테이블 / S3 버킷은 콘솔 수동 생성.** DDB 스키마는 [`be/CLAUDE.md`](be/CLAUDE.md) "스키마 — V2 single-table", 생성·기동 명령은 [`deploy/README.md`](deploy/README.md).
- **권한 부족 진단 = 정책 확장이 아닌 콘솔 우회.** "권한 받으면 한방에" 같은 미래 가정 코드 금지. 현재 권한이 전부라는 전제로 설계.

- **컴퓨팅은 EC2 단일.** Ubuntu, `t3.nano`~`t3.medium`. 크롤러·FastAPI API 서버·AI 오케스트레이션이 한 인스턴스의 한 프로세스에서 돈다. Lambda·SAM·Mangum 미사용 — 전국 크롤링 시 Lambda 15분 제한을 피하려는 게 EC2 전환 사유.
- **AI 트랙 개발 환경: EC2 + VSCode Remote-SSH.** 로컬 PC에서는 지원 계정 자원(Bedrock KB·DynamoDB·Bedrock 등) 직접 호출 불가 — IAM Role만 받고 Access Key 발급이 안 되기 때문. **워크플로**: 로컬 VSCode에서 Remote-SSH 확장으로 EC2 접속 → EC2 위에서 직접 편집·터미널·git·Claude Code 실행. UI는 로컬, 실행 컨텍스트는 전부 EC2 (인스턴스 프로파일 자동 인증). Cloud9 권한이 강사 계정에서 발급 안 돼서 EC2가 임시 대체 환경 — Cloud9 권한 받으면 동일 워크플로를 Cloud9 브라우저 IDE로 이전 가능.
- **EC2 코드의 자격증명 = 지원 계정 인스턴스 프로파일 단일.** DynamoDB·S3·Bedrock KB·Titan Embed·텍스트 LLM(재랭커) 전부 인스턴스 프로파일로 자동 인증. 개인 계정은 제거됐다 — `ai/core/aws_clients._get_ai_session()`(AI_AWS_*) 은 데드 레거시. 검색 런타임 LLM(재랭커)은 `get_bedrock_runtime_client_support()` 로 지원 계정만 쓴다.
- **지원 계정 Bedrock 제약(중요·실측 2026-06-08).** SafeRole-kmuproj-10 인스턴스 프로파일로 us-east-1 에서 **on-demand 모델만** 호출된다 — **Claude 3 Haiku(`anthropic.claude-3-haiku-20240307-v1:0`)·Nova 전 계열**. ❌ **막힘**: Haiku 4.5(on-demand=ValidationException)·Claude 3.5 Haiku·모든 `us.`/`global.` cross-region **inference profile**(=AccessDeniedException). 그래서 재랭커 기본 모델 = **Nova Lite**(`amazon.nova-lite-v1:0`, A/B 우위 — `RERANK_MODEL_ID` 로 Claude 3 Haiku/Nova Pro 교체 가능). 임베딩(Titan v2)은 KB가 내부 호출. 전체 1만 텍스트 분류는 **룰 기반(LLM 미사용)**. (사전처리 데모였던 `generate_description`·Vision 은 개인 계정 Sonnet/Haiku4.5 의존이라 **신규 생성 불가** — 기존 적재분 504/508 은 정적이라 무관.)
- **벡터 검색은 Bedrock KB 경유.** 강사가 제공한 KB `kmuproj-team-03` (ID `GTBJ6HLFDK`, Titan v2 셋팅)을 사용. 내부 storage는 S3 Vectors 버킷 `bedrock-knowledge-base-1tvot3`이지만 우리는 KB API(`bedrock-agent-runtime:Retrieve`, `bedrock-agent:StartIngestionJob`)만 호출. S3 Vectors 직접 호출 ❌ (`SafeRole-kmuproj-10`에 `s3vectors:*` 권한 없음 + 강사 셋팅이 KB).
- **검색 경로 이원화.** 자연어 쿼리는 AI 모듈이 KB Retrieve로 처리하고, 단순 카테고리 탐색(`sigungu=강남구 & specialty=피부과` 전체 목록)은 BE가 DynamoDB GSI로 직접 처리 — KB 미경유. AI는 자연어 검색만 책임.
- **S3 버킷 이름은 `{username}-` 접두사**로 시작.

### 모델 ID

| 항목 | 값 | 계정 | 사용 범위 |
|---|---|---|---|
| **검색 재랭커(런타임)** | `amazon.nova-lite-v1:0` (on-demand, A/B 우위) / `RERANK_MODEL_ID` 로 교체 | 지원 | `RERANK_MODE=llm` 일 때 검색당 1회 |
| Embedding | `amazon.titan-embed-text-v2:0` (차원 1024) | 지원 | 전체 (서울 1만) |
| ~~LLM 텍스트 시연 (사전처리)~~ | ~~`...claude-haiku-4-5-...`/Nova~~ — Haiku4.5 막힘, 개인계정 데드 | ~~지원/개인~~ | DESCRIPTION 504 **기적재 정적** (신규 생성 불가) |
| ~~Vision (사전처리)~~ | ~~`global.anthropic.claude-sonnet-4-6`~~ — 개인 계정 제거 | ~~개인~~ | VISION 508 **기적재 정적** (신규 생성 불가) |

> ★ 지원 계정 on-demand 만 호출 가능(실측 2026-06-08): **Claude 3 Haiku·Nova ✅** / Haiku 4.5·Sonnet·모든 `us.`·`global.` inference profile **❌ AccessDenied/Validation**. 그래서 런타임 LLM(재랭커)은 **Nova Lite 기본**(A/B: Nova Lite P@1 0.81 > Claude 3 Haiku 0.76 > Nova Pro 0.77).

### AI 트랙 3트랙 구조 (이번 결정)

| 트랙 | 대상 | 모델 | 범위 |
|---|---|---|---|
| A. 룰 기반 분류 | 자칭 컨셉 추출 (LLM 미사용) | 키워드/빈도 룰 | 강남 PoC (서울 확장 설계) |
| B. LLM 텍스트 시연 (사전처리, 정적) | 자칭 추출 + `generate_description` | ~~개인 Haiku4.5/Sonnet~~ → 신규 생성 불가 | 기적재 504 정적 |
| C. Vision 시연 (사전처리, 정적) | 이미지 분석 | ~~개인 Sonnet 4.6~~ → 신규 생성 불가 | 기적재 508 정적 |
| **D. 검색 재랭커 (런타임)** | 2-stage RAG 2단계 정렬 + thin-signal 회수(컷 0.35 결합) | **지원 Nova Lite (on-demand)** | `RERANK_MODE=llm` |

→ A는 1만 풀커버 베이스라인, B·C는 같은 약 500개 병원의 기적재 정적 데모(개인계정 제거로 신규 생성 불가), **D는 검색 런타임 재랭킹(지원 계정 on-demand)**. 자세한 건 `ai/CLAUDE.md`.

## 멀티 에이전트 — 트랙 리더 + 서브 구조

각 트랙 엔지니어가 그 트랙의 첫 진입점. ai/ 트랙에 한해 서브에이전트 4개가 추가로 분리돼 있음 (최비성이 ai/ 안에서 자신의 작업을 분담시키는 구조). BE·FE 트랙은 그쪽 개발자들이 알아서 운영.

### 트랙 리더
- `fe-engineer` — fe/ 트랙 (하재원)
- `be-engineer` — be/ + shared/ (김경재)
- `ai-engineer` — ai/ + shared/ (최비성). 아래 4개 ai/ 서브에이전트에 위임 가능

### ai/ 서브에이전트 (ai-engineer가 위임)
- `prompt-engineer` — `generate_description` 프롬프트 설계·튜닝, 의료법 5규칙 강제, `ai/prompts/*.md` 관리
- `vector-search-engineer` — Bedrock Knowledge Base 경유 (`retrieve_hospital` / `ingest_hospital`), `embed_text` (실험용), 메타필터, DataSource S3 파일/metadata 스키마
- `vision-analyst` — Bedrock Vision, `analyze_images`, 시술/기기 사진 분류 (OCR 포함, Textract 미사용), `MAX_VISION_IMAGES` 비용 관리
- `signal-fusion-engineer` — 4 시그널 교차 검증, `classify_hospital`, 자칭 도배 페널티, `recompute_confidence`

### 리뷰·검수
- `python-reviewer` — Python PR 리뷰 (ECC)
- `typescript-reviewer` — TS PR 리뷰 (ECC)
- `security-reviewer` — 보안 점검 (ECC)
- `medical-language-reviewer` — 의료법 표현 검수 (자체)
- `tdd-guide` — TDD 가이드 (ECC) — Bedrock mock 의무화에 필수

### 작업 위임 흐름 (ai/ 트랙 기준)

```
사용자 요청 (ai/ 관련)
  ↓
ai-engineer (직접 처리 / 위임 판단)
  ↓
prompt-engineer · vector-search-engineer · vision-analyst · signal-fusion-engineer
  (병렬 가능 시 동시 호출)
  ↓
medical-language-reviewer (의료법) · python-reviewer (코드)
  ↓
ai-engineer 통합 보고
```

트랙 간 인터페이스·의존성은 `docs/API-FE-BE.md`·`docs/API-BE-AI.md`(함수·엔드포인트 계약)와 각 트랙 `*/CLAUDE.md` 참조.

## 외부 자산

- `.claude/skills/gstack/` (git submodule) — Garry Tan의 Claude Code Skills 모음. `/code-review`, `/simplify`, `/review`, `/security-review`, `/run`, `/init` 등 + 내부 스킬 다수(plan-eng-review·design-review·qa·retro·office-hours 등). 발표 전 데모 검증·트랙간 동기화에 활용. **EC2/팀원 신규 환경에서 한 번**: `git submodule update --init --recursive` (clone 후 .gitmodules에 등록만 돼 있고 로컬 워킹 트리는 비어있음)
- `.claude/agents/{python,typescript,security}-reviewer.md`, `tdd-guide.md` — ECC(everything-claude-code)에서 가져옴
- `.mcp.json`의 `context7` — 라이브러리·프레임워크 최신 문서를 컨텍스트로 주입하는 MCP. 라이브러리 이름이 나오는 코드 작성 중 자동 활용 (npx로 실행, 초기 1회 설치 메시지 정상)
