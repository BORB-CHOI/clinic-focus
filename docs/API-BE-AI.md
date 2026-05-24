# API 명세: BE ↔ AI

> 김경재(백엔드) ↔ 최비성(AI/RAG) 간 인터페이스 정의

---

## 호출 방식

**BE와 AI는 같은 EC2 인스턴스의 단일 Python 프로세스에서 돌아간다.** 모노레포의 `be/` `ai/` `shared/` 가 한 프로세스에 함께 로드되고, BE는 AI 함수를 Python 패키지 import로 직접 호출.

```python
# be/handlers/ingest_hospital.py
from ai import classify_hospital, generate_description
from shared.models import CrawlData
```

- 호출 지연 없음 (같은 프로세스 내 함수 호출)
- 디버깅·테스트 쉬움
- 평가용 PoC라 개별 배포 필요성 없음, 인프라 단순화

> 추후 트래픽이 커지거나 AI 모듈을 다른 서비스에서도 호출하게 되면 별도 서비스로 분리하면 된다. 이 경우에도 본 문서의 함수 시그니처가 그대로 HTTP body 스키마로 매핑되므로 호출 코드만 바꾸면 됨 — **인터페이스 명세는 동일.**

---

## 공유 Pydantic 모델

`shared/models.py`에 정의해서 BE·AI 양쪽에서 import.

### `CrawlData`
```python
class CrawlData(BaseModel):
    hospital_id: str
    website_url: str
    pages: list[CrawledPage]
    images: list[CrawledImage]
    public_data: PublicData  # 심평원 공공 데이터

class CrawledPage(BaseModel):
    url: str
    page_type: Literal["main", "about", "service", "doctors", "blog", "other"]
    html_text: str           # HTML에서 추출한 plain text
    fetched_at: datetime

class CrawledImage(BaseModel):
    url: str                 # S3 URI
    page_url: str            # 어느 페이지에서 발견됐는지
    alt_text: str | None

class PublicData(BaseModel):
    license_number: str
    specialists: list[str]   # 전문의 자격
    registered_devices: list[str]  # 신고된 의료기기
```

### `Classification`
```python
class Classification(BaseModel):
    hospital_id: str
    standard_specialty: str
    primary_focus: list[str]
    confidence: Confidence
    detailed_signals: DetailedSignals
    classified_at: datetime
    classifier_version: str  # 알고리즘 버전 추적

class Confidence(BaseModel):
    score: int  # 0~100
    level: Literal["확실", "추정", "정보 부족"]
    signals: SignalContributions

class SignalContributions(BaseModel):
    self_claim: int   # 0~100, 각 시그널의 신뢰도 기여도
    vision: int
    blog: int
    reviews: int

class DetailedSignals(BaseModel):
    self_claim: SelfClaimSignal
    vision: VisionSignal
    blog: BlogSignal
    reviews: ReviewSignal
```

### `HospitalDescription` — AI 통합 상세 설명 ⭐
```python
class HospitalDescription(BaseModel):
    """본 서비스의 핵심 결과물. 4 시그널을 종합한 자연어 통합 설명."""
    hospital_id: str
    headline: str                   # 1문장 헤드라인
    paragraphs: list[DescriptionParagraph]
    one_line_summary: str           # 검색 카드용 한 줄 요약
    generated_at: datetime
    generator_model: str            # 사용된 LLM 모델 ID

class DescriptionParagraph(BaseModel):
    text: str
    citations: list[Literal["self_claim", "vision", "blog", "reviews", "public_data"]]
```

### `SearchQuery`, `SearchResult`
```python
class SearchQuery(BaseModel):
    query_text: str | None = None       # 자연어 쿼리 (없으면 위치 기반 단독 검색)
    lat: float | None = None            # 사용자 위도
    lng: float | None = None            # 사용자 경도
    radius_km: float = 3.0              # lat/lng 있을 때 검색 반경
    sido: str | None = None
    sigungu: str | None = None
    specialty: str | None = None
    min_confidence: int = 70
    sort: Literal["distance", "confidence", "relevance"] = "relevance"
    limit: int = 20

    # query_text 또는 (lat, lng) 중 최소 하나 필수 — 검증 로직 별도

class SearchResult(BaseModel):
    hospital_id: str
    similarity_score: float | None      # 자연어 검색 시 KB Retrieve score. 없으면 None
    distance_km: float | None           # 위치 검색 시 거리. 없으면 None
    matched_focus: list[str]
    query_interpretation: str | None    # LLM이 해석한 자연어 쿼리 의도
```

> **검색 경로 이원화**: 자연어 쿼리는 AI 모듈(`retrieve_hospital`)이 KB Retrieve API 경유로 처리하고, 단순 카테고리 탐색(`sigungu=강남구 & specialty=피부과` 같은 메타 완전일치 전체 목록)은 BE가 DynamoDB GSI로 직접 조회한다. AI는 자연어 검색만 책임 — KB Retrieve는 빈 쿼리 텍스트를 받지 못하고 `numberOfResults` 최대 100 제한이 있어 카테고리 탐색에 부적합.

