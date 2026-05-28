# 개발 로드맵 — clinic-focus

> 프로젝트명: **clinic-focus** (클리닉포커스)  
> 레포: `clinic-focus` (모노레포, 폴더로 `fe/` `be/` `ai/` `shared/` 분리)

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
- 주 1회 30분 동기화. 분류 스키마·API 스펙은 별도 문서로 버전 관리.
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

- **JS 렌더링 필요한 사이트** → Playwright (Lambda Layer 추가)
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
| **정형 데이터** | DynamoDB | 지원 | 병원 / 분류 결과 / 시그널 / 신뢰도 / 피드백 / 변경 이력 |
| **원본 저장** | S3 (버킷명 `{username}-` 접두사) | 지원 | 크롤링한 HTML·이미지 원본 |
| **벡터 저장·검색** | **Bedrock Knowledge Base** (`kmuproj-team-03`, ID `GTBJ6HLFDK`, 강사 제공) | 지원 | 병원 분류·설명을 KB DataSource S3에 업로드 → KB가 Titan v2 임베딩 + S3 Vectors 적재 자동 처리. 검색은 `bedrock-agent-runtime:Retrieve` API. 내부 storage는 S3 Vectors 버킷 `bedrock-knowledge-base-1tvot3`이지만 직접 호출 ❌ |
| **LLM·Vision (시연 10개)** | Bedrock Haiku 4.5 또는 Nova | 지원 | 트랙 B 자칭 추출·`generate_description` (강사 자원, 10개 한도) |
| **Vision 고품질 시연 (10개)** | Bedrock Claude Sonnet 4.6 (`global.anthropic.claude-sonnet-4-6`, Global cross-region inference profile, 서울 리전) | 개인 | 트랙 C 이미지 분석 (한국어 OCR + 시각 해석) |
| **임베딩** | Bedrock Titan Embed Text v2 | 지원 | 병원 설명·쿼리 임베딩 (1만 전체) |
| **OCR** | (미사용) | — | Textract 한국어 미지원 → Bedrock Vision으로 흡수 |
| **프론트 호스팅** | S3 + CloudFront | 지원 | 정적 빌드 결과물 배포 + CDN 가속 |
| **배포** | 수동 (EC2 `git pull` / `aws s3 sync`) | — | CI·CD·로드밸런싱 없음 |
| **개발 환경** | EC2 + VSCode Remote-SSH | 지원 | AI 트랙 작업 환경. 로컬 VSCode가 Remote-SSH 확장으로 EC2에 접속, 편집·터미널·git·Claude Code 전부 EC2에서 실행. 인스턴스 프로파일로 지원 계정 자원 자동 인증. (Cloud9이 강사 계정에서 권한 미발급 상태 → EC2가 임시 대체. Cloud9 권한 받으면 동일 방식으로 이전 가능) |

### 왜 DynamoDB인가 (RDS 대신)

RDS도 지원 계정에서 가용하지만 DynamoDB를 택한 근거는 **우리 워크로드의 형태**가 RDB의 강점과 어긋난다는 것:

1. **S3 + DDB 분리가 정석 패턴** — 크롤링 본문(`crawl_data.json`, 페이지당 1MB+)은 S3에, 인덱싱 가능한 메타·분류 결과는 DDB에. RDS에 BLOB/TEXT 큰 칼럼 박는 건 백업 부풀음·성능 저하 안티패턴.
2. **Single-table-design 친화성** — `PK=hospital_id`로 한 병원의 모든 entity(메타·크롤링·분류·설명)를 `Query` 1회로 가져옴. RDS면 4~5개 테이블 JOIN + N+1 방지 코드 필요. (BE는 실제 `kmuproj-02-team3-backend` 단일 테이블로 운영 중)
3. **간헐적 트래픽** — 크롤링은 며칠에 한 번 몇 시간, 그 외엔 발표 시연 잠깐. DDB on-demand는 idle 시 $0, RDS `db.t4g.micro`는 항상 ~$13/월.
4. **스키마 변경 자유** — `shared/models.py`가 PoC 중 자주 바뀜 (예: P0.5 `pages=[]`/`images=[]` 빈 객체 허용). DDB는 그대로 박고, RDS면 매번 마이그레이션.
5. **RDS의 SQL 강점이 무의미** — 자연어 검색은 Bedrock KB가 처리하고 카테고리 필터는 GSI 1개로 충분. 복합 `WHERE`·풀텍스트·JOIN을 쓸 access pattern 자체가 없음.

