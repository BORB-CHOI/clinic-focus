# clinic-focus

병원 검색 서비스. **표준 진료과목 카테고리 너머, 병원이 실제로 무엇에 집중하는지를 알려준다.**

## 무엇보다 먼저 읽어야 할 문서

작업 들어가기 전에 관련 문서를 먼저 본다. 이 CLAUDE.md는 요약·포인터일 뿐이고 진실은 아래 4개 문서에 있다.

- `docs/overview.md` — 서비스 기획·문제 정의·의료법 대응·수익 모델
- `docs/dev-roadmap.md` — 트랙 분담·기술 스택·마일스톤·평가 4요소 매핑
- `docs/API-FE-BE.md` — 프론트 ↔ 백엔드 인터페이스
- `docs/API-BE-AI.md` — 백엔드 ↔ AI 모듈 함수 명세

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
├── ai/         # 최비성 — 룰 기반 분류(서울 1만) + Bedrock LLM/Vision 시연(10개) + S3 Vectors + Titan Embed v2
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
| **지원 계정** | EC2 · RDS · DynamoDB · S3 · S3 Vectors · Bedrock(Titan Embed v2, Haiku/Nova 한정) · API Gateway · Amplify · SQS · SNS | `us-east-1` | IAM Role만 (Access Key 발급 불가). EC2=`SafeInstanceProfile-{username}` |
| **개인 계정** | Bedrock (Claude Sonnet 4.5 — Vision 시연 한정) | `us-east-1` | 개인 계정 자격증명 (전용 프로파일/환경변수) |

- **컴퓨팅은 EC2 단일.** Ubuntu, `t3.nano`~`t3.medium`. 크롤러·FastAPI API 서버·AI 오케스트레이션이 한 인스턴스의 한 프로세스에서 돈다. Lambda·SAM·Mangum 미사용 — 전국 크롤링 시 Lambda 15분 제한을 피하려는 게 EC2 전환 사유.
- **EC2 코드의 자격증명 분리.** 지원 계정 서비스(DynamoDB·S3·S3 Vectors·Titan Embed·Haiku/Nova)는 EC2 인스턴스 프로파일로 자동 인증. **개인 계정 Sonnet 4.5(Vision 시연용)** 만 별도 자격증명으로 boto3 클라이언트를 따로 생성한다.
- **지원 계정 Bedrock 제약(중요).** 강사가 제공한 자원이라 모델·범위가 한정된다. 텍스트/Vision **Haiku 또는 Nova만**, 시연 **10개 병원 한도**. 임베딩(Titan v2)은 전체 자유. 전체 1만 병원 텍스트 분류는 **룰 기반(LLM 미사용)** 으로 처리.
- **S3 버킷 이름은 `{username}-` 접두사**로 시작. 강사가 만들어준 벡터 버킷: `bedrock-knowledge-base-1tvot3`.

### 모델 ID

| 항목 | 값 | 계정 | 사용 범위 |
|---|---|---|---|
| LLM/Vision (시연) | `anthropic.claude-haiku-4-5-...` 또는 `amazon.nova-...` | 지원 | 10개 병원 |
| Vision (고품질 시연) | `anthropic.claude-sonnet-4-5-20250929-v1:0` | 개인 | 10개 병원 (시연용) |
| Embedding | `amazon.titan-embed-text-v2:0` (차원 1024) | 지원 | 전체 (서울 1만) |

### AI 트랙 3트랙 구조 (이번 결정)

| 트랙 | 대상 | 모델 | 범위 |
|---|---|---|---|
| A. 룰 기반 분류 | 자칭 컨셉 추출 (LLM 미사용) | 키워드/빈도 룰 | 서울 5개구 1만 |
| B. LLM 텍스트 시연 | 자칭 추출 + `generate_description` | 지원 Haiku/Nova | 10개 |
| C. Vision 시연 | 이미지 분석 | 개인 Sonnet 4.5 | 10개 |

→ A는 1만 풀커버 베이스라인, B·C는 같은 10개 병원으로 차별 효과 시연. 자세한 건 `ai/CLAUDE.md`.

## 멀티 에이전트 — 트랙 리더 + 서브 구조

각 트랙 엔지니어가 그 트랙의 첫 진입점. ai/ 트랙에 한해 서브에이전트 4개가 추가로 분리돼 있음 (최비성이 ai/ 안에서 자신의 작업을 분담시키는 구조). BE·FE 트랙은 그쪽 개발자들이 알아서 운영.

### 트랙 리더
- `fe-engineer` — fe/ 트랙 (하재원)
- `be-engineer` — be/ + shared/ (김경재)
- `ai-engineer` — ai/ + shared/ (최비성). 아래 4개 ai/ 서브에이전트에 위임 가능

### ai/ 서브에이전트 (ai-engineer가 위임)
- `prompt-engineer` — `generate_description` 프롬프트 설계·튜닝, 의료법 5규칙 강제, `ai/prompts/*.md` 관리
- `vector-search-engineer` — S3 Vectors, `search_similar`, `index_hospital`, `embed_text`, 메타필터
- `vision-analyst` — Bedrock Vision + Textract, `analyze_images`, 시술/기기 사진 분류, `MAX_VISION_IMAGES` 비용 관리
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

트랙 간 의존성은 `docs/dev-roadmap.md`의 "협업 의존성" 섹션 참조.

## 외부 자산

- `.claude/skills/gstack/` (git submodule) — Garry Tan의 Claude Code Skills 모음. `/plan-eng-review`, `/plan-design-review`, `/review`, `/qa`, `/retro`, `/office-hours` 등. 발표 전 데모 검증·트랙간 동기화에 활용
- `.claude/agents/{python,typescript,security}-reviewer.md`, `tdd-guide.md` — ECC(everything-claude-code)에서 가져옴
- `.mcp.json`의 `context7` — 라이브러리·프레임워크 최신 문서를 컨텍스트로 주입하는 MCP. 라이브러리 이름이 나오는 코드 작성 중 자동 활용 (npx로 실행, 초기 1회 설치 메시지 정상)