### `ImageAnalysisResult`
```python
class ImageAnalysisResult(BaseModel):
    image_url: str
    detected_devices: list[str]
    image_category: Literal["일반 진료", "미용 시술", "장비 사진", "건물·내부", "기타"]
    confidence: float  # 0~1
```

### `FeedbackEntry`
```python
class FeedbackEntry(BaseModel):
    feedback_id: str
    hospital_id: str
    device_id: str
    primary_focus: str
    verdict: Literal["agree", "disagree"]
    received_at: datetime
```

---

## AI 모듈 함수 명세

### 1. `classify_hospital`

크롤링된 사이트 데이터를 받아 분류 결과 + 신뢰도 + 시그널 기여도를 반환. **PoC의 핵심 함수.**

```python
def classify_hospital(
    crawl_data: CrawlData,
    use_vision: bool = True,
) -> Classification:
    ...
```

#### 동작 흐름

PoC에서는 **3트랙으로 분기**한다 (자세한 건 `../ai/CLAUDE.md` "AI 트랙 3트랙 구조" 참조):

- **트랙 A (룰 기반, 서울 1만 풀커버)**: 정제된 텍스트의 키워드 빈도 + 페이지 타입별 강조도로 자칭 컨셉 추출. LLM 미사용. `use_llm=False` 분기.
- **트랙 B (LLM 시연, 10개)**: 지원 계정 Haiku/Nova로 자칭 컨셉 추출 — 룰 결과보다 정밀.
- **트랙 C (Vision 시연, 10개)**: 개인 계정 Sonnet 4.5 Vision으로 이미지 분석. `use_vision=True` 분기.

공통 흐름:

1. 자칭 컨셉 추출 (트랙 A/B 중 하나)
2. 이미지 분석 (트랙 C — `use_vision=False`면 생략, 시연 10개에만 True)
3. 블로그 페이지의 키워드 빈도 분석
4. 후기 키워드 빈도 분석 (수집된 후기가 있을 때)
5. 4 시그널 교차 검증 → 신뢰도 점수 계산. Vision 시그널 없으면 가중치 재정규화.
6. 자칭 도배 페널티 적용
7. `Classification` 반환

#### 의존성

- 트랙 A: 추가 의존성 없음 (룰만)
- 트랙 B: `BEDROCK_LLM_MODEL_ID` (지원 계정, 예: `anthropic.claude-haiku-4-5-...`), 인스턴스 프로파일 자동 인증
- 트랙 C: `BEDROCK_VISION_MODEL_ID` (개인 계정, `anthropic.claude-sonnet-4-5-20250929-v1:0`), 개인 계정 자격증명 (`AI_AWS_*` 환경변수)
- `AWS_REGION`: 기본 `us-east-1`
- IAM 권한: 지원 계정 `bedrock:InvokeModel`, 개인 계정 `bedrock:InvokeModel`

#### 예외
- `BedrockInvocationError` — Bedrock 호출 실패
- `InsufficientDataError` — 크롤링 데이터가 너무 빈약 (페이지 0개, 또는 전부 빈 텍스트)

#### 사용 예시
```python
from ai import classify_hospital
from shared.models import CrawlData

crawl_data = CrawlData(...)  # 김경재가 크롤링 후 채워서 전달
result = classify_hospital(crawl_data)

# DynamoDB에 저장
db.put_item(
    TableName="Classifications",
    Item=result.model_dump(),
)
```

---

### 2. `generate_description` ⭐ **본 서비스의 핵심 함수** (시연 10개 한정)

분류 결과 + 4 시그널 원본 데이터를 받아 자연어 통합 상세 설명을 생성. **FE-BE `GET /api/hospitals/{id}` 응답의 `ai_description` 필드가 이 함수의 결과.**

> **PoC 한도**: 지원 계정 Bedrock 자원이 10개 병원 한도이므로 시연 10개 병원에만 호출. 나머지 9990개 병원은 `ai_description = null` 로 반환되고 FE가 자연어 단락 대신 룰 기반 태그 카드를 렌더링한다. 어느 병원이 시연 대상인지는 DynamoDB `HospitalDescriptions` 테이블에 레코드 존재 여부로 판별.

```python
def generate_description(
    classification: Classification,
    detailed_signals: DetailedSignals,
    hospital_meta: HospitalMeta,  # 이름·주소 등 기본 정보
) -> HospitalDescription:
    ...
```

#### 동작 흐름

**PoC에서는 시연 10개 병원에만 적용** (트랙 B). 나머지 9990개는 자연어 단락 없이 룰 기반 태그·메타데이터만 제공.