**약점도 명시**: 1억 건 + 초당 수만 TPS가 아닌 한 성능 차이는 없고, GSI 미설계 필드로는 못 찾는 제약이 있음. 우리는 access pattern이 단순해서 이 제약에 안 걸림.

**솔직한 보완**: 초기 선택은 "AWS 매니지드 풀스택 어필 + idle $0"라는 약한 근거로 진행됐고, 위 근거 1·2·3은 BE 산출물(single-table 운영 + S3 본문 적재)을 본 뒤 사후 정리한 것. 결과적으로 워크로드와 맞아서 유지.

---

## 최비성 트랙 — AI · RAG

**스택**: Python 3.11 · boto3 (bedrock-runtime, bedrock-agent-runtime, bedrock-agent, s3) · Pydantic · `shared/models.py`

> **AI 트랙 3트랙 구조 (PoC)**: 지원 계정 Bedrock이 Haiku/Nova + 10개 한도로 제공돼서 분류는 **룰 기반(트랙 A)** 으로 1만 베이스라인을 깔고, LLM/Vision은 **시연 10개(트랙 B·C)** 에 집중한다. 자세한 건 `../ai/CLAUDE.md` "AI 트랙 3트랙 구조" 참조.

### Phase 1 (M0~3) — PoC

**자칭 컨셉 추출 프롬프트 설계**  
김경재가 크롤링한 사이트 텍스트를 Bedrock Claude Sonnet 4.6에 던져서 그 병원이 어떤 진료 분야를 메인으로 내세우는지 태그로 뽑아낸다. 예: 정형외과 사이트인데 메인 페이지에 어깨·견관절 시술 사진이 70%, 척추 언급 0% → "어깨 전문" 태그. 과목별 프롬프트 템플릿 분리 (피부과·정형외과·이비인후과·안과 등).

