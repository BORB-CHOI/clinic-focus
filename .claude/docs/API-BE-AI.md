# API 명세: BE ↔ AI

> 김경재(백엔드) ↔ 최비성(AI/RAG) 간 인터페이스 정의

---

## 호출 방식

**BE와 AI는 같은 EC2 인스턴스의 단일 Python 프로세스에서 돌아간다.** 모노레포의 `be/` `ai/` `shared/` 가 한 프로세스에 함께 로드되고, BE는 AI 함수를 Python 패키지 import로 직접 호출.

```python
# be/handlers/index_hospital.py
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
    similarity_score: float | None      # 자연어 검색 시 S3 Vectors 유사도. 없으면 None
    distance_km: float | None           # 위치 검색 시 거리. 없으면 None
    matched_focus: list[str]
    query_interpretation: str | None    # LLM이 해석한 자연어 쿼리 의도
```

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
1. `crawl_data.pages`에서 자칭 컨셉을 LLM 프롬프트로 추출 (Bedrock Claude Sonnet 4.5)
2. `crawl_data.images`를 Bedrock Vision으로 분석 (use_vision=False면 생략)
3. 블로그 페이지의 키워드 빈도 분석
4. 후기 키워드 빈도 분석 (수집된 후기가 있을 때)
5. 4 시그널 교차 검증 → 신뢰도 점수 계산
6. 자칭 도배 페널티 적용
7. `Classification` 반환

#### 의존성
- `BEDROCK_MODEL_ID`: 환경 변수, 기본 `anthropic.claude-sonnet-4-5-20250929-v1:0`
- `AWS_REGION`: 기본 `ap-northeast-2`
- IAM 권한: `bedrock:InvokeModel`, `textract:AnalyzeDocument`

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

### 2. `generate_description` ⭐ **본 서비스의 핵심 함수**

분류 결과 + 4 시그널 원본 데이터를 받아 자연어 통합 상세 설명을 생성. **FE-BE `GET /api/hospitals/{id}` 응답의 `ai_description` 필드가 이 함수의 결과.**

```python
def generate_description(
    classification: Classification,
    detailed_signals: DetailedSignals,
    hospital_meta: HospitalMeta,  # 이름·주소 등 기본 정보
) -> HospitalDescription:
    ...
```

#### 동작 흐름
1. 분류 결과·신뢰도·4 시그널 원본 데이터를 구조화된 컨텍스트로 정리
2. Bedrock Claude Sonnet 4.5에 전용 프롬프트 + 컨텍스트 입력
3. 프롬프트는 다음을 강제:
   - **주체 명시 표현 의무** — "이 병원이 자기 사이트에서 ~를 메인으로 표시함" 형태만 허용
   - **출처 시그널 태그 의무** — 각 단락의 주장이 어떤 시그널에서 나왔는지 `citations` 목록 자동 첨부
   - **평가·추천 표현 금지** — "잘 본다" "추천한다" 같은 의료광고 회색지대 표현 사용 금지
   - **약점·주의사항도 포함** — 보유하지 않은 장비, 다루지 않는 분야도 명시
4. 출력은 구조화된 JSON으로 받아 `HospitalDescription`으로 파싱
5. 1문장 `one_line_summary`도 별도로 생성 (검색 카드용)

#### 의존성
- `BEDROCK_LLM_MODEL_ID`
- IAM: `bedrock:InvokeModel`
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

텍스트를 벡터로 변환. S3 Vectors 적재용·쿼리용 양쪽에서 사용.

```python
def embed_text(text: str) -> list[float]:
    ...
```

#### 동작
- Bedrock Titan Embed Text v2 호출
- 반환 벡터 차원: 1024 (Titan v2 기본)

#### 의존성
- IAM: `bedrock:InvokeModel` (모델 ID: `amazon.titan-embed-text-v2:0`)

#### 예외
- `BedrockInvocationError`
- `TextTooLongError` — 8192 토큰 초과 시 (사전 청킹 필요)

---

### 4. `index_hospital`