1. 분류 결과·신뢰도·4 시그널 원본 데이터를 구조화된 컨텍스트로 정리
2. 지원 계정 Bedrock Haiku/Nova에 전용 프롬프트 + 컨텍스트 입력
3. 프롬프트는 다음을 강제:
   - **주체 명시 표현 의무** — "이 병원이 자기 사이트에서 ~를 메인으로 표시함" 형태만 허용
   - **출처 시그널 태그 의무** — 각 단락의 주장이 어떤 시그널에서 나왔는지 `citations` 목록 자동 첨부
   - **평가·추천 표현 금지** — "잘 본다" "추천한다" 같은 의료광고 회색지대 표현 사용 금지
   - **약점·주의사항도 포함** — 보유하지 않은 장비, 다루지 않는 분야도 명시
4. 출력은 구조화된 JSON으로 받아 `HospitalDescription`으로 파싱
5. 1문장 `one_line_summary`도 별도로 생성 (검색 카드용)

#### 의존성

- `BEDROCK_LLM_MODEL_ID` (지원 계정, 예: `anthropic.claude-haiku-4-5-...`)
- IAM: `bedrock:InvokeModel` (인스턴스 프로파일 자동 인증)
- 프롬프트 템플릿 파일 (`ai/prompts/hospital_description.md`)

#### 예외
- `BedrockInvocationError`
- `DescriptionValidationError` — 출력이 주체 명시 원칙·출처 태그 의무를 위반하면 재시도 또는 실패 처리

#### 사용 예시
```python
from ai import classify_hospital, generate_description

classification = classify_hospital(crawl_data)
description = generate_description(
    classification=classification,
    detailed_signals=classification.detailed_signals,
    hospital_meta=hospital_meta,
)

# DynamoDB에 저장 — Classification과 함께 또는 별도 테이블
db.put_item(
    TableName="HospitalDescriptions",
    Item=description.model_dump(),
)
```

#### 출력 예시
```python
HospitalDescription(
    hospital_id="h_abc123",
    headline="○○피부과는 일반 피부 진료 중심의 동네 의원입니다.",
    paragraphs=[
        DescriptionParagraph(
            text="홈페이지 메인 화면에서 아토피·여드름·습진 같은 일반 피부질환을 가장 먼저 안내하고 있으며, 시술 사진 80%가 일반 진료 케이스(피부 발진·습진·여드름)고 미용 시술 사진은 18%로 적습니다. 블로그 글 50건 중 아토피 관련 글이 34%, 여드름 관련 글이 21%로 가장 많고, 미용 시술 관련 글은 5건뿐입니다.",
            citations=["self_claim", "vision", "blog"],
        ),
        DescriptionParagraph(
            text="실제 방문 후기에서도 '친절한 아토피 상담', '꼼꼼한 여드름 치료' 같은 키워드가 자주 등장합니다. 다만 사마귀 냉동치료기·점 제거 레이저 같은 시술 장비는 보유하고 있지 않은 것으로 보이므로, 미용 목적이라면 다른 병원을 권합니다.",
            citations=["reviews", "vision"],
        ),
    ],
    one_line_summary="일반 피부 진료 중심, 미용 시술은 거의 안 하는 동네 의원",
    generated_at=datetime.utcnow(),
    generator_model="anthropic.claude-sonnet-4-5-20250929-v1:0",
)
```

---

### 3. `embed_text`

텍스트를 벡터로 변환. **주로 디버깅·실험용** (벡터 구성 비교 실험 시 코사인 유사도 직접 측정 등). 운영 검색 경로는 KB가 내부에서 자동 임베딩하므로 이 함수를 호출하지 않는다.

```python
def embed_text(text: str) -> list[float]:
    ...
```

#### 동작
- Bedrock Titan Embed Text v2 직접 호출 (`bedrock-runtime:InvokeModel`)
- 반환 벡터 차원: 1024 (Titan v2 기본)

#### 의존성
- IAM: `bedrock:InvokeModel` (모델 ID: `amazon.titan-embed-text-v2:0`, 지원 계정 인스턴스 프로파일)

#### 예외
- `BedrockInvocationError`
- `TextTooLongError` — 8192 토큰 초과 시 (사전 청킹 필요)

---

### 4. `ingest_hospital`

병원 데이터를 Bedrock Knowledge Base에 적재. 새 병원 분류 후 또는 분류 변경 후 호출.

> **이전 `index_hospital` 함수 폐기**. KB 경유로 변경되면서 직접 PutVectors가 아니라 DataSource S3에 파일을 업로드하고 ingestion job을 트리거하는 방식으로 바뀜.