**Bedrock Vision 의료기기·시술 사진 인식 PoC (시연 10개)**  
병원 사이트에 올라온 의료기기 사진·시술 결과 사진을 개인 계정 Claude Sonnet 4.6 (서울 리전, Global cross-region inference profile)의 vision 입력으로 분석 (트랙 C, 10개 한정). "사마귀 냉동치료기" "라식 장비" "MRI" 같은 보유 장비 식별, 시술 사진 분포(미용 vs 일반 진료) 추출. 이미지 안 글자(의료기기 신고증·가격표 등)도 같은 Vision 호출로 OCR 처리 — Textract는 한국어 미지원으로 사용하지 않는다. PoC는 정확도 완성보다 원리 검증이 목표. **2026-05-24 hello-world 완료** ([실측 응답 카탈로그](setup/aws-onboarding.md#5-6-실제-출력--시연-응답-카탈로그-2026-05-24)).

**분류 체계 v1 정의**  
각 표준 진료과목 안에서 세부 4~6 분류 정의·문서화. 예:
- 피부과: 미용 시술 / 일반 진료(아토피·여드름) / 피부암·종양 / 모발·탈모
- 정형외과: 척추 / 어깨·견관절 / 무릎·관절 / 손·발(수부외과) / 스포츠 의학
- 이비인후과: 알레르기·비염 / 청각·이명 / 코·수면호흡 / 갑상선
- 안과: 라식·라섹 / 백내장 / 망막 / 일반 시력

스키마가 김경재의 DynamoDB 테이블 키·인덱스, 하재원 컴포넌트 props의 기반. **M1 시점 동결 필요**.

**신뢰도 점수 산출 로직 v1**  
4개 시그널(자칭 / Vision / 블로그 / 후기)이 한 방향으로 정렬되면 점수 높게, 엇갈리면 페널티. 구간은 95%↑ "확실" / 70~95% "추정" / 70% 미만 "정보 부족". 모든 분류 결과에 점수와 근거 시그널이 따라다니고 사용자에게 분류와 함께 노출. **평가요소 "AI 분류 오류 대응"의 핵심 장치.**

**AI 통합 상세 설명 생성 (`generate_hospital_description`)** ⭐ **본 서비스의 핵심 결과물**  
4 시그널 데이터(자칭·Vision·블로그·후기) + 분류 결과 + 신뢰도 점수를 Bedrock Claude Sonnet 4.6에 입력해 병원의 정체성·실제 진료 영역·강점·약점·주의사항을 **자연어 단락**으로 생성한다. 모든 문장에 출처 시그널 태그(`[사이트]`, `[Vision]`, `[블로그]`, `[후기]`)를 자동 부착해 추적 가능성 확보. 의료법 회색지대 회피를 위해 항상 주체 명시 표현 사용("이 병원이 자기 사이트에서 ~를 메인으로 표시함"). 프롬프트 템플릿은 별도 파일로 관리하며 과목별로 분리. 출력 결과는 DynamoDB에 저장돼 상세 페이지 API가 그대로 반환. **기존 서비스(굿닥·모두닥·똑닥)와의 가장 큰 차별점이 시각화되는 지점.**

### Phase 2 (M3~6) — 베타

**Bedrock Knowledge Base 기반 Semantic Search 엔진** (업계 통상 "RAG"라 부르지만 엄밀히는 LLM Generation이 없는 의미 검색)  
병원 분류 결과·설명 텍스트를 KB DataSource S3에 업로드 → KB가 Titan Embed Text v2로 자동 임베딩하고 S3 Vectors에 적재. 사용자가 "M자 탈모 처방받을 수 있는 강남 의원" 같이 자연어로 검색하면 `bedrock-agent-runtime:Retrieve` 호출 → KB가 내부에서 쿼리 임베딩 + 벡터 검색 → 메타필터(`sigungu`/`standard_specialty`/`confidence_score`/`lat`/`lng` bounding box) 적용 → DynamoDB에서 신뢰도 점수 조인 → 정렬해서 반환. **사용자 검색 시점엔 LLM(Sonnet/Haiku) 호출 0건** — KB가 Titan 임베딩만 호출하는 구조라 응답 ~200~500ms, 검색당 비용 ~$0.00003. LLM은 사전 단계의 `generate_description`·Vision 분석·자칭 추출에만 도는데, 이건 한 번 처리 후 정적 데이터로 6개월~1년 우려먹는다 (자세한 건 `overview.md` "4-5. 검색 동작 원리" 참조). **검색 경로 이원화**: 자연어 검색은 KB 경유, `sigungu=강남구 & specialty=피부과` 같은 단순 카테고리 탐색은 BE DynamoDB GSI 직접 조회 (AI 미경유).

**4 시그널 교차 검증 알고리즘**  
Phase 1의 신뢰도 점수 v1 본격화. 자칭 컨셉·Vision 결과·블로그 주제 분포·후기 키워드 빈도 4축 가중치 조정 + 정렬 검증. 한 방향 정렬된 분류만 "확실/추정"으로 노출, 엇갈린 분류는 "정보 부족" 표기.

**자칭 도배 페널티 로직**  
병원이 "전문" "특화" 키워드를 사이트에 도배해도 나머지 시그널(Vision·후기·블로그)이 따라오지 않으면 분류 점수를 강하게 감점. 도배 의심도가 임계치 넘으면 분류 결과에서 제외.

### Phase 3 (M6~12) — 정식

**피드백 학습 → 분류 보정 시스템**  
하재원의 1-tap UI에서 들어온 익명 피드백을 누적해서 분류 보정. 같은 병원에 부정 피드백이 N건 넘으면 분류 자동 재검토 트리거. 재학습은 주기적(주 1회 또는 N건 임계). **이 모듈이 평가요소 "사용자 피드백 루프"의 실증.**

**인간 검수 워크플로**  
AI 자동 보정이 곤란한 케이스(애매·의료 영향 큼)는 검수자 큐로 전달. 검수자 어드민 페이지에서 문제 분류 + 원본 시그널 + 피드백을 같이 보고 판정. 의료 도메인 자문 패널 1~2인은 자문 계약 형태로 유지.

**분류 변경 이력 관리**  
분류가 바뀐 모든 병원의 변경 이력을 DynamoDB에 적재. "2026년 3월 미용 전문 → 4월 일반 진료 비중 증가로 변경" 같은 기록을 사용자가 조회 가능. 투명성 + 분쟁 대응.

---

## 하재원 트랙 — 프론트

**스택**: TypeScript · React + Vite · Tailwind CSS + shadcn/ui · TanStack Query · React Router · fetch · **카카오맵 JavaScript SDK** (지도 검색) · 빌드 산출물은 S3 + CloudFront로 배포

### Phase 1 (M0~3) — PoC

**바이브 코딩으로 즉시 개발 진입**  
와이어프레임 없이 Claude Design + Claude Code로 React + Vite + Tailwind + shadcn/ui 코드를 바로 작성. M1 분류 스키마 동결 전에는 Mock 데이터로 화면 골격 먼저 만들고 스키마 확정 후 BE 자동 생성 OpenAPI 스펙에서 `openapi-typescript`로 TS 타입을 뽑아 props 교체. 모바일 반응형·다크모드는 별도 작업 항목으로 잡지 않음 (바이브 코딩 기본 제공 수준에 위임).

**검색 결과 화면 v1**  
입력창 + 결과 리스트. 각 결과 카드에 병원 이름·표준 진료과목·실제 주력 태그·신뢰도 점수·한 줄 요약. 예: "○○피부과 / 피부과 / 실제 주력: 일반 진료 (확실 92%) / 일반 피부 진료 중심, 미용 시술은 거의 안 하는 동네 의원". **카드는 차별점의 미리보기**이고, 클릭 시 진입하는 상세 페이지가 본 결과물.

**병원 상세 페이지** ⭐ **본 서비스의 핵심 화면**  
검색 결과 카드 클릭 시 진입하는 이 페이지가 차별점이 노출되는 자리이자 데모 핵심 장면. 9개 영역 구성:

1. **헤드라이너 — AI 통합 설명** (최비성의 `generate_description` 출력)  
   페이지 최상단에 자연어 단락 그대로 렌더. 출처 태그 `[사이트]` `[Vision]` `[블로그]` `[후기]`는 시각적 배지로 처리. 배지 클릭 시 ④번 영역으로 스크롤 또는 모달 오픈

2. **핵심 진료 정보**  
   - 표준 진료과목 + 실제 주력 분야 태그
   - 다루는 세부 진료 항목 리스트
   - **다루지 않는 분야 명시** (헛걸음 방지 핵심)
   - 보유 의료기기 ○/✗ 표시
   - 비급여 가격 (있는 경우)

3. **의료진 정보**  
   원장·의사 명단, 전문의 자격(심평원), 세부 전공·경력. 의사별 진료 분야가 다르면 분리 표시

4. **신뢰도·근거 영역**  
   신뢰도 게이지 + 4 시그널 기여도 분해. 자칭 컨셉 원문 인용·시술 사진 분포·블로그 주제 분포·후기 키워드 빈도를 펼침 메뉴로 제공

5. **기본 운영 정보**  
   주소(지도 임베드) · 전화(탭하면 통화) · 운영시간 · 야간·주말 진료 · 주차 · 예약 방법 · 홈페이지 링크

6. **사용자 피드백 영역**  
   👍/👎 1-tap UI + 누적 통계 표시 ("이 분류에 대한 사용자 피드백: 👍 87% / 👎 13% (N=145)") + 분류 오류 신고 버튼

7. **분류 변경 이력 미리보기**  
   최근 변경 1~2건 노출 + 전체 이력 페이지 링크

8. **관련 병원 추천**  
   같은 동네에서 같은 세부 주력을 다루는 병원 3~5곳 + **"이 병원이 안 다루는 분야"의 대안 병원** (예: "사마귀 냉동치료는 △△의원에서 가능")

9. **메타 정보**  
   데이터 마지막 업데이트 시각 + 출처 고지 + 신뢰도 70% 미만 시 "정보 부족" 경고 배너

이 9개 영역이 한 페이지에 응축되어 환자가 헛걸음 없이 결정 가능한 종합 정보를 제공. 굿닥·모두닥의 정보 나열식 페이지와 가장 크게 다른 지점.

**신뢰도·근거 시각화 컴포넌트**  
신뢰도를 숫자만이 아니라 색상 배지·게이지로 시각화. 검색 카드와 상세 페이지 양쪽에서 재사용. **평가요소 "투명성 = 신뢰" 메시지를 시각으로 전달하는 핵심 컴포넌트.**

### Phase 2 (M3~6) — 베타

**자연어 검색 UI**  
검색창에 자연어 질의 가능. 예: "M자 탈모 처방받을 수 있는 동네 의원" → API Gateway → EC2 FastAPI → AI `retrieve_hospital` → Bedrock KB Retrieve → 결과 표시. 자동 완성·인기 검색어·최근 검색 기록(localStorage)은 기본 UX.

**지도 기반 내 근처 검색 UI** ⭐ **핵심 사용 케이스**  
카카오맵 SDK 임베드. 사용자 현재 위치(GPS, `navigator.geolocation`)를 잡고 반경 내 병원을 지도 마커로 표시. 반경 슬라이더(0.5 / 1 / 3 / 5 / 10km), 마커 색상은 신뢰도 등급별로 다름(확실 = 초록, 추정 = 노랑, 정보 부족 = 회색). 마커 클릭 시 카드 팝업 → 상세 페이지 진입. 자연어 검색과 지도 뷰 토글 가능 — 예: "어깨 잘 보는 정형외과" 검색 후 지도 뷰로 전환하면 결과를 마커로 표시. 결과 리스트는 거리순/신뢰도순 정렬 토글.

**사용자 피드백 1-tap UI (익명)**  
검색 후 병원 다녀온 사용자에게 짧은 카드 노출: "○○피부과의 아토피 진료, 실제로 어땠나요?" + 👍 / 👎 두 버튼. 한 번 탭이면 끝, 글쓰기·로그인·양식 전혀 없음. 중복 방지는 **localStorage + 브라우저 디바이스 ID(브라우저별 임의 UUID 생성·저장)** 로 처리. 같은 디바이스에서 같은 병원에 대해 1회만 가능. 봇 방지는 평가 환경에서는 생략, 운영 단계에서 Cloudflare Turnstile 같은 무료 옵션 검토.

### Phase 3 (M6~12) — 정식

**신뢰도·근거 시그널 상세 뷰**  
Phase 1 시각화 컴포넌트 확장. 각 시그널이 분류에 얼마나 기여했는지 breakdown 그래프로 표시. 예: "어깨 전문 분류 신뢰도 92% — 사이트 35% + Vision 30% + 블로그 15% + 후기 12%". 사용자가 직접 근거를 검토 가능.

**분류 변경 이력 공개 페이지**  
최비성의 변경 이력 DB를 사용자가 직접 조회. "이 병원의 분류 변경 히스토리" + 변경 사유(피드백 누적 / 인간 검수 / Vision 재분석) 표시.

---

## 김경재 트랙 — 데이터 · 백엔드

**스택**: Python 3.11 · FastAPI + uvicorn · Pydantic · boto3 · httpx + BeautifulSoup4 (크롤링) · EC2 (배포)

### Phase 1 (M0~3) — PoC

**병원 사이트 크롤러 (EC2)**  
PoC 대상 서울 5개 구 약 1만 병원 사이트 자동 수집. `httpx + BeautifulSoup4`로 한 사이트당 메인·소개·진료 안내·의료진 등 핵심 5~10 페이지의 HTML·이미지 URL 추출 → S3에 원본 적재. robots.txt 준수, User-Agent 명시, 요청 간격 조절. JS 렌더링 필요한 사이트는 Playwright로 보강. EC2는 실행 시간 제한이 없어 한 프로세스로 장시간 크롤링 가능 — 부하가 크면 SQS로 작업을 분산한다.

**심평원 공공 API 통합**  
건강보험심사평가원 공공 데이터 포털에서 의료기관 기본 정보·전문의 자격·신고된 의료기기 목록 수집. 합법·무료. 콜드 스타트(신규·지방 병원 데이터 빈약) 완화 + 크롤링 보조.

**외부 플랫폼 크롤 — 실측 요약 (2026-05-28)**  
4 시그널 중 블로그·후기는 외부 플랫폼에서 온다. 어댑터 4종 완성(`be/adapters/{kakao_place,naver_place,naver_blog,google_places}_adapter.py`), 실제 크롤 실행은 운영자 결정.

- **합법 경로**: 구글 Places API(Text Search→Details, reviews 5건) · 네이버 검색 API(`v1/search/blog`). 공식 키, robots/약관 무관.
- **회색지대**: 네이버 플레이스·카카오맵 후기·정보 탭은 비공식 엔드포인트뿐 — robots.txt 전부 `Disallow: /` + 약관 자동화 금지. 실행은 운영자 판단.
  - 네이버: Playwright headless 로 `ncpt` 토큰 자동 발급 → `pcmap-api.place.naver.com/graphql`(getVisitorReviews). 1건 18~25초. 병원 카테고리는 키워드 통계 미노출이라 후기 본문에서 자체 추출.
  - 카카오: httpx 단발(토큰 불필요, 1~3초). `place-api.map.kakao.com/panel3` 1회로 자칭 tags·HIRA 정제본·후기·블로그 시드를 묶어 회수(네이버 3호출분).
- **공통 제약**: 검색 매칭 실패율 ~40%(정확한 병원명+지역 필요), 1만 풀커버 IP rate-limit 미실측.
- **PII·의료법**: 작성자 owner/nickname 은 parse 단계 마스킹·미저장. §56③ — 후기 본문 raw 는 DDB 저장·임베딩 입력만, 화면 노출은 키워드 빈도만.
- **Vision 입력 동결**: 자체 사이트 이미지 한정. 외부 플랫폼 사진은 Vision 분석 제외(자칭 오염 방지), FE 대표 이미지 용도로만.

**DynamoDB 스키마 설계**  
핵심 테이블: Hospitals / Classifications / Signals / Confidence / Feedback / ChangeHistory. 최비성의 분류 스키마 v1을 파티션 키·정렬 키·GSI 구조로 반영. 위치 기반 검색은 KB metadata 필터(`lat`/`lng` bounding box) + EC2 haversine 재계산으로 처리. 단순 카테고리 탐색(`sigungu#specialty` 완전일치)은 DynamoDB GSI로 BE가 직접 조회.

**FastAPI 기반 API 서버 (EC2)**  
FastAPI 라우터를 EC2에서 uvicorn으로 직접 서빙. 검색 API, 병원 상세 API, 분류 변경 이력 API, 피드백 제출 API 네 개 엔드포인트. 자동 생성되는 OpenAPI 스펙(`/openapi.json`)은 프론트가 TS 타입 자동 생성에 그대로 사용. 인증 없음 — public endpoint. 호출 제한이 필요하면 API Gateway를 EC2 앞단에 둘 수 있다.

**프론트 호스팅 (S3 + CloudFront)**  
하재원 빌드 결과물을 S3에 업로드, CloudFront로 배포. 수동 배포 (`aws s3 sync` + CloudFront invalidation).

### Phase 2 (M3~6) — 베타

**Bedrock Vision 파이프라인**  
Phase 1에서 S3에 적재한 이미지 URL을 EC2 batch로 처리. 의료기기 신고증·시술 사진·기기 사진 모두 개인 계정 Bedrock Claude Sonnet 4.6 vision (서울 리전) 한 번 호출로 OCR + 시각 해석을 같이 받는다 (Textract 미사용). 결과는 DynamoDB에 적재. PoC 단계에서는 시연 10개 병원에 한정.

**Bedrock KB 인덱스 구축**  
최비성이 정의한 분류 결과·설명 텍스트를 `ingest_hospital`로 KB DataSource S3에 업로드(`{hospital_id}.txt` + `{hospital_id}.txt.metadata.json` 동봉) → `start_ingestion_job` 호출하면 KB가 자동으로 청크 분할·Titan v2 임베딩·S3 Vectors 적재. metadata에 지역·진료과목·세부 주력·신뢰도 점수 + **위경도(lat, lng)** 를 함께 저장해 KB Retrieve `vectorSearchConfiguration.filter` 단계에서 필터링 가능.

**지오 검색 API (`/api/search/nearby`)** ⭐  
사용자 현재 위경도 + 반경(km)을 받아 반경 내 병원 리스트를 반환. 구현:
1. 입력 위경도 기준 bounding box 계산 (반경 5km면 위경도 ±0.045°)
2. KB Retrieve `filter`로 1차 후보 추출 (bounding box 내 lat/lng + 쿼리 텍스트 매칭)
3. Lambda에서 haversine 공식으로 정확한 거리 계산 → 반경 내 필터링
4. 거리순 또는 신뢰도순 정렬해서 반환

자연어 검색과 결합 가능: 자연어 쿼리 + 위경도 둘 다 받으면 의미 매칭 + 지리적 필터링 동시 적용.

**변경 감지(diff) 시스템 — 사업화 운영의 핵심**  
재크롤링 시 페이지 단위로 본문 hash 비교 → 변경된 페이지만 다시 AI 분석. 전체 재처리 대비 비용 80~90% 절감. 변경 이력 DB 자동 기록. 평가 단계에서는 수동 트리거로 충분하지만, **사업화 시 운영 비용 통제의 핵심 메커니즘** 이라 구조는 PoC부터 잡아둔다 — `crawled_at` + `body_hash` 컬럼 + diff 워커 분리.

데이터 종류별 갱신 빈도 (사업화 기준):

| 데이터 종류 | 변경 빈도 | 갱신 주기 |
|---|---|---|
| 메인 페이지 컨셉 | 연 1~2회 | 주 1회 크롤링 → 변경 시만 재분석 |
| 의료진 정보 | 연 2~4회 | 주 1회 |
| 시술/가격 안내 | 연 3~6회 | 주 1회 |
| 블로그 포스팅 | 주 0~2개 | 일 1회 (별도 시그널) |
| 후기 (외부) | 수시 | 주 1회 |
| 심평원 공공 데이터 | 월 1회 | 월 1회 |

크롤링 자체는 비용 무시 수준(HTTP 요청)이고, 진짜 비용은 LLM 재분석. hash diff로 변경 페이지만 통과시키면 전국 7만 병원도 월 ~$700 수준.

**피드백 저장 구조 (DynamoDB)**  
하재원의 1-tap UI에서 들어온 익명 피드백 저장. 파티션 키는 `hospital_id`, 정렬 키는 `device_id#timestamp`. 1디바이스 1피드백은 `device_id + hospital_id` 조합 unique 체크로 처리.

### Phase 3 (M6~12) — 정식

**EC2 cron 기반 자동 갱신 (사업화 핵심 파이프라인)**  
주 1회 cron이 전 병원 크롤링 트리거 → 페이지별 hash diff → 변경 페이지만 SQS에 적재 → AI 워커가 큐 소비 → DB 적재. 실패 알림은 SNS로 메일 발송. 운영 비용은 변경분에만 LLM 호출되므로 전국 7만 병원도 월 ~$700 수준 (자세한 추정은 `overview.md` "운영 비용 구조" 참조).

**인간 검수자 어드민 백엔드**  
하재원의 검수자 어드민 페이지가 호출할 API. 분류 대기열·시그널 원본·피드백 누적 통계 조회 가능. 인증은 IAM이나 Cognito 대신 단순 API Key (평가 단계).

---

## Phase 1 (M0~3) — V2 완전 서비스 단계 분해

`docs/plans/task-queue.md` 의 Phase A~G 가 V2(본 서비스 9가지 차별점 + 4 외부 소스 + DDB single-table + 임베딩 통합) 까지 가는 단계. 트랙별 작업 매핑:

| Phase | 핵심 | AI | BE | FE |
|---|---|---|---|---|
| **A. 기반 재설계** | DDB single-table + shared/models 4 시그널 + 외부 API 키 발급 + 이슈 #23/#24 머지 | shared/models 확장 | 단일 어댑터 재작성 + 이슈 #23/#24 + 키 발급 | OpenAPI TS 타입 재생성 |
| **B. 외부 시그널 크롤러 4종** | 자체 사이트 정제(#13) + 네이버 플레이스·블로그 + 카카오 확장 + 구글 Places + hash diff | — | 4 크롤러 + DDB entity 적재 | — |
| **C. AI 본체화 + 4 시그널 통합** | scratch→ai/ + classify·describe 4 시그널 재설계 + Vision 활성화 + extract·related·recompute·aggregate·변경이력 자동 기록 | 전부 | `ingest_hospital` 파이프라인 호출부 | — |
| **D. BE FastAPI 4개 본체** | /api/search(자연어+지도) + /api/hospitals/{id}(9영역) + /api/hospitals/{id}/history + /api/feedback + CORS | API 함수 시그니처 합의 | 전부 | API 스펙 받아 hook 갱신 |
| **E. FE 9영역 + 시그널 시각화** | 9개 영역 컴포넌트 + 4 시그널 기여도 차트 + 1-tap 피드백 + 변경 이력 + 차등 렌더링 + 카카오맵 신뢰도 색 마커 | — | — | 전부 |
| **F. 표본 확장 + 통합 검증** | 88 → 1000 → 1만 풀커버 + 의료법 전수 검수 + 통합 E2E 5건 + 비용 측정 | 분류 일괄 + 의료법 검수 | 풀크롤링 + KB 일괄 ingest | E2E 시나리오 검증 |
| **G. 인프라·운영 마무리** | systemd 검증 + CloudFront + .env 정렬 + PR 리뷰 | — | systemd · 배포 | S3+CloudFront 정적 배포 |

병렬 진행 가능:
- Phase A 내부 4 항목 병렬
- Phase B 의 4 크롤러 병렬 (소스별 독립)
- Phase C·D 의 인터페이스 합의 후 동시 진행
- Phase E 는 Phase D `/api/*` skeleton 만 있어도 진입 (Mock 가능)

진척 현황(2026-05-27):

- AI 트랙 ✅ scratch e2e 통과 (PR #25, 자칭만으로 14개). Phase A·C 진입 전
- BE 트랙 ⏳ 이슈 #23/#24/#13/#18 위임 상태, 외부 3 크롤러 신규 필요
- FE 트랙 △ 검색·상세·지도 화면 골격 OK (PR #14), 9영역 컴포넌트 분리·실 API 미연결

연관 문서: [`plans/task-queue.md`](plans/task-queue.md) §4 (Phase A~G 상세 체크리스트) + §5 (의존성 그래프).

---

## 마일스톤

| 시점 | 달성 기준 |
|---|---|
| **M3** | 서울 5개 구 1만 병원 분류 결과 + 검색 화면 시연 가능 (PoC 데모) |
| **M6** | 자연어 검색 + 피드백 1-tap 작동. 수도권 확장 |
| **M12** | 피드백 기반 분류 보정 + 변경 이력 공개. 평가 4요소 모두 시연 가능 단계 |

---

## 협업 의존성

- **M0~1.5** — 김경재가 BE 풀커버(서울 5개구 1만) 진행. 최비성은 **계정 분리(2026-05-25)** 이후 AI 자기 계정(`kmuproj-10`)에서 강남구 4과목 ~85개 미니 표본을 독립 적재해 알고리즘·프롬프트 튜닝 병렬 진행 ([task-queue Step 6](plans/task-queue.md#step-6--ai-개인-dev-계정-e2e-ddb--s3--28개--85개-미니-크롤링--진행-중)). 하재원은 Mock·심평원 공공 데이터로 화면 골격 병렬. 발표 정본은 **BE 계정 풀커버**가 정본이며 AI 계정 미니 표본은 개발·튜닝 보조.
- **M1** — 최비성이 분류 스키마 v1 동결. 김경재는 DynamoDB 컬럼·인덱스 확정, 하재원은 결과 화면 컴포넌트 props 확정.
- **M4~5** — 하재원 1-tap 피드백 UI → 김경재 피드백 저장 → 최비성 보정 시스템 데이터 파이프 연결.

---

## 평가 4요소와의 매핑

| 평가 요소 | 본 로드맵에서의 실현 지점 |
|---|---|
| **문제 정의 (25%)** | 검색 결과 화면 + 상세 페이지 도입부가 "표준 카테고리 ≠ 실제 진료 영역"을 즉시 보여줌 → 카테고리 함정 가시화 |
| **문제 해결 타당성 (25%)** | 4 시그널 교차 검증 + Bedrock KB Semantic Search + 신뢰도 점수 + 익명 피드백 루프 |
| **창의성 (25%)** | ⭐ **AI가 4 시그널을 종합해 생성한 자연어 통합 상세 설명** (`generate_hospital_description`) — 기존 서비스가 안 하는 핵심 차별점. 추가로 자기 정체성 색인 + Bedrock Vision + Bedrock Knowledge Base 활용 + 주체 명시 표현(의료법 회색지대 회피) |
| **발표 (25%)** | 병원 상세 페이지 = 데모 핵심 장면. 신뢰도·근거 시각화 + 출처 배지 + 변경 이력 페이지 |