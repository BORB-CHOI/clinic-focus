# 개발 로드맵 — clinic-focus

> 프로젝트명: **clinic-focus** (클리닉포커스)  
> 레포: `clinic-focus` (모노레포, 폴더로 `fe/` `be/` `ai/` `shared/` 분리)
>
> **이 문서는 트랙 분담·기술 스택·평가 4요소 매핑을 한곳에 모은 참조 문서다.** 강남구 PoC as-built
> (FE-BE 실연동·검색·분류·KB까지 전부 `main` 머지 완료) 기준으로, 각 트랙이 **무엇을 만들었는지**를
> 정리한다. 구조·알고리즘 상세는 [`architecture.md`](architecture.md), 기획·동작 원리는
> [`overview.md`](overview.md), 인터페이스는 [`API-FE-BE.md`](API-FE-BE.md)·[`API-BE-AI.md`](API-BE-AI.md),
> **남은 일**은 [`plans/task-queue.md`](plans/task-queue.md)에 둔다. 여기서는 가리키기만 한다.

## 팀 구성

| 담당자 | 영역 |
|---|---|
| **최비성** | AI · RAG · 분류 알고리즘 |
| **하재원** | 프론트엔드 · UI |
| **김경재** | 데이터 수집·가공 · 백엔드 |

### 공통 개발 원칙

- **목표는 평가 4요소(문제 정의 / 해결 타당성 / 창의성 / 발표) 충족.** 사업 운영용 인프라(B2B SDK, 자동 갱신 파이프라인 등)는 모두 제외.
- **와이어프레임 없이 바이브 코딩.** Claude Design + Claude Code로 직접 코드 작성.
- **Docker / CI·CD / 로드밸런싱 / 인증·로그인 / SEO·마케팅 / 다크모드 제외.**
- BE FastAPI 자동 생성 OpenAPI 스펙 → 프론트 TS 타입 자동 생성 (`openapi-typescript`). 수동 동기화 없음.
- BE ↔ AI는 `shared/` 폴더의 Pydantic 모델 공유.

---

## 기술 스택

### 프론트 (하재원)

| 항목 | 선택 | 비고 |
|---|---|---|
| 언어 | TypeScript | |
| 프레임워크 | **React + Vite** | SEO·SSR 안 쓰니 Next.js는 오버킬 |
| UI | **Tailwind CSS + shadcn/ui** | Claude Design 친화적, 바이브 코딩 최적 |
| 서버 상태 | **TanStack Query** | 캐싱·재시도·로딩 자동 처리 |
| 라우팅 | React Router | 검색·상세·이력 페이지 |
| API 클라이언트 | fetch | axios까지 갈 필요 없음 |
| 빌드·배포 | `vite build` → S3 + CloudFront | 수동 배포 (`aws s3 sync`) |

### 백엔드 (김경재)

| 항목 | 선택 | 비고 |
|---|---|---|
| 언어 | **Python 3.11+** | AI 통합·boto3 풍부함 |
| 프레임워크 | **FastAPI + uvicorn** | 자동 OpenAPI 스펙, EC2에서 직접 서빙 |
| 데이터 검증 | **Pydantic** | FastAPI 기본 포함, AI 모듈과 모델 공유 |
| AWS SDK | boto3 | DynamoDB·S3·Bedrock·Bedrock Knowledge Base (Textract 미사용) |
| 크롤링 | **httpx + BeautifulSoup4** | 단순. JS 렌더링 필요한 일부만 Playwright 보강 |
| 배포 | **EC2 (수동)** | git pull + 프로세스 재시작, 도커 불필요 |

### AI · RAG (최비성)