```python
def ingest_hospital(
    hospital_id: str,
    content_text: str,                      # KB가 임베딩할 본문 (AI 설명 본문 또는 정제된 원문)
    metadata: HospitalIngestMetadata,
    trigger_ingestion: bool = False,        # False면 파일만 업로드, True면 ingestion job 즉시 트리거
) -> None:
    ...

class HospitalIngestMetadata(BaseModel):
    standard_specialty: str
    primary_focus: list[str]
    sido: str
    sigungu: str
    confidence_score: int
    lat: float | None = None
    lng: float | None = None
    last_updated: str                       # ISO8601
```

#### 동작
1. `content_text`를 DataSource S3 버킷에 `{hospital_id}.txt`로 업로드
2. 같은 prefix에 `{hospital_id}.txt.metadata.json` 동봉 (KB metadata 사양: 필터 가능 타입은 string/number/boolean/list[string]만)
3. `trigger_ingestion=True`면 `bedrock-agent:StartIngestionJob` 호출. 배치 적재 시 False로 두고 마지막에 한 번만 트리거
4. KB가 자동으로: 청크 분할(KB 설정대로) → Titan v2 임베딩 → S3 Vectors 인덱스 적재

#### 의존성
- `KB_ID`: 환경 변수 (강사 제공 `GTBJ6HLFDK`)
- `KB_DATA_SOURCE_ID`: 환경 변수 (강사 제공 `PLC6QYALDU`)
- `KB_DATASOURCE_S3_BUCKET`, `KB_DATASOURCE_S3_PREFIX`: 환경 변수 (DataSource가 가리키는 S3 경로)
- IAM: `s3:PutObject` (DataSource 버킷), `bedrock-agent:StartIngestionJob`

#### 예외
- `KBIngestError` — S3 업로드 또는 ingestion job 트리거 실패

#### 메타데이터 키 (KB Retrieve 필터링용)

| 키 | 타입 | 비고 |
|---|---|---|
| `hospital_id` | string | 필터 가능 (역추적용 핵심) |
| `standard_specialty` | string | 필터 가능 |
| `primary_focus` | list[string] | 필터 가능 (`stringContains` 등) |
| `sido` | string | 필터 가능 |
| `sigungu` | string | 필터 가능 |
| `confidence_score` | number | 필터 가능 (`>=` 비교) |
| `lat` | number | 필터 가능 (bounding box용) |
| `lng` | number | 필터 가능 (bounding box용) |
| `last_updated` | string | 비필터 |

---

### 5. `retrieve_hospital`

자연어 쿼리로 유사 병원을 검색. **FE-BE `GET /api/search`의 자연어 모드가 내부에서 호출.**

> **이전 `search_similar` 함수 폐기**. KB Retrieve API 래퍼로 재설계. 검색 경로 이원화에 따라 **자연어 쿼리만 처리** — 단순 카테고리 탐색(`sigungu=강남구 & specialty=피부과` 전체 목록)은 BE가 DynamoDB GSI로 직접 처리하고 AI 모듈을 거치지 않는다.

```python
def retrieve_hospital(
    query: SearchQuery,
) -> list[SearchResult]:
    ...
```

> **호출당 LLM 0건.** KB Retrieve API가 내부에서 Titan v2 임베딩 1회 + 벡터 검색 1회를 수행. BE에서 DynamoDB 신뢰도 조회 1회 추가. Sonnet/Haiku 호출 0건. 응답 ~200~500ms (KB 오버헤드 포함), 검색당 비용 ~$0.00003. 자세한 건 `overview.md` "4-5. 검색 동작 원리" 참조.

#### 동작 흐름

**전제**: `query.query_text`는 필수 (KB Retrieve는 빈 쿼리 불가). 위치만 있는 단독 검색이나 메타 전체 목록 조회는 BE 측 DynamoDB GSI 경로로 처리되어 이 함수에 도달하지 않는다.

**자연어 단독 검색** (`query_text`만 있음):

1. `bedrock-agent-runtime:Retrieve` 호출 — KB가 내부에서 Titan 임베딩 + 벡터 검색
2. `retrievalConfiguration.vectorSearchConfiguration.filter`에 `sido`/`sigungu`/`specialty`/`min_confidence` 매핑
3. KB가 반환한 청크들의 `metadata.hospital_id`로 역추적
4. 같은 병원에서 여러 청크 매칭 시 최고 점수만 유지 (dedup by `hospital_id`)
5. DynamoDB에서 신뢰도 점수 조회 → KB score × 신뢰도 종합 정렬
6. 상위 N개 반환

**자연어 + 위치 복합 검색** (`query_text` + `lat`/`lng`):

1. KB Retrieve 호출 — `filter`에 `lat`/`lng` bounding box 범위 필터 추가 (`greaterThan` / `lessThan`)
2. KB 결과의 메타데이터 `lat`/`lng`로 EC2에서 haversine 공식으로 정확한 거리 재계산
3. `sort` 기준(`relevance` / `distance` / `confidence`)으로 정렬
4. 상위 N개 반환