분류 결과 + AI 상세 설명을 S3 Vectors에 적재. 새 병원 분류 후 또는 분류 변경 후 호출.

```python
def index_hospital(
    hospital_id: str,
    classification: Classification,
    description_text: str,
    sido: str,
    sigungu: str,
    lat: float | None = None,
    lng: float | None = None,
) -> None:
    ...
```

#### 동작
1. `description_text`를 `embed_text`로 임베딩
2. S3 Vectors `PutVectors` API로 적재
3. 메타데이터로 `standard_specialty`, `primary_focus`, `sido`, `sigungu`, `confidence_score`, `lat`, `lng` 첨부 (쿼리 시 필터링용)

#### 의존성
- `S3_VECTOR_BUCKET`: 환경 변수
- `S3_VECTOR_INDEX`: 환경 변수
- IAM: `s3vectors:PutVectors`

#### 메타데이터 키 (S3 Vectors 필터링용)

| 키 | 타입 | 비고 |
|---|---|---|
| `standard_specialty` | string | 필터 가능 |
| `primary_focus` | list[string] | 필터 가능 |
| `sido` | string | 필터 가능 |
| `sigungu` | string | 필터 가능 |
| `confidence_score` | number | 필터 가능 (`>=` 비교) |
| `lat` | number | 필터 가능 (bounding box 범위 필터) |
| `lng` | number | 필터 가능 (bounding box 범위 필터) |
| `last_updated` | string | 비필터 |

---

### 5. `search_similar`

자연어 쿼리로 유사 병원을 검색. **FE-BE `GET /api/search`가 내부에서 호출.**

```python
def search_similar(
    query: SearchQuery,
) -> list[SearchResult]:
    ...
```

#### 동작 흐름

검색 모드를 입력 파라미터에 따라 분기:

**자연어 단독 검색** (`query_text`만 있음):
1. `query.query_text`를 LLM으로 해석 → 검색 의도 추출
2. 의도를 임베딩 → S3 Vectors `QueryVectors` 호출
3. 메타데이터 필터링 (`sido`, `sigungu`, `specialty`, `min_confidence`)
4. 상위 N개 반환

**위치 단독 검색** (`lat`/`lng`만 있음):
1. 입력 위경도 + `radius_km`로 bounding box 계산 (예: 반경 3km → 위경도 ±0.027°)
2. S3 Vectors 메타데이터 필터로 bounding box 내 후보 추출 (벡터 검색 없이 dummy 임베딩 + 메타 필터만)
3. Lambda에서 haversine 공식으로 정확한 거리 재계산 → `radius_km` 내 필터링
4. `sort` 기준(`distance` 기본 / `confidence`)으로 정렬

**복합 검색** (`query_text` + `lat`/`lng`):
1. 자연어 의미 검색으로 유사도 상위 N×3개 추출
2. 그 중 `radius_km` 내 후보만 haversine 필터링
3. `sort` 기준으로 정렬(`relevance` 기본 / `distance` / `confidence`)
4. 상위 N개 반환

#### 의존성
- Bedrock (자연어 검색 시 의도 해석 + 임베딩)
- S3 Vectors (QueryVectors, 메타데이터 lat/lng 필터)
- IAM: `bedrock:InvokeModel`, `s3vectors:QueryVectors`

#### 예외
- `BedrockInvocationError`
- `S3VectorsError`
- `InvalidQueryError` — `query_text`와 `lat`/`lng` 둘 다 없을 때

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

이미지 URL 리스트를 받아 Vision + OCR로 분석. `classify_hospital` 내부에서 사용되거나, 별도로 batch 처리할 때도 호출.

```python
def analyze_images(
    image_urls: list[str],
    extract_text: bool = False,  # True면 Textract OCR 같이 수행
) -> list[ImageAnalysisResult]:
    ...
```

#### 동작
1. 각 이미지를 S3에서 가져와서 Bedrock Vision에 입력
2. `extract_text=True`인 경우 Textract로 OCR 텍스트도 추출
3. 결과를 `ImageAnalysisResult` 리스트로 반환