| 항목 | 선택 | 비고 |
|---|---|---|
| 언어 | Python 3.11+ | BE와 동일 환경, 패키지 import 가능 |
| AI 호출 | boto3 (bedrock-runtime) | LLM·Vision·OCR 모두 단일 SDK (Textract 미사용 — Bedrock Vision으로 OCR 흡수) |
| 벡터 | boto3 (bedrock-agent-runtime, bedrock-agent) | Bedrock Knowledge Base 경유 (강사 제공 `kmuproj-team-03`). Retrieve API + DataSource S3 업로드 + ingestion job |
| RAG 프레임워크 | **직접 구현 (LangChain 안 씀)** | 4 시그널 교차 검증 같은 커스텀 로직 통제 위해 |
| 데이터 모델 | Pydantic | BE와 공유 (`shared/models.py`) |

### 오픈소스 보강

기본은 AWS 매니지드, 다음의 경우만 오픈소스 라이브러리 보강:

- **JS 렌더링 필요한 사이트** → Playwright (네이버 place 후기 회색지대 수집용, 현재 보류)
- **PDF 의료기기 신고증** → PyMuPDF (필요 시. OCR은 Bedrock Vision으로 흡수, Textract 미사용)
- **이미지 전처리** → Pillow (Vision 호출 전 리사이즈)
- 자체 호스팅 오픈소스 인프라(Elasticsearch·Airflow·Redis)는 **도입하지 않음**

---

## AWS 인프라 스택

AWS 계정이 둘로 나뉜다 — **지원 계정**(us-east-1, IAM Role만, Access Key 발급 불가)과
**개인 계정**(Vision 시연 전용). EC2 코드는 지원 계정 서비스는 인스턴스 프로파일로,
개인 계정 Sonnet 4.6(Vision 시연용, 서울 리전 `ap-northeast-2`, Global cross-region inference profile)은 별도 자격증명으로 호출한다.

| 계층 | 서비스 | 계정 | 용도 |
|---|---|---|---|
| **컴퓨팅** | EC2 (Ubuntu, `t3.nano`~`t3.medium`) | 지원 | 크롤러 + API 서버 + AI 오케스트레이션. Lambda 15분 제한 회피 위해 EC2 단일 |
| **API 노출** | API Gateway (선택) 또는 EC2 직접 | 지원 | EC2의 FastAPI를 public endpoint로 노출. 인증 없음 |
| **정형 데이터** | DynamoDB single-table `kmuproj-10-clinic-Main` (AI 계정) / `kmuproj-02-team3-backend` (BE) | 지원 | 메타·수집메타·분류·신뢰도·피드백·변경 이력. `PK=hospital_id` · `SK=entity`. (스키마는 [`architecture.md`](architecture.md) §1·[`plans/task-queue.md`](plans/task-queue.md)) |
| **원본 저장** | S3 (버킷명 `{username}-` 접두사) | 지원 | 크롤링한 HTML 본문·이미지 원본 (자체사이트 본문은 S3에, DDB엔 포인터만) |
| **벡터 저장·검색** | **Bedrock Knowledge Base** (`kmuproj-team-03`, ID `GTBJ6HLFDK`, 강사 제공) | 지원 | 병원 분류·설명을 KB DataSource S3에 업로드 → KB가 Titan v2 임베딩 + S3 Vectors 적재 자동 처리. 검색은 `bedrock-agent-runtime:Retrieve` API. 내부 storage는 S3 Vectors 버킷 `bedrock-knowledge-base-1tvot3`이지만 직접 호출 ❌ |
| **LLM·Vision (시연 10개)** | Bedrock Haiku 4.5 또는 Nova | 지원 | 트랙 B 자칭 추출·`generate_description` (강사 자원, 10개 한도) |
| **Vision 고품질 시연 (10개)** | Bedrock Claude Sonnet 4.6 (`global.anthropic.claude-sonnet-4-6`, Global cross-region inference profile, 서울 리전) | 개인 | 트랙 C 이미지 분석 (한국어 OCR + 시각 해석) |
| **임베딩** | Bedrock Titan Embed Text v2 (1024차원) | 지원 | 병원 설명·쿼리 임베딩 |
| **OCR** | (미사용) | — | Textract 한국어 미지원 → Bedrock Vision으로 흡수 |
| **프론트 호스팅** | S3 + CloudFront | 지원 | 정적 빌드 결과물 배포 + CDN 가속 |
| **배포** | 수동 (EC2 `git pull` / `aws s3 sync`) | — | CI·CD·로드밸런싱 없음 |
| **개발 환경** | EC2 + VSCode Remote-SSH | 지원 | AI 트랙 작업 환경. 로컬 VSCode가 Remote-SSH 확장으로 EC2에 접속, 편집·터미널·git·Claude Code 전부 EC2에서 실행. 인스턴스 프로파일로 지원 계정 자원 자동 인증. (Cloud9이 강사 계정에서 권한 미발급 상태 → EC2가 임시 대체. Cloud9 권한 받으면 동일 방식으로 이전 가능) |