> **자연어 의도 해석에 LLM을 안 쓰는 이유**: Titan v2가 의미 좌표 공간에서 *"M자 탈모 처방"* 과 *"안드로겐성 탈모 약물치료"* 가 가깝다는 걸 안다. 학습으로 동의어·문맥을 흡수한 상태라 LLM 의도 파싱 단계가 불필요. KB Retrieve가 이 임베딩을 내부에서 처리한다.

#### 의존성

- `KB_ID`: 환경 변수
- IAM: `bedrock-agent-runtime:Retrieve` (지원 계정 인스턴스 프로파일)
- DynamoDB 신뢰도 조회 (지원 계정)
- **LLM(Sonnet/Haiku) 호출 없음**

#### 예외
- `KBRetrieveError` — KB Retrieve API 호출 실패
- `InvalidQueryError` — `query_text`가 비었을 때 (KB 빈 쿼리 불가)

#### 반환 예시
```python
[
    SearchResult(
        hospital_id="h_abc123",
        similarity_score=0.87,
        distance_km=0.8,
        matched_focus=["모발·탈모"],
        query_interpretation="M자 탈모 처방 / 의원급",
    ),
    ...
]
```

---

### 6. `analyze_images`

이미지 URL 리스트를 받아 Bedrock Vision으로 분석. **PoC에서는 시연 10개 병원에만 호출** (트랙 C). `classify_hospital` 내부에서 `use_vision=True`로 호출되거나, 별도 batch에서 직접 호출.

OCR(이미지 안 글자 추출)도 Bedrock Vision 한 번 호출로 같이 처리한다 — 한국어 미지원으로 Textract는 사용하지 않는다.

```python
def analyze_images(
    image_urls: list[str],
) -> list[ImageAnalysisResult]:
    ...
```

#### 동작

1. 각 이미지를 S3에서 가져와서 개인 계정 Bedrock Claude Sonnet 4.5 Vision에 입력
2. Vision 응답에 OCR 텍스트 + 시각 해석(시술/기기 식별, 메인 강조 영역 등) 둘 다 포함
3. 결과를 `ImageAnalysisResult` 리스트로 반환

#### 의존성

- `BEDROCK_VISION_MODEL_ID` (개인 계정, `anthropic.claude-sonnet-4-5-20250929-v1:0`)
- 개인 계정 자격증명 (`AI_AWS_*` 환경변수)
- IAM: 개인 계정 `bedrock:InvokeModel` / 지원 계정 `s3:GetObject`

#### 예외
- `BedrockInvocationError`
- `ImageNotFoundError` — S3 URL 무효

---

### 7. `recompute_confidence`

피드백 누적 시 신뢰도 재계산. EventBridge 스케줄 또는 피드백 N건 누적 시 트리거.

```python
def recompute_confidence(
    hospital_id: str,
    recent_feedback: list[FeedbackEntry],
) -> Confidence:
    ...
```

#### 동작
1. 기존 4 시그널 점수 로드 (DynamoDB)
2. 최근 피드백 비율 계산 (agree vs disagree)
3. 가중치 조정하여 신뢰도 재계산
4. 부정 피드백 임계치 초과 시 인간 검수자 큐로 자동 enqueue
5. 변경된 `Confidence` 반환 (DB 업데이트는 BE 측 책임)

#### 의존성
- DynamoDB 조회 (직접 또는 BE 통해)

#### 예외
- `InsufficientFeedbackError` — 피드백이 너무 적어 통계적 의미 없음 (예: 3건 미만)

---

### 8. `extract_services_and_doctors`

크롤링 데이터에서 상세 페이지 영역 ②③에 들어갈 구조화된 정보를 추출. **상세 페이지의 진료 항목·다루지 않는 분야·의료기기·의료진 영역을 채우는 함수.**

```python
def extract_services_and_doctors(
    crawl_data: CrawlData,
    classification: Classification,
    vision_results: list[ImageAnalysisResult],
) -> ServicesAndDoctors:
    ...

class ServicesAndDoctors(BaseModel):
    services: list[Service]                   # 다루는 진료 항목
    excluded_services: list[ExcludedService]  # 다루지 않는 분야
    equipment: list[Equipment]                # 보유 의료기기
    prices: list[PriceItem]                   # 비급여 가격 (있는 경우만)
    doctors: list[Doctor]                     # 의료진
```

#### 동작 흐름
1. **다루는 진료 항목**: 사이트 텍스트·블로그·후기 키워드에서 LLM이 진료 항목 리스트 추출
2. **다루지 않는 분야**: 표준 진료과목 기본 항목 목록과 비교 → 자칭·블로그·Vision 어디에도 등장하지 않으면 "다루지 않음" 판정. 단, 신뢰도 70% 이상인 부재만 표시 (확신 없으면 표시 안 함)
3. **의료기기**: Vision 결과 + 심평원 공공 신고 데이터 병합. Vision이 식별한 장비 + 공공 신고에 등록된 장비를 합집합으로 표시
4. **비급여 가격**: 사이트의 비급여 가격 페이지 크롤링 결과 (있는 경우만)
5. **의료진**: 사이트 의료진 페이지 + 심평원 전문의 자격 데이터 결합. 의사별 세부 전공·경력 정리