#### 의존성
- IAM: `bedrock:InvokeModel`, `textract:AnalyzeDocument`, `s3:GetObject`

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
1. **same_focus 추천**: 현재 병원의 분류 설명을 S3 Vectors에서 유사도 검색 → 상위 N개 + 같은 시군구 필터
2. **fills_gap 추천**: `excluded_services` 각각에 대해 "그 서비스를 다루는 동네 병원"을 S3 Vectors + 메타데이터 필터로 검색
3. 거리 계산 (`location` 위경도 기반 haversine)
4. 두 종류를 섞어서 반환 (보통 same_focus 3개 + fills_gap 2개)

#### 의존성
- IAM: `s3vectors:QueryVectors`
- DynamoDB 조회

#### 예외
- `S3VectorsError`

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
| `AWS_REGION` | `us-east-1` | Bedrock·S3 Vectors 리전 (개인 계정) |
| `BEDROCK_LLM_MODEL_ID` | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | LLM·Vision (US 인퍼런스 프로파일) |
| `BEDROCK_EMBED_MODEL_ID` | `amazon.titan-embed-text-v2:0` | 임베딩 모델 |
| `S3_VECTOR_BUCKET` | 환경별 | 벡터 버킷 이름 |
| `S3_VECTOR_INDEX` | `hospital-index` | 벡터 인덱스 이름 |
| `MAX_VISION_IMAGES` | `10` | 한 번 분류 시 처리할 최대 이미지 수 |
| `CONFIDENCE_THRESHOLD_HIGH` | `95` | "확실" 등급 임계치 |
| `CONFIDENCE_THRESHOLD_LOW` | `70` | "정보 부족" 등급 임계치 |

> AI 모듈의 Bedrock·S3 Vectors·Textract는 **개인 계정**에서 운영된다. EC2 코드는 이
> 클라이언트들을 개인 계정 자격증명으로 생성하고, 지원 계정 서비스(DynamoDB)는 EC2
> 인스턴스 프로파일을 쓴다.

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
# be/handlers/index_hospital.py
from ai import (
    classify_hospital,
    generate_description,
    extract_services_and_doctors,
    find_related_hospitals,
    index_hospital,
)
from shared.models import CrawlData

def index_hospital_pipeline(hospital_id: str):
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

    # 7. S3 Vectors 인덱싱
    #    벡터 임베딩 대상은 AI 상세 설명 본문 (검색 정확도가 가장 높음)
    embedding_text = "\n".join(p.text for p in description.paragraphs)
    index_hospital(
        hospital_id,
        classification,
        embedding_text,
        sido=hospital_meta.location.sido,
        sigungu=hospital_meta.location.sigungu,
        lat=hospital_meta.location.lat,
        lng=hospital_meta.location.lng,
    )

    return {"status": "indexed", "hospital_id": hospital_id}
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
from ai import search_similar
from shared.models import SearchQuery

def handle_search(query_params):
    query = SearchQuery(
        query_text=query_params["q"],
        sido=query_params.get("sido"),
        sigungu=query_params.get("sigungu"),
        specialty=query_params.get("specialty"),
        min_confidence=int(query_params.get("min_confidence", 70)),
        limit=int(query_params.get("limit", 20)),
    )

    # 1. AI 모듈로 유사도 검색
    ai_results = search_similar(query)

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

- **분류 1회당 예상 비용** (PoC 기준)
  - Bedrock Claude Sonnet 4.5 (텍스트 + Vision): ~$0.05~0.20/병원
  - Titan Embed Text v2: ~$0.0001/병원
  - Textract: ~$0.0015/페이지 (필요한 경우만)
- **1만 병원 PoC 총 비용**: ~$500~2,000 (변동 큼, ⚠️ 추정)
- **비용 절감 팁**
  - `use_vision=False`로 일부 케이스 처리
  - 자칭 컨셉이 매우 명확한 경우 Vision 생략
  - Haiku 모델로 1차 분류, Sonnet으로 검증하는 cascading