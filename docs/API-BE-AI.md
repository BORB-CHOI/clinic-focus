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

### `NaverPlace` — 네이버 플레이스 장소 정보
```python
class NaverPlace(BaseModel):
    place_id: str                        # 네이버 플레이스 고유 ID
    name: str
    operating_hours: str | None          # "월~금 09:00~18:00" 형태 자유 문자열
    phone: str | None
    visitor_count: int | None            # 누적 방문자 수 (비공개 시 None)
    keyword_stats: dict[str, int]        # {키워드: 언급 횟수}, 예: {"친절": 42, "청결": 31}
    photo_urls: list[str]                # 대표 사진 URL 목록 (최대 10개)
```

### `NaverBlogPost` — 네이버 블로그 포스트 1건
```python
class NaverBlogPost(BaseModel):
    url: str
    title: str
    text_excerpt: str                    # 본문 앞 500자 (전문 저장은 DDB raw, 임베딩은 키워드만)
    published_at: datetime
    topic: str | None                    # LLM 또는 TF-IDF 분류 주제 (예: "아토피", "여드름")
```

### `KakaoPlace` — 카카오 로컬 API 장소 정보
```python
class KakaoPlace(BaseModel):
    place_id: str                        # 카카오 place_id
    name: str
    category_group_code: str             # 병원은 "HP8" 고정
    review_count: int | None             # 카카오맵 리뷰 수 (공개된 경우)
    review_keywords: dict[str, int]      # {키워드: 언급 횟수} — 개별 후기 본문 미저장 (§56③)
```

### `GoogleReviews` — Google Places 리뷰 집계
```python
class GoogleReviews(BaseModel):
    place_id: str                        # Google place_id
    rating: float | None                 # 평균 별점 (1~5)
    user_ratings_total: int | None       # 총 리뷰 수
    reviews_keywords: dict[str, int]     # {키워드: 언급 횟수}
    # 개별 리뷰 본문은 저장하지 않는다 — 의료법 §56③ 광고성 후기 금지
    # Google Places API 무료 tier 는 reviews 필드를 최대 5건만 반환하므로
    # 키워드 추출 후 즉시 폐기
```

> **외부 시그널은 묶음 모델 없이 개별 인자로 전달한다.** `classify_hospital` /
> `build_signal_chunks` 가 `kakao_place`·`kakao_reviews`·`kakao_blog`·`naver_reviews`·
> `naver_blog`·`google_reviews` 를 키워드 인자로 받고, BE 핸들러는
> `DynamoAdapter.load_external_signals()` 가 돌려준 dict 를 `**` 로 전개한다.
> (옛 `ExternalSignalBundle` 컨테이너는 미사용이라 제거됨 — 2026-05-28.)

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
    """4 시그널 각각의 신뢰도 기여 점수 (0~100).

    - 해당 시그널 데이터가 없으면 None (가중치 재정규화 대상).
    - 자칭 도배 페널티: self_claim 이 높고 vision·blog·reviews 가 모두 낮거나 None 이면
      confidence.score 에 강제 감점 (-10 ~ -30 포인트). 자칭 내용이 타 시그널로
      검증되지 않은 케이스를 과신하는 것을 방지.
    """
    self_claim: float          # 자칭 점수 0~100 (항상 존재)
    vision: float | None       # Vision 시그널 없으면 None (use_vision=False 또는 이미지 없음)
    blog: float | None         # 네이버 블로그 시그널 없으면 None
    reviews: float | None      # 네이버+카카오+구글 후기 합산 점수. 3개 소스 중 1개 이상 있으면 산출

class DetailedSignals(BaseModel):
    """4 시그널 원본 데이터.

    각 sub-block 이 None 이면 해당 시그널은 채워지지 않은 것.
    None 인 시그널은 SignalContributions 에서도 None 으로 처리되며
    confidence 산출 시 해당 가중치를 나머지 시그널에 재분배.
    """
    self_claim: SelfClaimSignal          # 항상 존재 (자체 사이트 크롤링 결과)
    vision: VisionSignal | None          # use_vision=False 또는 이미지 0개 시 None
    blog: BlogSignal | None              # 네이버 블로그 크롤링 미완료 시 None
    reviews: ReviewSignal | None         # 외부 후기 소스 크롤링 미완료 시 None
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

크롤링된 사이트 데이터와 외부 3개 소스 시그널을 받아 분류 결과 + 신뢰도 + 시그널 기여도를 반환. **PoC의 핵심 함수.**

> **실구현 시그니처** — 외부 시그널은 **시그널별 개별 키워드 인자**로 받는다 (번들 1개 아님).
> `build_signal_chunks(...)` 와 시그니처를 일치시켜, 핸들러가 `db.load_external_signals()` 가
> 돌려준 dict 를 `**external` 로 두 함수에 그대로 전개한다. 4 시그널 교차검증이 시그널 종류별
> 독립 출처를 다루는 철학(벡터도 시그널별 청크로 분리)과 일관된다.

```python
def classify_hospital(
    crawl_data: CrawlData,
    use_vision: bool = True,
    use_llm: bool = True,
    *,
    kakao_place: "KakaoPlace | dict | None" = None,
    kakao_reviews: "KakaoReviews | dict | None" = None,
    kakao_blog: "KakaoBlog | dict | None" = None,
    naver_reviews: "NaverPlace | dict | None" = None,
    google_reviews: "GoogleReviews | dict | None" = None,
) -> Classification:
    ...
```