#### 의존성
- `BEDROCK_LLM_MODEL_ID`
- IAM: `bedrock:InvokeModel`

#### 예외
- `BedrockInvocationError`
- `InsufficientDataError`

---

### 9. `find_related_hospitals`

상세 페이지 영역 ⑧을 채우는 함수. 두 종류의 추천:
- **같은 주력**: 같은 동네에서 같은 세부 주력을 다루는 병원
- **빈자리 보완**: 현재 병원이 다루지 않는 분야의 대안 병원

```python
def find_related_hospitals(
    hospital_id: str,
    location: Location,
    primary_focus: list[str],
    excluded_services: list[ExcludedService],
    limit: int = 5,
) -> list[RelatedHospital]:
    ...

class RelatedHospital(BaseModel):
    hospital_id: str
    name: str
    primary_focus: list[str]
    similarity_score: float
    recommendation_type: Literal["same_focus", "fills_gap"]
    distance_km: float | None
```

#### 동작 흐름
1. **same_focus 추천**: 현재 병원 설명 텍스트를 쿼리로 KB Retrieve 호출 → 상위 N개 + 같은 시군구 필터 (`bedrock-agent-runtime:Retrieve`)
2. **fills_gap 추천**: `excluded_services` 각 항목을 쿼리 텍스트로 KB Retrieve + `sigungu` 필터로 동네 후보 검색
3. 거리 계산 (`location` 위경도 기반 haversine)
4. 두 종류를 섞어서 반환 (보통 same_focus 3개 + fills_gap 2개)

#### 의존성
- IAM: `bedrock-agent-runtime:Retrieve`
- DynamoDB 조회

#### 예외
- `KBRetrieveError`

---

### 10. `aggregate_feedback_stats`

상세 페이지 영역 ⑥의 피드백 누적 통계를 계산. DynamoDB의 Feedback 테이블 집계.

```python
def aggregate_feedback_stats(
    hospital_id: str,
) -> FeedbackStats:
    ...

class FeedbackStats(BaseModel):
    total_count: int
    agree_count: int
    disagree_count: int
    agree_ratio: float
    last_feedback_at: datetime | None
```

#### 동작 흐름
1. DynamoDB Feedback 테이블에서 `hospital_id` 기준 모든 피드백 조회
2. `verdict` 별 카운트 집계
3. agree/disagree 비율 계산
4. 가장 최근 피드백 시각 반환

#### 비고
- 단순 집계라 캐싱 가능. 일정 시간(예: 1시간) 캐싱 후 재계산
- 평가용 PoC에서는 매 요청마다 직접 집계해도 무방 (피드백 수가 적음)

#### 의존성
- DynamoDB 조회

---

## 환경 변수 (AI 모듈)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `AWS_REGION` | `us-east-1` | 공통 리전 |
| `BEDROCK_LLM_MODEL_ID` | `anthropic.claude-haiku-4-5-...` | 트랙 B용 LLM (지원 계정 Haiku/Nova 한정) |
| `BEDROCK_VISION_MODEL_ID` | `anthropic.claude-sonnet-4-5-20250929-v1:0` | 트랙 C용 Vision (개인 계정) |
| `BEDROCK_EMBED_MODEL_ID` | `amazon.titan-embed-text-v2:0` | `embed_text` 직접 호출용 임베딩 모델 (KB는 자체적으로 동일 모델 사용) |
| `KB_ID` | `GTBJ6HLFDK` | 강사 제공 Bedrock Knowledge Base ID (`kmuproj-team-03`, 지원 계정) |
| `KB_DATA_SOURCE_ID` | `PLC6QYALDU` | KB DataSource ID (`main-datasource`) |
| `KB_DATASOURCE_S3_BUCKET` | (강사 제공) | DataSource가 가리키는 S3 버킷 — `get-data-source`로 확인 후 적기 |
| `KB_DATASOURCE_S3_PREFIX` | (강사 제공) | DataSource S3 prefix |
| `AI_AWS_ACCESS_KEY_ID` / `AI_AWS_SECRET_ACCESS_KEY` | — | 개인 계정 Sonnet 호출용 (트랙 C 시연 시) |
| `MAX_VISION_IMAGES` | `10` | 한 번 분류 시 처리할 최대 이미지 수 |
| `MAX_LLM_DEMO_HOSPITALS` | `10` | 트랙 B·C 시연 대상 병원 수 (지원 계정 한도) |
| `CONFIDENCE_THRESHOLD_HIGH` | `95` | "확실" 등급 임계치 |
| `CONFIDENCE_THRESHOLD_LOW` | `70` | "정보 부족" 등급 임계치 |