### 왜 DynamoDB인가 (RDS 대신)

RDS도 지원 계정에서 가용하지만 DynamoDB를 택한 근거는 **우리 워크로드의 형태**가 RDB의 강점과 어긋난다는 것:

1. **S3 + DDB 분리가 정석 패턴** — 크롤링 본문(`crawl_data.json`, 페이지당 1MB+)은 S3에, 인덱싱 가능한 메타·분류 결과는 DDB에. RDS에 BLOB/TEXT 큰 칼럼 박는 건 백업 부풀음·성능 저하 안티패턴.
2. **Single-table-design 친화성** — `PK=hospital_id`로 한 병원의 모든 entity(메타·크롤링·분류·설명)를 `Query` 1회로 가져옴. RDS면 4~5개 테이블 JOIN + N+1 방지 코드 필요. (BE는 실제 single-table로 운영 중)
3. **간헐적 트래픽** — 크롤링은 며칠에 한 번 몇 시간, 그 외엔 발표 시연 잠깐. DDB on-demand는 idle 시 $0, RDS `db.t4g.micro`는 항상 ~$13/월.
4. **스키마 변경 자유** — `shared/models.py`가 PoC 중 자주 바뀜 (예: P0.5 `pages=[]`/`images=[]` 빈 객체 허용). DDB는 그대로 박고, RDS면 매번 마이그레이션.
5. **RDS의 SQL 강점이 무의미** — 자연어 검색은 Bedrock KB가 처리하고 카테고리 필터는 GSI 1개로 충분. 복합 `WHERE`·풀텍스트·JOIN을 쓸 access pattern 자체가 없음.

**약점도 명시**: 1억 건 + 초당 수만 TPS가 아닌 한 성능 차이는 없고, GSI 미설계 필드로는 못 찾는 제약이 있음. 우리는 access pattern이 단순해서 이 제약에 안 걸림.

**솔직한 보완**: 초기 선택은 "AWS 매니지드 풀스택 어필 + idle $0"라는 약한 근거로 진행됐고, 위 근거 1·2·3은 BE 산출물(single-table 운영 + S3 본문 적재)을 본 뒤 사후 정리한 것. 결과적으로 워크로드와 맞아서 유지.

---

## 트랙별 산출물 (as-built)

> 아래는 각 트랙이 **만든 것**이다. 알고리즘·데이터 구조 상세는 [`architecture.md`](architecture.md),
> 기획 맥락은 [`overview.md`](overview.md), 함수·엔드포인트 명세는 [`API-BE-AI.md`](API-BE-AI.md)·
> [`API-FE-BE.md`](API-FE-BE.md)를 가리킨다. 여기서는 "무엇을 했고 어디 가서 보면 되는지"만 적는다.
> 남은 작업은 [`plans/task-queue.md`](plans/task-queue.md).

### 최비성 트랙 — AI · RAG

**스택**: Python 3.11 · boto3 (bedrock-runtime, bedrock-agent-runtime, bedrock-agent, s3) · Pydantic · `shared/models.py`