**파라미터 의미**:
- 외부 시그널 인자(`kakao_place`·`kakao_reviews`·`kakao_blog`·`naver_reviews`·`google_reviews`) — 각각 dict 또는 대응 Pydantic 모델 둘 다 수용. 미적재면 None → self_claim 등 가용 시그널만으로 분류. `kakao_place.tags` 는 자칭 보강에, 후기 3종은 후기 시그널에 흩어져 들어간다.
- `use_llm=False` — 트랙 A 룰 기반(Bedrock 0회, 1만 풀커버). True 면 트랙 B/C(LLM/Vision 시연 10개).
- `use_vision=False` — 자칭 명확한 케이스(비용 절감). `use_llm=False` 면 이 값과 무관하게 Vision 생략.

#### 동작 흐름

PoC에서는 **3트랙으로 분기**한다 (자세한 건 `../ai/CLAUDE.md` "AI 트랙 3트랙 구조" 참조):

- **트랙 A (룰 기반, 서울 1만 풀커버)**: 정제된 텍스트의 키워드 빈도 + 페이지 타입별 강조도로 자칭 컨셉 추출. LLM 미사용. `use_llm=False` 분기.
- **트랙 B (LLM 시연, 10개)**: 지원 계정 Haiku/Nova로 자칭 컨셉 추출 — 룰 결과보다 정밀.
- **트랙 C (Vision 시연, 10개)**: 개인 계정 Sonnet 4.6 Vision (서울 리전, Global cross-region inference profile)으로 이미지 분석. `use_vision=True` 분기.

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
- 트랙 C: `BEDROCK_VISION_MODEL_ID` (개인 계정, `global.anthropic.claude-sonnet-4-6` — Global cross-region inference profile, foundation-model 직접 호출 불가), 개인 계정 자격증명 (`AI_AWS_*` 환경변수, `AI_AWS_REGION=ap-northeast-2`)
- `AWS_REGION`: 지원 계정 기본 `us-east-1` (개인 계정은 `AI_AWS_REGION=ap-northeast-2`)
- IAM 권한: 지원 계정 `bedrock:InvokeModel`, 개인 계정 `bedrock:InvokeModel`

#### 예외
- `BedrockInvocationError` — Bedrock 호출 실패
- `InsufficientDataError` — 크롤링 데이터가 너무 빈약 (페이지 0개, 또는 전부 빈 텍스트)

#### 신뢰도 계산 — 옛 약점과 해소 (2026-05-28)