> Bedrock KB(Retrieve/StartIngestionJob) · Titan Embed · Haiku/Nova 는 **지원 계정**(us-east-1) 자원으로 EC2 인스턴스
> 프로파일로 자동 인증된다. **Sonnet 4.5(Vision 시연)만 개인 계정** 자격증명으로 boto3
> 클라이언트를 따로 생성한다. 자세한 건 `../CLAUDE.md`의 "AWS 계정·인프라 구조" 참조.

---

## 분류 알고리즘 의사 코드 (참고)

```python
def classify_hospital(crawl_data: CrawlData, use_vision: bool = True) -> Classification:
    # 1. 자칭 컨셉 추출
    self_claim_result = extract_self_claim_with_llm(crawl_data.pages)

    # 2. Vision 분석
    vision_result = (
        analyze_images([img.url for img in crawl_data.images])
        if use_vision else None
    )

    # 3. 블로그 키워드 빈도
    blog_result = analyze_blog_topics(
        [p for p in crawl_data.pages if p.page_type == "blog"]
    )

    # 4. 후기 키워드 분석 (수집된 후기가 있을 때만)
    review_result = analyze_review_keywords(crawl_data.hospital_id)

    # 5. 4 시그널 교차 검증
    primary_focus, signal_scores = cross_validate_signals(
        self_claim_result, vision_result, blog_result, review_result
    )

    # 6. 자칭 도배 페널티
    if is_keyword_spamming(self_claim_result, vision_result, blog_result):
        signal_scores = apply_spamming_penalty(signal_scores)

    # 7. 신뢰도 점수
    confidence = compute_confidence(signal_scores)

    return Classification(
        hospital_id=crawl_data.hospital_id,
        standard_specialty=infer_specialty(crawl_data),
        primary_focus=primary_focus,
        confidence=confidence,
        detailed_signals=build_detailed_signals(
            self_claim_result, vision_result, blog_result, review_result
        ),
        classified_at=datetime.utcnow(),
        classifier_version="v1.0",
    )
```

---

## BE 호출 패턴 예시

### 새 병원 등록 시 (배치)

```python
# be/handlers/ingest_hospital.py
from ai import (
    classify_hospital,
    generate_description,
    extract_services_and_doctors,
    find_related_hospitals,
    ingest_hospital,
)
from shared.models import CrawlData, HospitalIngestMetadata

def ingest_hospital_pipeline(hospital_id: str):
    # 1. 크롤링 데이터 로드 (김경재 모듈)
    crawl_data: CrawlData = load_crawl_data(hospital_id)
    hospital_meta = load_hospital_meta(hospital_id)

    # 2. AI 분류 (영역 ② 일부, ④)
    classification = classify_hospital(crawl_data)

    # 3. 진료 항목·의료기기·의료진 추출 (영역 ②③)
    services_and_doctors = extract_services_and_doctors(
        crawl_data=crawl_data,
        classification=classification,
        vision_results=classification.detailed_signals.vision,
    )

    # 4. AI 통합 상세 설명 생성 ⭐ 본 서비스의 핵심 결과물 (영역 ①)
    description = generate_description(
        classification=classification,
        detailed_signals=classification.detailed_signals,
        hospital_meta=hospital_meta,
    )

    # 5. 관련 병원 추천 (영역 ⑧)
    #    같은 주력 + 빈자리 보완 병원 검색
    related = find_related_hospitals(
        hospital_id=hospital_id,
        location=hospital_meta.location,
        primary_focus=classification.primary_focus,
        excluded_services=services_and_doctors.excluded_services,
    )

    # 6. DynamoDB 적재
    save_classification(classification)
    save_description(description)
    save_services_and_doctors(services_and_doctors)
    save_related_hospitals(hospital_id, related)

    # 7. KB ingestion (DataSource S3 업로드 — 배치 적재 시 trigger_ingestion=False, 마지막에 한 번만 True)
    #    임베딩 대상 본문은 AI 상세 설명 (검색 정확도가 가장 높음)
    embedding_text = "\n".join(p.text for p in description.paragraphs)
    ingest_hospital(
        hospital_id=hospital_id,
        content_text=embedding_text,
        metadata=HospitalIngestMetadata(
            standard_specialty=classification.standard_specialty,
            primary_focus=classification.primary_focus,
            sido=hospital_meta.location.sido,
            sigungu=hospital_meta.location.sigungu,
            confidence_score=classification.confidence.score,
            lat=hospital_meta.location.lat,
            lng=hospital_meta.location.lng,
            last_updated=classification.classified_at.isoformat(),
        ),
        trigger_ingestion=False,  # 배치 후 별도로 start_ingestion_job 한 번 호출
    )

    return {"status": "ingested", "hospital_id": hospital_id}
```