> **AI 트랙 3트랙 구조 (PoC)**: 지원 계정 Bedrock이 Haiku/Nova + 10개 한도로 제공돼서 분류는 **룰 기반(트랙 A)** 으로 강남 베이스라인을 깔고, LLM/Vision은 **시연 10개(트랙 B·C)** 에 집중한다. 자세한 건 `../ai/CLAUDE.md` "AI 트랙 3트랙 구조" 참조.

| 트랙 | 한 것 | 모델 | 범위 |
|---|---|---|---|
| **A. 룰 기반 분류** | 자칭 컨셉 추출 + 4 시그널 교차검증 → `standard_specialty`(22종) + `primary_focus`(자유 태그 리스트) + 신뢰도. **검색·분류 시점 LLM 0회** | 키워드/빈도 룰 | 강남 전수 (분류완료 ~3098) |
| **B. LLM 텍스트 시연** | `generate_description` (출처 태그 자동 부착, 의료법 주체 명시) | 지원 Haiku/Nova | 시연 10개 |
| **C. Vision 시연** | `analyze_images` (시술/기기 사진 분류 + 한국어 OCR, Textract 미사용) | 개인 Sonnet 4.6 | 시연 10개 |

- **4 시그널 교차 검증·신뢰도** — 자칭 25% / Vision 30% / 블로그 20% / 후기 25% 가중치로 교차검증, present 시그널끼리 재분배, 자칭 도배 페널티. 등급 천장은 "근거 종류 수". 시그널 개별 기여도는 `confidence.signals`에 `int|None`으로 보존. 상세 = [`architecture.md`](architecture.md) §2·§3.
- **신뢰도 리브랜딩** — confidence는 병원 품질 평가가 아니라 *우리 분류를 뒷받침하는 독립 출처 일치도(근거 강도)*. UI/카피·자동 생성 메시지에서 "근거"로 표기, 품질평가 표현 금지, 의료법 §56 면책. (overview §4-2·§6)
- **Bedrock KB Semantic Search** (업계 통상 "RAG"지만 LLM Generation 없는 의미 검색) — 분류·설명 텍스트를 `ingest_hospital`로 KB DataSource S3(`clinic-focus/prod/{id}/{signal}.txt` + `.metadata.json`)에 업로드 → `start_ingestion_job` → KB가 청크 분할·Titan v2 임베딩·S3 Vectors 적재. 검색은 `retrieve_hospital`이 KB Retrieve로 처리하고 **검색 시점 LLM 호출 0회**. 메타필터(`sigungu`/`standard_specialty`/`confidence_score`/`lat`·`lng` bbox) 적용. 동작 원리 = [`overview.md`](overview.md) §4-5, 함수 명세 = [`API-BE-AI.md`](API-BE-AI.md).
- **★ 검색 랭킹 = 주력 강도(focus intensity)** — relevance 1순위 키를 '최고 청크 코사인 1개'에서 **주력 강도**로 교체했다. `relevance_score = max_chunk_cosine + W_PF·[쿼리 토픽 ∈ primary_focus] + W_FREQ·log1p(언급 횟수) + W_CHUNK·log1p(매칭 청크 수−1)`. 코사인 단독은 길이 정규화로 빈도/양을 씻고, 병원당 최고 청크 1개만 dedup해 반복 주장을 버리며, "메인이냐"를 못 가린다. env(`FOCUS_RANK_WPF`=0.06·`FOCUS_RANK_WFREQ`=0.010·`FOCUS_RANK_WCHUNK`=0.010·`RANK_MODE`)로 A/B 가능. 코드는 `ai/search/kb_store.py`의 `_aggregate_by_hospital`·`_focus_intensity`. 전수 A/B 검증(`be/scripts/focus_rank_eval.py`): P@1 0.571→0.655, P@5 0.562→0.617, MRR 0.675→0.734. 상세·검증 = [`architecture.md`](architecture.md) §5-1.
- **min-sim 컷** — `KB_MIN_SCORE=0.42`. 무관 쿼리는 구조적으로 '검색 결과 없음'을 돌려줄 수 있다. ([`architecture.md`](architecture.md) §5-2)
- **분류 체계 v1** — 표준 진료과목별 세부 4~6 분류(피부과: 미용/일반/피부암/모발 등, 정형외과: 척추/어깨/무릎/수부/스포츠 등). M1 시점 동결. `shared/models.py`가 BE·FE props의 단일 진실.
- **알려진 한계** — 호흡기·감기/예방접종/알레르기 등 내과·소아 thin-signal 토픽은 텍스트 빈약 → 임베딩 약함(코사인 ~0.41) → min_score 컷으로 top5 미진입. 주력 강도로도 안 고쳐짐(컷라인을 못 넘어서). 후속 과제 = [`plans/task-queue.md`](plans/task-queue.md).