2026-05-26 강남구 14개 병원 e2e 검증(PR [#25](https://github.com/BORB-CHOI/clinic-focus/pull/25), scratch 우회로 — 제거됨)에서 확인된 신뢰도 계산 버그. 룰 단독 경로는 이후 `_cap_rule_only_confidence`(70 상한) + 빈 페이지 `InsufficientDataError` 로 일부 완화됨 — 아래 항목 전수 적용 여부는 재검증 필요.

- **`5. 강남우태하피부과의원`** — `primary_focus=[]`(빈 리스트)임에도 `confidence.score=100` 출력. 자칭 컨셉을 추출하지 못한 데이터 부족 상황인데 신뢰도가 최고값으로 잡힘.
- **`12. 개포센트럴이비인후과의원`** — 병원 이름에 "이비인후과"가 명시돼 있음에도 피부과로 오분류, `primary_focus=[]`, `confidence.score=100`. 크롤 성공 1페이지·이미지 0개인 데이터 부족 케이스임에도 confidence가 낮아지지 않음.

두 케이스 모두 `_cross_validate_signals` 가 **focus 후보를 하나도 못 만들 때 전체 가중치(합≈1.0)를 기여도로 반환** → `_compute_confidence` 에서 score=100 "확실" 이 나오던 버그. 아래로 해소됨(2026-05-28):

- ✅ **focus 후보 0 → 기여도 0** (`_cross_validate_signals`). `primary_focus=[]` 이면 score≈0 → `level="정보 부족"`. 회귀 테스트 `TestEmptyFocusConfidence` 추가
- ✅ **빈 페이지 → `InsufficientDataError`** (`classify_hospital` 진입 검증). 페이지 0개·전부 빈 html_text 면 분류 자체를 막음
- ✅ **룰 단독(use_llm=False) 경로 70 cap** (`_cap_rule_only_confidence`). LLM·Vision 교차검증 없는 경로는 "확실" 불가
- ⚠️ 잔여 — 외부 시그널 전부 None 일 때의 **명시적** 추가 페널티는 미적용. 현재는 외부 기여도가 자연히 낮아지는 것에 의존(단일 소스 과신 방지를 명시 페널티로 강화할지는 실데이터 후 판단)

#### 사용 예시
```python
from ai import classify_hospital
from shared.models import CrawlData

crawl_data = CrawlData(...)           # 김경재가 자체 사이트 크롤링 후 채워서 전달

# 4 시그널 전부 활성화 (V2 기본) — 외부 시그널은 개별 키워드 인자
# 보통 BE 핸들러가 db.load_external_signals(hospital_id) 결과를 **external 로 전개
result = classify_hospital(
    crawl_data,
    use_vision=True,
    kakao_place=...,                  # 카카오 panel3 정제본 (KakaoPlace)
    kakao_reviews=...,                # 카카오 후기 키워드 빈도 (KakaoReviews)
    naver_reviews=...,                # 네이버 플레이스 후기 (NaverPlace)
    google_reviews=...,               # 구글 Places 리뷰 집계 (GoogleReviews)
)

# 외부 크롤링 미완료 시 graceful 처리 (외부 인자 생략 → self_claim 만 사용)
result = classify_hospital(crawl_data, use_vision=False)

# DynamoDB single-table 에 저장 (entity SK="CLASSIFICATION")
db.put_item(
    TableName="kmuproj-XX-clinic-Hospitals",
    Item={"hospital_id": crawl_data.hospital_id, "entity": "CLASSIFICATION", **result.model_dump()},
)
```

---

### 2. `generate_description` ⭐ **본 서비스의 핵심 함수** (시연 10개 한정)

분류 결과 + 4 시그널 원본 데이터 전체를 받아 자연어 통합 상세 설명을 생성. **FE-BE `GET /api/hospitals/{id}` 응답의 `ai_description` 필드가 이 함수의 결과.**

> **PoC 한도**: 지원 계정 Bedrock 자원이 10개 병원 한도이므로 시연 10개 병원에만 호출. 나머지 9990개 병원은 `ai_description = null` 로 반환되고 FE가 자연어 단락 대신 룰 기반 태그 카드를 렌더링한다. 어느 병원이 시연 대상인지는 DynamoDB single-table `DESCRIPTION` entity 존재 여부로 판별.

> **4 시그널은 `detailed_signals` 로 전달된다** — `classify_hospital` 이 외부 시그널(카카오/네이버/구글)을 이미 흡수해 `DetailedSignals`(self_claim·vision·blog·reviews)로 정제하므로, generate_description 은 `detailed_signals` 만 받으면 4 시그널 종합이 된다. 별도 `external_signals` 파라미터는 두지 않는다(원본 외부 dict 를 LLM 에 직접 넣지 않음 — 정제된 시그널만).

```python
def generate_description(
    classification: Classification,
    detailed_signals: DetailedSignals,   # 4 시그널 정제본 (classify 가 외부 시그널 흡수)
    hospital_meta: HospitalMeta,         # 이름·주소 등 기본 정보
) -> HospitalDescription:
    ...
```

**`DetailedSignals` 입력 구조 (V2)**:

프롬프트 컨텍스트 구성 시 아래 sub-block 을 각각 섹션으로 분리하여 LLM 에 전달:
- `self_claim` — 자체 사이트 키워드 빈도·page_type 강조도
- `vision` — 시술 사진 분포(일반/미용/기타 비율) + 식별된 의료기기 목록
- `blog` — 네이버 블로그 주제 분포 + 상위 키워드 빈도
- `reviews` — 네이버 플레이스·카카오·구글 후기 키워드 빈도 합산 (개별 후기 본문 ❌)

각 sub-block 이 None 이면 해당 섹션을 컨텍스트에서 제외하고, LLM 에 "해당 시그널 정보 없음"을 명시적으로 전달하여 없는 데이터를 지어내지 않도록 강제.

#### 동작 흐름

**PoC에서는 시연 10개 병원에만 적용** (트랙 B). 나머지 9990개는 자연어 단락 없이 룰 기반 태그·메타데이터만 제공.

1. 분류 결과·신뢰도·4 시그널 원본 데이터를 구조화된 컨텍스트로 정리
2. 지원 계정 Bedrock Haiku/Nova에 전용 프롬프트 + 컨텍스트 입력
3. 프롬프트는 다음을 강제 (의료법 5규칙):
   - **주체 명시 표현 의무** — "이 병원이 자기 사이트에서 ~를 메인으로 표시함" 형태만 허용
   - **출처 시그널 태그 의무** — 각 단락의 `citations` 는 그 단락이 실제로 인용한 시그널만 박혀야 함. 자칭 단락에 reviews citation 붙이거나, 모든 단락에 self_claim 만 붙이는 것 금지
   - **평가·추천 표현 금지** — "잘 본다" "추천한다" 같은 의료광고 회색지대 표현 사용 금지
   - **약점 단락 의무화** — 보유하지 않은 장비·다루지 않는 분야를 반드시 1개 이상 단락으로 명시 (헛걸음 방지 핵심)
   - **JSON 검증** — 출력이 `HospitalDescription` 스키마를 만족하지 않으면 재시도 또는 `DescriptionValidationError`
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
    generator_model="global.anthropic.claude-sonnet-4-6",
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

병원 시그널 데이터를 시그널 단위 .txt 파일로 KB DataSource S3 에 업로드하고 선택적으로 ingestion job 을 트리거. 새 병원 분류 후 또는 분류 변경 후 호출.

> **이전 `index_hospital` 함수 폐기**. KB 경유로 변경. 직접 PutVectors 가 아니라 DataSource S3 에 파일을 업로드하고 ingestion job 을 트리거하는 방식.

> **현재 실구현 시그니처** — 호출자가 `build_signal_chunks(...)` + `build_ingest_metadata(meta, classification)` 로 청크/메타를 조립해 넘기는 패턴. BE 호출부에서 직접 빌더를 import 하여 사용.

```python
def ingest_hospital(
    hospital_id: str,
    signal_chunks: dict[str, str],   # build_signal_chunks() 반환값. signal_type → 텍스트
    metadata: dict,                   # build_ingest_metadata() 반환값 (metadataAttributes 안쪽 평탄 dict)
    *,
    trigger_ingestion: bool = False,  # False면 파일만 업로드, True면 ingestion job 즉시 트리거
) -> None:
    ...
```

**호출자 조립 패턴**:

```python
from ai.search.kb_store import build_signal_chunks, build_ingest_metadata, ingest_hospital

signal_chunks = build_signal_chunks(
    crawl_data=crawl_data,
    kakao_place=kakao_place,
    kakao_reviews=kakao_reviews,
    kakao_blog=kakao_blog,
    naver_reviews=naver_reviews,
)
metadata = build_ingest_metadata(hospital_meta, classification)
ingest_hospital(hospital_id, signal_chunks, metadata, trigger_ingestion=False)
```

#### 청크 전략

병원당 벡터 1개가 아닌 **시그널별 .txt 파일로 분리** (KB 파일 단위 청킹이 signal 경계 보존).

| signal_type | 내용 | S3 키 |
|---|---|---|
| `self_claim` | 자체 사이트 service/about/main 텍스트 + 카카오 자칭 키워드 | `{prefix}{hospital_id}/self_claim.txt` |
| `blog` | 자체 사이트 blog 페이지 + 카카오 블로그 포스트 제목/발췌 | `{prefix}{hospital_id}/blog.txt` |
| `reviews` | 카카오/네이버 후기 **키워드 빈도 요약만** (§56③) | `{prefix}{hospital_id}/reviews.txt` |

각 .txt 옆에 `.txt.metadata.json` 사이드카 파일 동봉. 사이드카 포맷:
```json
{"metadataAttributes": {<build_ingest_metadata 반환값>, "signal_type": "<signal_type>"}}
```

> **후기 처리 — 의료법 §56③ 준수** (아래 별도 박스 참조)

#### 동작
1. `signal_chunks` 에서 빈 텍스트 시그널은 스킵
2. 시그널별로 `.txt` + `.txt.metadata.json` 쌍을 DataSource S3 버킷에 업로드
3. `trigger_ingestion=True`면 `bedrock-agent:StartIngestionJob` 1회 호출. 배치 시 False 로 모두 올린 뒤 마지막에 한 번만 True
4. KB가 자동으로: 청크 분할(KB 기본 설정) → Titan v2 임베딩 → S3 Vectors 인덱스 적재

#### 의료법 §56③ 준수 — 후기 데이터 처리 규칙

| 항목 | 허용 | 금지 |
|---|---|---|
| 후기 raw 본문 DDB 저장 | 내부 분석용 OK | — |
| KB ingest 본문에 후기 포함 | **키워드 빈도만** ("친절: 42건" 형태) | 개별 후기 본문 그대로 박는 것 ❌ |
| AI 통합 설명에서 인용 | "후기 키워드 빈도 N%" + `[후기]` 배지 | "후기에서 호평" 같은 평가형 어조 ❌ |

의료광고법 §56③ — 환자의 치료 경험담(후기)이 의료광고로 간주될 수 있으므로, 개별 후기 본문을 사용자에게 직접 노출하거나 AI 설명 본문에 그대로 삽입하는 것을 금지. 키워드 빈도 통계 형태로만 가공하여 사용.

#### 의존성
- `KB_ID`: 환경 변수 (강사 제공 `GTBJ6HLFDK`)
- `KB_DATA_SOURCE_ID`: 환경 변수 (강사 제공 `PLC6QYALDU`)
- `KB_DATASOURCE_S3_BUCKET`, `KB_DATASOURCE_S3_PREFIX`: 환경 변수 (DataSource가 가리키는 S3 경로)
- IAM: `s3:PutObject` (DataSource 버킷), `bedrock-agent:StartIngestionJob`

#### 예외
- `KBIngestError` — S3 업로드 또는 ingestion job 트리거 실패

#### 메타데이터 파일 포맷

`{hospital_id}.txt.metadata.json` 의 본문은 **단순 dict** 형식 (List 형식 아님). 2026-05-26 실측으로 확정 — 14개 ingest 후 `numberOfDocumentsFailed: 0` 통과. 출처: AWS 공식 문서 "Add metadata to your files" + 실측.

```json
{
  "metadataAttributes": {
    "team_id": "clinic-focus",
    "hospital_id": "JDQ4...",
    "name": "하나이비인후과병원",
    "standard_specialty": "이비인후과",
    "primary_focus": ["코·수면호흡", "알레르기·비염"],
    "sido": "서울",
    "sigungu": "강남구",
    "confidence_score": 56,
    "lat": 37.4979277,
    "lng": 127.0429904
  }
}
```

**제약 — 2026-05-26 실측으로 확인된 함정**:

1. **값 타입**: string / number / boolean / list[string] 만 허용 (KB 공식 사양)
2. **빈 리스트 `[]` 거절**: KB가 `"invalid metadata attributes"`로 거절함. 빈 리스트 필드는 **dict에서 아예 제외** (`None`/`""`/0 도 같은 패턴 가능성 있음 — 미검증)
3. **List-form 형식 거절**: `[{"key": ..., "value": {"type": "STRING", "stringValue": ...}}]` 같은 List/typed-value 형식은 `"metadata file is not in valid JSON format"`로 거절됨. 그 형식은 KB의 다른 API(Retrieve filter expression)용이고 metadata 파일용 아님

#### 메타데이터 키 (KB Retrieve 필터링용)

| 키 | 타입 | 비고 |
|---|---|---|
| `team_id` | string | 필수 — `"clinic-focus"` 고정. KB가 02팀과 공유라 retrieve 시 `team_id=clinic-focus` 필터로 격리 |
| `hospital_id` | string | 필터 가능 (역추적용 핵심) |
| `standard_specialty` | string | 필터 가능 |
| `primary_focus` | list[string] | 필터 가능 (`stringContains` 등). **비어있으면 키 자체 제외** |
| `sido` | string | 필터 가능 |
| `sigungu` | string | 필터 가능 |
| `confidence_score` | number | 필터 가능 (`>=` 비교) |
| `lat` | number | 필터 가능 (bounding box용). null이면 키 제외 |
| `lng` | number | 필터 가능 (bounding box용). null이면 키 제외 |
| `last_updated` | string | 비필터 |

#### 실측 함정 (2026-05-26 검증)

14개 병원 ingest + `numberOfDocumentsFailed: 0` 통과(PR [#25](https://github.com/BORB-CHOI/clinic-focus/pull/25) scratch 우회로 — 제거됨, 본체는 `ai/search/kb_store.py`)로 확인된 사항.

1. **`metadataAttributes` 는 단순 dict, list-form 거절** — AWS 문서에 list-form 예시(`[{"key":..., "value":{"type":"STRING","stringValue":...}}]`)가 일부 있지만, DataSource 메타 파일에 그 형식을 쓰면 `"metadata file is not in valid JSON format"`으로 거절됨. 메타 파일은 반드시 `{"metadataAttributes": {"key": "value", ...}}` 단순 dict. list-form은 KB Retrieve filter expression 전용 문법임.
2. **빈 list·None 값 거절** — `"primary_focus": []`, `"lat": null` 같이 빈 리스트나 null 값이 들어가면 `"invalid metadata attributes"`로 거절됨. 해당 키는 **dict에서 아예 제외**해야 함. `primary_focus`가 비어있으면 키 생략, `lat`/`lng`가 None이면 키 생략.
3. **`team_id="clinic-focus"` 필수** — KB DataSource(`kmuproj-02-vector`)를 02팀과 공유하므로, `team_id` 없이 ingest하면 retrieve 시 02팀 데이터가 섞여 나옴. 모든 메타에 `"team_id": "clinic-focus"` 고정 필수.
4. **본문 자르지 말 것** — `vectorIngestionConfiguration: {}` (기본값) 셋팅이라 KB가 기본 청크 분할(약 300토큰)을 자동 수행. 우리가 임의로 1KB·8KB 한도를 걸면 사이트 공통 네비/메뉴 텍스트만 들어가는 사고가 발생함(실제 발생). 통째 박고 KB에 청크 분할을 맡길 것.
5. **자체 사이트 텍스트 필수** — DDB의 분류 결과·설명 텍스트만 본문에 넣으면 구체 시술명(사마귀·냉동치료기 등) 쿼리와 매칭이 안 됨. `crawl_data.pages[*].html_text`가 본문에 포함돼야 함. **page_type 우선순위**: `service` → `about` → `main` → `doctors` → `blog` 순 정렬 후 앞 페이지부터 본문 상단에 배치 (정보 밀도가 높은 페이지가 청크 상위에 위치해야 임베딩 품질 향상).
6. **부정 문장 매칭 함정** — `generate_description`이 "X 정보 없음" 또는 "X는 다루지 않음"이라고 적은 부정 문장도 임베딩 공간에서 X 쿼리와 유사도가 높게 잡힘. 약점 단락이 검색 결과 1위로 반환돼 사용자 혼동 가능. 현재는 무시하고 진행하되, V2에서 부정 단락을 별도 필드/메타로 분리하여 임베딩 본문에서 제거하는 방안 검토 예정.
7. **Delete 운영 코드 호출 금지** — 강사 정책: `bedrock-agent:DeleteDocument`·`s3:DeleteObject` 권한은 있으나 의도치 않게 02팀 데이터를 삭제할 위험. 본문 갱신은 S3 `PutObject` 덮어쓰기, 폐업 처리는 `metadata.status="closed"` soft-delete로 우회.
8. **prefix 분리 운영 규약** — 운영 데이터는 `clinic-focus/prod/{hospital_id}.txt`, 실험·테스트용은 `clinic-focus/probe/...` 로 prefix 구분. 운영 prefix에 테스트 데이터가 섞이면 검색 품질에 직접 영향.

---

### 5. `retrieve_hospital`

자연어 쿼리로 유사 병원을 검색. **FE-BE `GET /api/search`의 자연어 모드가 내부에서 호출.**

> **이전 `search_similar` 함수 폐기**. KB Retrieve API 래퍼로 재설계 (`ai/search/kb_store.py`). 검색 경로 이원화에 따라 **자연어 쿼리만 처리** — 단순 카테고리 탐색(`sigungu=강남구 & specialty=피부과` 전체 목록)은 BE가 DynamoDB GSI로 직접 처리하고 AI 모듈을 거치지 않는다.

```python
def retrieve_hospital(
    query: SearchQuery,   # query_text 필수. lat/lng 있으면 복합 검색
) -> list[SearchResult]:
    ...
```

> **호출당 LLM 0건.** KB Retrieve API가 내부에서 Titan v2 임베딩 1회 + 벡터 검색 1회를 수행. Sonnet/Haiku 호출 0건. 응답 ~200~500ms, 검색당 비용 ~$0.00003. 자세한 건 `overview.md` "4-5. 검색 동작 원리" 참조.

#### 동작 흐름

**전제**: `query.query_text` 필수 (KB Retrieve 는 빈 쿼리 불가). 위치만 있는 단독 검색이나 메타 전체 목록 조회는 BE 측 DynamoDB GSI 경로로 처리되어 이 함수에 도달하지 않는다.

**자연어 단독 검색** (`query_text` 만 있음):

1. `bedrock-agent-runtime:Retrieve` 호출 — KB가 내부에서 Titan v2 임베딩 + 벡터 검색
2. `filter` 에 `team_id="clinic-focus"` + `sido`/`sigungu`/`specialty`/`min_confidence` 조건 추가
3. KB가 반환한 청크들의 `metadata.hospital_id` 로 역추적
4. **같은 hospital_id 에서 여러 청크 매칭 시 최고 score 1개만 유지 (dedup)**
5. score 내림차순 정렬 후 상위 `limit` 개 반환
6. 빈 결과 시 지역/specialty/min_confidence 완화 fallback (team_id 는 유지)

**자연어 + 위치 복합 검색** (`query_text` + `lat`/`lng`):

1. KB Retrieve 호출 — `filter` 에 lat/lng bounding box 범위 필터 추가 (`greaterThanOrEquals` / `lessThanOrEquals`)
2. KB 결과의 `metadata.lat`/`lng` 로 EC2 에서 haversine 공식으로 정확한 거리 재계산
3. `query.radius_km` 내 결과만 필터링
4. `sort` 기준(`relevance` / `distance` / `confidence`)으로 정렬
5. 상위 `limit` 개 반환

**필터 조립 규칙**:

```python
# 조건이 team_id 하나뿐이면 단일 조건
filter = {"equals": {"key": "team_id", "value": "clinic-focus"}}

# 추가 조건이 있으면 andAll 로 묶음
filter = {
    "andAll": [
        {"equals": {"key": "team_id", "value": "clinic-focus"}},
        {"equals": {"key": "sigungu", "value": query.sigungu}},
        {"greaterThanOrEquals": {"key": "confidence_score", "value": query.min_confidence}},
        # lat/lng bounding box (복합 검색 시)
        {"greaterThanOrEquals": {"key": "lat", "value": lat_min}},
        {"lessThanOrEquals": {"key": "lat", "value": lat_max}},
    ]
}
```

#### 의존성

- `KB_ID`: 환경 변수
- `AWS_REGION`: 환경 변수 (기본 `us-east-1`)
- IAM: `bedrock-agent-runtime:Retrieve` (지원 계정 인스턴스 프로파일)
- **LLM(Sonnet/Haiku) 호출 없음**

#### 예외
- `KBRetrieveError` — KB Retrieve API 호출 실패
- `InvalidQueryError` — `query_text` 가 비어있을 때 (KB 빈 쿼리 불가)

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

#### 실측 함정 (2026-05-26 검증)

하드코딩 4쿼리 + 자연어 검색(PR [#25](https://github.com/BORB-CHOI/clinic-focus/pull/25) scratch 우회로 — 제거됨, 본체는 `ai/search/kb_store.py` `retrieve_hospital`)으로 확인된 사항.

1. **`team_id` 필터 필수** — KB DataSource를 02팀과 공유하므로, 필터 없이 Retrieve하면 02팀이 ingest한 문서도 결과에 섞임. 모든 Retrieve 호출에 아래 필터를 기본 적용할 것:

   ```python
   filter = {
       "equals": {
           "key": "team_id",
           "value": "clinic-focus"
       }
   }
   ```

   `sido`·`sigungu`·`specialty`·`min_confidence` 추가 필터가 있을 때는 `andAll` 조합:

   ```python
   filter = {
       "andAll": [
           {"equals": {"key": "team_id", "value": "clinic-focus"}},
           {"equals": {"key": "sigungu", "value": query.sigungu}},
           # ... 추가 조건
       ]
   }
   ```

2. **single-table 환경에서 `entity="META"` 필터 자동 포함** — DDB single-table 재설계 후 KB ingest 본문은 `META` entity 데이터를 기준으로 검색해야 함. `hospital_id` 역추적 후 DDB 에서 entity 별 조회가 가능하므로 KB 필터 자체에 entity 를 박을 필요는 없지만, ingest 시 metadata 에 `entity="META"` 를 포함시켜 필터로 활용할 수 있음. 구현 시 확인 필요.

   ```python
   # ingest_hospital 에서 metadata 에 entity 포함한 경우의 필터 예시
   filter = {
       "andAll": [
           {"equals": {"key": "team_id", "value": "clinic-focus"}},
           {"equals": {"key": "entity", "value": "META"}},
           # ... 추가 조건
       ]
   }
   ```

3. **`lat`/`lng` bounding box 필터는 KB metadata 의 number 필터로 처리** — `ingest_hospital` 에서 metadata 에 `lat`/`lng` 를 number 타입으로 박고, Retrieve 시 `greaterThan`/`lessThan` 조합으로 bounding box 필터 적용. null 이면 metadata 키 자체 누락(빈 리스트/None 거절 실측 함정 동일).

4. **`numberOfResults` 최대 100 제한** — KB Retrieve API는 한 번 호출에 최대 100개 청크 반환. 한 병원에서 여러 청크가 나올 수 있으므로 `hospital_id` 기준 dedup 후 실제 병원 수는 더 적어질 수 있음. 카테고리 전체 탐색(`sigungu=강남구 & specialty=피부과` 전체 목록)이 이 경로에 적합하지 않은 이유.

5. **부정 문장 매칭 함정** — `generate_description`이 "X 정보 없음", "X는 다루지 않음" 형태로 쓴 부정 단락도 임베딩 공간에서 X 쿼리와 유사도가 높게 잡힘(`ingest_hospital` 실측 함정 6번 동일 현상). 현재는 무시하고 진행하되, V2에서 부정 단락을 임베딩 본문에서 분리하는 방안 검토 예정. Retrieve 결과에서 해당 청크를 점수 가중치 하향 처리하는 방어 로직도 고려.

6. **빈 쿼리 텍스트 불가** — KB Retrieve API는 `query_text`가 빈 문자열이면 오류 반환. `query.query_text`가 None이거나 빈 문자열이면 이 함수에 도달하기 전에 BE 측에서 DynamoDB GSI 경로로 분기시켜야 함. 이 함수 진입 전 validation 필수.

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

1. 각 이미지를 S3에서 가져와서 개인 계정 Bedrock Claude Sonnet 4.6 Vision (서울 리전, Global cross-region inference profile)에 입력
2. Vision 응답에 OCR 텍스트 + 시각 해석(시술/기기 식별, 메인 강조 영역 등) 둘 다 포함
3. 결과를 `ImageAnalysisResult` 리스트로 반환

#### 의존성

- `BEDROCK_VISION_MODEL_ID` (개인 계정, `global.anthropic.claude-sonnet-4-6` — Global cross-region inference profile)
- 개인 계정 자격증명 (`AI_AWS_*` 환경변수, `AI_AWS_REGION=ap-northeast-2`)
- IAM: 개인 계정 `bedrock:InvokeModel` (3-ARN 정책 — inference-profile + regional FM + global FM) / 지원 계정 `s3:GetObject`

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
| `BEDROCK_VISION_MODEL_ID` | `global.anthropic.claude-sonnet-4-6` | 트랙 C용 Vision (개인 계정, Global cross-region inference profile — foundation-model 직접 호출 불가) |
| `AI_AWS_REGION` | `ap-northeast-2` | 개인 계정 리전 (Sonnet 4.6 호출은 서울에서) |
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
> 프로파일로 자동 인증된다. **Sonnet 4.6(Vision 시연)만 개인 계정** (서울 리전 `ap-northeast-2`) 자격증명으로 boto3
> 클라이언트를 따로 생성한다. 자세한 건 `../CLAUDE.md`의 "AWS 계정·인프라 구조" + [`setup/aws-onboarding.md` Step 5](setup/aws-onboarding.md#step-5--개인-계정-sonnet-46-vision-연결-서울-리전-global-cross-region-inference) 참조.

---

## 분류 알고리즘 의사 코드 (참고)

```python
def classify_hospital(
    crawl_data: CrawlData,
    use_vision: bool = True,
    use_llm: bool = True,
    *,
    kakao_place=None, kakao_reviews=None, kakao_blog=None,
    naver_reviews=None, naver_blog=None, google_reviews=None,
) -> Classification:
    # 1. 자칭 컨셉 추출 (트랙 A: 룰 기반 use_llm=False / 트랙 B: LLM)
    #    카카오 tags 가 있으면 자칭 키워드·focus 보강
    self_claim_result = extract_self_claim(crawl_data.pages, use_llm, kakao_place)

    # 2. Vision 분석 (use_llm=True 이고 이미지가 있을 때만)
    if use_llm and use_vision and crawl_data.images:
        raw = analyze_images([img.url for img in crawl_data.images])
        vision_result = build_vision_signal(raw)
    else:
        vision_result = None

    # 3. 블로그 키워드 빈도 (자체 사이트 blog + 네이버 블로그)
    blog_result = analyze_blog_topics(crawl_data, naver_blog, kakao_blog)

    # 4. 후기 키워드 분석 (카카오+네이버+구글 합산, §56③ 본문 미저장)
    review_result = aggregate_review_keywords(kakao_reviews, naver_reviews, google_reviews)

    # 5. 4 시그널 교차 검증
    primary_focus, signal_scores = cross_validate_signals(
        self_claim_result, vision_result, blog_result, review_result
    )

    # 6. 자칭 도배 페널티
    #    자칭 ↑ + 나머지 시그널 ↓ 시 confidence 강제 감점
    if is_keyword_spamming(self_claim_result, vision_result, blog_result):
        signal_scores = apply_spamming_penalty(signal_scores)

    # 7. 신뢰도 점수 (룰 단독 use_llm=False 경로는 70 cap)
    confidence = compute_confidence(signal_scores, vision_result)

    return Classification(
        hospital_id=crawl_data.hospital_id,
        standard_specialty=infer_specialty(crawl_data),
        primary_focus=primary_focus,
        confidence=confidence,
        detailed_signals=build_detailed_signals(
            self_claim_result, vision_result, blog_result, review_result
        ),
        classified_at=datetime.utcnow(),
        classifier_version="v2.0",
    )
```

---

## BE 호출 패턴 예시

### 새 병원 등록 시 (배치)

```python
# be/handlers/index_hospital.py — 실구현은 run_index_pipeline(hospital_id, *, demo, trigger_ingestion)
from ai import (
    classify_hospital,
    generate_description,
    extract_services_and_doctors,
    find_related_hospitals,
    ingest_hospital,
)
from ai.search.kb_store import build_ingest_metadata, build_signal_chunks
from be.adapters.dynamo_adapter import DynamoAdapter
from be.adapters.s3_adapter import S3Adapter

def run_index_pipeline(hospital_id: str, *, demo: bool = False, trigger_ingestion: bool = True):
    db = DynamoAdapter()
    s3 = S3Adapter()

    # 1. 크롤링 데이터 + META + 외부 시그널 로드
    crawl_data = s3.load_crawl_data(hospital_id)              # 자체 사이트 CrawlData
    hospital_meta = db.load_hospital_meta(hospital_id)
    # 외부 시그널(카카오/네이버/구글)을 build_signal_chunks·classify 인자 dict 로.
    # 키는 두 함수의 키워드 인자명과 일치 → **external 로 전개. 적재 안 된 entity 는 None.
    external = db.load_external_signals(hospital_id)
    #   external = {kakao_place, kakao_reviews, kakao_blog, naver_reviews, google_reviews}

    # 2. AI 분류 (개별 외부 인자 전개 — 4 시그널 교차검증)
    #    demo=False → 룰 단독(Bedrock 0회), demo=True → LLM/Vision 시연 10개
    classification = classify_hospital(crawl_data, use_llm=demo, **external)
    db.save_classification(classification)

    # 3~5. 시연 10개만 — 진료항목·설명·관련병원 (LLM/Vision)
    if demo:
        services_and_doctors = extract_services_and_doctors(
            crawl_data=crawl_data, classification=classification, vision_results=[],
        )
        description = generate_description(
            classification=classification,
            detailed_signals=classification.detailed_signals,
            hospital_meta=hospital_meta,
        )
        related = find_related_hospitals(
            hospital_id=hospital_id,
            location=hospital_meta.location,
            primary_focus=classification.primary_focus,
            excluded_services=services_and_doctors.excluded_services,
        )
        db.save_description(description)
        db.save_services_and_doctors(hospital_id, services_and_doctors)
        db.save_related_hospitals(hospital_id, related)

    # 6. KB ingestion — 시그널별 청크(자칭/블로그/후기)로 분리 적재.
    #    DESCRIPTION 은 임베딩 본문에 미포함(상세페이지 표시용). 임베딩 = 시그널 원본 청크.
    #    metadata 는 검색 필터 키만(평탄 dict). signals_included·last_updated 같은
    #    표시용 값은 KB 가 아니라 DDB CLASSIFICATION/INGEST#STATE 에서 9영역이 직접 읽는다.
    signal_chunks = build_signal_chunks(crawl_data=crawl_data, **external)
    metadata = build_ingest_metadata(hospital_meta, classification)
    ingest_hospital(hospital_id, signal_chunks, metadata, trigger_ingestion=trigger_ingestion)

    return {"status": "indexed", "hospital_id": hospital_id, "demo": demo}
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
from shared.models import CrawlData, NaverBlog, NaverBlogPost, KakaoReviews

def test_classify_with_sample_data():
    crawl_data = CrawlData.model_validate_json(
        open("tests/fixtures/sample_hospital.json").read()
    )
    # 외부 인자 없이 호출 — self_claim 만 사용, confidence 패널티 적용
    result = classify_hospital(crawl_data, use_vision=False)
    assert result.confidence.level in ["확실", "추정", "정보 부족"]

def test_classify_with_external_signals():
    crawl_data = CrawlData.model_validate_json(
        open("tests/fixtures/sample_hospital.json").read()
    )
    naver_blog = NaverBlog(total=1, posts=[
        NaverBlogPost(title="아토피 치료", link="https://...",
                      description="...", post_date="20260501"),
    ])
    kakao_reviews = KakaoReviews(total_reviews=30,
                                 keyword_frequency={"친절": 15, "청결": 8})
    # 외부 시그널은 개별 키워드 인자 (dict 또는 모델 양받)
    result = classify_hospital(crawl_data, use_vision=False,
                               naver_blog=naver_blog, kakao_reviews=kakao_reviews)
    # blog·reviews 가 채워졌으므로 signals.blog·reviews 기여도가 잡혀야
    assert result.confidence.signals.blog is not None
    assert result.confidence.signals.reviews is not None
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