### 상세 페이지 조회 시

```python
# be/handlers/get_hospital_detail.py
from ai import aggregate_feedback_stats

def handle_get_detail(hospital_id: str):
    # 9개 영역에 해당하는 데이터를 DynamoDB에서 조회
    classification = load_classification(hospital_id)
    description = load_description(hospital_id)
    services_and_doctors = load_services_and_doctors(hospital_id)
    hospital_meta = load_hospital_meta(hospital_id)
    related = load_related_hospitals(hospital_id)
    recent_changes = load_recent_changes(hospital_id, limit=2)

    # 영역 ⑥ 피드백 통계는 실시간 집계 (또는 캐싱)
    feedback_stats = aggregate_feedback_stats(hospital_id)

    # FE-BE API 응답 형태로 조립
    return build_hospital_detail_response(
        classification=classification,
        description=description,
        services_and_doctors=services_and_doctors,
        hospital_meta=hospital_meta,
        related_hospitals=related,
        recent_changes=recent_changes,
        feedback_stats=feedback_stats,
    )
```

### 검색 시

```python
# be/handlers/search.py
from ai import retrieve_hospital
from shared.models import SearchQuery

def handle_search(query_params):
    # 검색 경로 이원화:
    #   - query_text 있으면 → AI 자연어 검색 (KB Retrieve)
    #   - query_text 없고 메타 필터만 있으면 → BE DynamoDB GSI 직접 조회 (AI 미경유)
    if not query_params.get("q"):
        return handle_category_browse(query_params)  # be/handlers/category.py — DynamoDB GSI

    query = SearchQuery(
        query_text=query_params["q"],
        sido=query_params.get("sido"),
        sigungu=query_params.get("sigungu"),
        specialty=query_params.get("specialty"),
        min_confidence=int(query_params.get("min_confidence", 70)),
        limit=int(query_params.get("limit", 20)),
    )

    # 1. AI 모듈로 자연어 검색 (KB Retrieve 경유)
    ai_results = retrieve_hospital(query)

    # 2. DynamoDB에서 상세 정보 조인
    hospitals = batch_get_hospitals([r.hospital_id for r in ai_results])

    # 3. FE에 반환할 형태로 변환
    return [build_response_hospital(h, r) for h, r in zip(hospitals, ai_results)]
```

### 피드백 처리 시

```python
# be/handlers/feedback.py
from ai import recompute_confidence

def handle_feedback(feedback: FeedbackEntry):
    # 1. 피드백 저장
    save_feedback(feedback)

    # 2. 임계치 이상 누적되면 신뢰도 재계산 트리거
    recent_feedback = get_recent_feedback(feedback.hospital_id)
    if should_recompute(recent_feedback):
        new_confidence = recompute_confidence(feedback.hospital_id, recent_feedback)
        update_confidence(feedback.hospital_id, new_confidence)
```

---

## 테스트 가이드

### AI 모듈 단독 테스트

```python
# tests/test_classify.py
from ai import classify_hospital
from shared.models import CrawlData

def test_classify_with_sample_data():
    crawl_data = CrawlData.model_validate_json(
        open("tests/fixtures/sample_hospital.json").read()
    )
    result = classify_hospital(crawl_data, use_vision=False)
    assert result.confidence.level in ["확실", "추정", "정보 부족"]
    assert len(result.primary_focus) > 0
```

### Bedrock 호출 모킹

```python
# 실제 Bedrock 호출 없이 테스트
from unittest.mock import patch

@patch("ai.bedrock_client.invoke_model")
def test_classify_mocked(mock_invoke):
    mock_invoke.return_value = {"body": ...}
    ...
```

---

## 비용 관리 가이드

PoC는 **3트랙 분리**로 비용 통제. 너희 카드 부담 거의 0.

- **트랙 A (룰 기반, 서울 1만)**: 비용 0 (LLM 미사용)
- **트랙 B (LLM 시연 10개)**: 지원 계정 Haiku/Nova — 강사 자원, 너희 카드 부담 0
- **트랙 C (Vision 시연 10개)**: 개인 계정 Sonnet — 시행착오 3회 포함 **~$1.3**
- **임베딩 (Titan v2, 1만 전체)**: 지원 계정 — 부담 0

**PoC 총 비용 추정**: 개인 카드 ~$1~5 / 지원 계정 자원 한도 내 무료.

**사업화 시 비용 (참고)** — `docs/overview.md` "운영 비용 구조" 참조. 핵심 요지:

- 룰 기반은 전국 7만 병원 확장에도 비용 0
- LLM 사용 영역도 **변경 감지(hash diff) 기반 부분 재처리**로 전수 재처리 대비 80~90% 절감
- 전국 풀커버 운영 시 월 ~$700 수준 (변경분 LLM 재처리만)