### 하재원 트랙 — 프론트

**스택**: TypeScript · React + Vite · Tailwind CSS + shadcn/ui · TanStack Query · React Router · fetch · **카카오맵 JavaScript SDK** (지도 검색) · 빌드 산출물은 S3 + CloudFront로 배포

- **FE-BE 실연동** — Mock 제거하고 실 API 연결. 검색(`/api/search`)·상세(`/api/hospitals/{id}`). OpenAPI → `openapi-typescript`로 TS 타입 자동 생성(수동 동기화 금지).
- **검색 결과 화면** — 입력창 + 결과 리스트. 카드에 병원 이름·표준 진료과목·실제 주력 태그·신뢰도(근거 강도)·한 줄 요약·거리. 카드는 차별점 미리보기, 클릭 시 상세가 본 결과물.
- **카테고리 탐색 랜딩** — `GET /api/specialties?sigungu=강남구` → 진료과 그리드 타일(아이콘+건수). 과 선택 시 드릴인(닥터나우/모두닥/굿닥 패턴) + 페이지네이션. (`fe/src/components/search/CategoryGrid.tsx`, `useSpecialties.ts`)
- **페이지네이션** — `meta.total`(필터 후 전체 매칭 수)·`has_more`·`offset`·`limit`로 페이지 이동. (`fe/src/components/search/Pagination.tsx`)
- **지도 검색** — 목업 제거 → 실 `/api/search` 위치검색. 카카오맵 JS SDK, 기본 중심 강남역. 자연어/지도 토글, 신뢰도 등급별 마커 색(확실=초록·추정=노랑·부족=회색).
- **병원 상세 페이지 (9개 영역)** ⭐ 핵심 화면 — 헤드라이너(AI 통합 설명+출처 배지) / 핵심 진료 정보(주력 태그 + **다루지 않는 분야 명시** + 보유 기기 + 비급여 가격) / 의료진 / **신뢰도·근거 영역**(4 시그널 분해, `null`=회색 "수집 안 됨" 배지 / `0`%=엇갈림 구분) / 기본 운영 정보(지도 임베드·통화·운영시간) / 1-tap 피드백(localStorage device_id) / 변경 이력 미리보기 / 관련 병원(같은 주력 + **gap-fill "안 다루는 분야" 대안 병원**) / 메타·면책. 영역 명세 = [`overview.md`](overview.md) "상세 페이지 9개 영역".
- **신뢰도·근거 시각화 컴포넌트** — 색상 배지·게이지로 시각화, 검색 카드·상세 양쪽 재사용. "투명성=신뢰" 메시지를 시각으로 전달.

### 김경재 트랙 — 데이터 · 백엔드

**스택**: Python 3.11 · FastAPI + uvicorn · Pydantic · boto3 · httpx + BeautifulSoup4 (크롤링) · EC2 (배포)

- **병원 사이트 크롤러 (EC2)** — `httpx + BeautifulSoup4`로 메인·소개·진료·의료진 페이지 HTML·이미지 URL 추출 → S3 적재. robots.txt 준수·요청 간격 조절. denoise + 페이지 단위 노이즈 필터 적용(재크롤 없이 raw 재처리). 적재 = META 6117(강남 3134·송파 1331·양천 705·중구 616·용산 331), 자체사이트 정제본 2133.
- **심평원 공공 API 통합** — 의료기관 기본정보·전문의 자격·신고 의료기기 목록 수집(합법·무료). `standard_specialty` 22종은 HIRA 종별(`clCdNm`) + 병원명 파싱(`hira_adapter.map_standard_specialty`)으로 매핑('○○여성의원'→산부인과 맨끝 폴백).
- **외부 플랫폼 크롤 (4 시그널 중 블로그·후기)** — 어댑터 4종 완성(`kakao_place`/`naver_place`/`naver_blog`/`google_places`). 카카오 place앵커 후기/블로그 적재(`KAKAO#REVIEWS` 641·`KAKAO#BLOG` 347). 블로그 시그널은 교차오염이 낮은 **카카오 place앵커 blog 사용**(네이버 키워드 검색은 16.78% 오염으로 폐기, 카카오 0.75%). **네이버 플레이스 후기는 의도적 보류**(회색지대·18~25초/건·EC2 IP 차단 → 로컬 PC 크롤로 분리, [`plans/task-queue.md`](plans/task-queue.md)). PII: 작성자 owner/nickname parse 단계 마스킹·미저장, §56③ 후기 본문은 DDB·임베딩 입력만·화면 노출은 키워드 빈도만.
- **DynamoDB single-table** — `PK=hospital_id`·`SK=entity`. GSI `sigungu-specialty-index`(카테고리 탐색 BE 직접)·`geo-index`(지도 근처 검색). 스키마 = [`architecture.md`](architecture.md) §1·[`plans/task-queue.md`](plans/task-queue.md).
- **FastAPI 서버 (EC2)** — uvicorn 직접 서빙. `/api/search`(자연어+카테고리+위치)·`/api/hospitals/{id}`·`/api/specialties` + 피드백·변경 이력. OpenAPI(`/openapi.json`)는 FE TS 타입 자동 생성에 사용. 인증 없음(public).
  - **검색 경로 이원화** — 자연어 = AI `retrieve_hospital`(KB Retrieve) / 카테고리(`sigungu`·`specialty`) = BE DDB GSI 직접 / 위치 = KB lat·lng bbox + EC2 haversine 재계산. AI는 자연어 검색만 책임.
  - **relevance 순서 보존** — `be/api/search.py`는 `retrieve_hospital`이 준 주력 강도 순서를 보존한다. relevance 정렬에서 BE가 similarity(코사인)로 재정렬하면 주력 랭킹을 덮어쓰므로 **금지**. confidence/distance 정렬만 보조키와 함께 재정렬.
  - **보조정렬(결정적)** — relevance→주력강도→(코사인/confidence)→이름 / confidence→confidence desc→유사도→이름 / distance→거리→confidence→이름.
  - **페이지네이션** — `meta.total`=필터 후 전체 매칭수·`has_more`·`offset`·`limit`(상한 `le=100`). NL은 `FETCH_CAP=100`으로 받아 BE 슬라이스, 카테고리 경로는 `ProjectionExpression` 경량 처리 후 페이지 구간만 풀 하이드레이트(N+1 회피). 상세 = [`architecture.md`](architecture.md) §5-3.
  - **카테고리 탐색** — `GET /api/specialties?sigungu=강남구` → `[{specialty,count}]` desc + meta(`total_hospitals`·`total_specialties`).
- **Bedrock Vision 파이프라인** — S3 이미지 → 개인 계정 Sonnet 4.6 vision 1회 호출로 OCR + 시각 해석(Textract 미사용). 시연 10개 한정.
- **프론트 호스팅** — S3 업로드 + CloudFront 배포(`aws s3 sync` + invalidation). CI·CD 없음.

> **2026-06-01부터 추가 LLM/Vision 호출 금지**(개인계정 Sonnet 4.6 쿼터). 기존 적재분은 정적으로 사용.

---

## 마일스톤

| 시점 | 달성 기준 | 상태 |
|---|---|---|
| **M3** | 강남구 PoC 분류 결과 + 검색·상세·지도 화면 시연 (FE-BE 실연동) | ✅ as-built (강남 분류 ~3098, 검색·상세·카테고리·지도 실 API) |
| **M6** | 자연어 검색(주력 강도 랭킹) + 피드백 1-tap + 수도권 확장 | ◐ 자연어 검색·주력 강도 랭킹 완료 / 5개구 풀커버는 [`task-queue`](plans/task-queue.md) C |
| **M12** | 피드백 기반 분류 보정 + 변경 이력 공개. 평가 4요소 시연 | ○ 후속 (피드백 루프 구조·변경 이력 entity는 마련, 자동 보정 미구현) |

> 사업화 단계(전국 확장·EC2 cron 자동 갱신·hash diff 부분 재처리·인간 검수 어드민·운영 비용 구조)는
> 평가용 PoC 범위 밖이다. 비용·운영 추정은 [`overview.md`](overview.md) §10, 미구현 항목은
> [`plans/task-queue.md`](plans/task-queue.md)에 정리.

---

## 협업 의존성

- **데이터 적재 단계** — 김경재가 BE 풀커버를 진행하고, 최비성은 **계정 분리(2026-05-25)** 이후 AI 자기 계정(`kmuproj-10`)에서 강남구 표본을 독립 적재해 알고리즘·프롬프트를 병렬 튜닝. 발표 정본 데이터는 AI 계정(`kmuproj-10-clinic-Main`)에 적재된 강남 분류·KB가 기준.
- **스키마 동결** — 최비성이 분류 스키마 v1(`shared/models.py`) 동결 → 김경재 DDB 컬럼·인덱스 확정, 하재원 결과 화면 컴포넌트 props 확정. BE·AI 한쪽이 모델 바꾸면 동시에 따라간다(drift 0).
- **FE ↔ BE ↔ AI 인터페이스** — BE FastAPI OpenAPI → FE `openapi-typescript` TS 타입 자동 생성 / BE는 AI 함수를 Python `import`로 직접 호출(HTTP 아님). 인터페이스 = [`API-FE-BE.md`](API-FE-BE.md)·[`API-BE-AI.md`](API-BE-AI.md).
- **피드백 파이프** — 하재원 1-tap UI → 김경재 피드백 저장(`FEEDBACK#{device}#{ts}`) → 최비성 보정 시스템. 보정 자동화는 후속([`task-queue`](plans/task-queue.md)).

---

## 평가 4요소와의 매핑

| 평가 요소 | 본 로드맵에서의 실현 지점 |
|---|---|
| **문제 정의 (25%)** | 검색 결과 화면 + 상세 페이지 도입부가 "표준 카테고리 ≠ 실제 진료 영역"을 즉시 보여줌 → 카테고리 함정 가시화. `standard_specialty`(표준) + `primary_focus`(실제 주력) 2축 색인 |
| **문제 해결 타당성 (25%)** | 4 시그널 교차 검증 + Bedrock KB Semantic Search + **주력 강도 랭킹** + 신뢰도(근거 강도) + 익명 피드백 루프. 검색 시점 LLM 0회로 응답 빠르고 비용 ~$0.00003/검색 |
| **창의성 (25%)** | ⭐ **AI가 4 시그널을 종합해 생성한 자연어 통합 상세 설명**(`generate_description`) + **코사인 단독을 넘는 주력 강도 랭킹**(빈도·주력 주장·사례 폭 합산) — 기존 서비스(굿닥·모두닥·똑닥)가 안 하는 핵심 차별점. 자기 정체성 색인 + Bedrock Vision + Bedrock KB + 주체 명시 표현(의료법 §56 회색지대 회피) |
| **발표 (25%)** | 병원 상세 페이지 = 데모 핵심 장면. 신뢰도·근거 시각화 + 출처 배지 + 카테고리 탐색 랜딩 + 지도 검색. "레이저 제모" 같은 실측 쿼리로 주력 강도 랭킹 효과 시연 |
