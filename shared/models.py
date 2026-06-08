from __future__ import annotations

from datetime import datetime
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, model_validator


# ---------------------------------------------------------------------------
# 크롤링 데이터
# ---------------------------------------------------------------------------

class CrawledPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    page_type: Literal["main", "about", "service", "doctors", "blog", "other"]
    html_text: str
    fetched_at: datetime
    render_method: Literal["static", "playwright"] = "static"


class CrawledImage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    page_url: str
    alt_text: str | None = None


class NonPayItem(BaseModel):
    """심평원 비급여진료비정보(15001700) 1건 — 병원이 *공식 신고*한 비급여 항목.

    의료법 제45조의2(비급여 진료비용 보고·공개)에 따른 공공 신고 사실이다. 우리가
    "이 병원이 미용/도수에 편중됐다"고 평가하는 게 아니라, 병원이 심평원에 신고한
    항목 그대로를 옮긴다(주체 명시 원칙). 가격(amount)은 신고 당시 원문 금액.
    """
    model_config = ConfigDict(extra="forbid")

    item_name: str                     # 비급여 항목명 (npayKorNm 신고명 그대로)
    category: str | None = None        # 분류 = npayKorNm 계층 첫 세그먼트(예: "이학요법료")
    amount: int | None = None          # 신고 금액(curAmt). 범위/문자 신고분은 None


class PublicData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    license_number: str
    specialists: list[str]
    registered_devices: list[str]
    # ── 심평원 객관 신고데이터(전문의 교차검증·비급여 전향) — 전부 기본값(하위호환) ──
    # 진료과목별 전문의 수 {진료과목명: 전문의수}. getDgsbjtInfo2.8 의 dgsbjtCdNm+dgsbjtPrSdrCnt.
    # "진료과목 피부과로 표기하나 신고 기준 피부과 전문의 0명" 같은 간판-진실성 노출용.
    specialists_by_dept: dict[str, int] = {}
    # 총 의사 수(base getHospBasisList drTotCnt, 선택). 일반의 단독 추론 — 전 과목 전문의 0명인데 의사 N명.
    total_doctors: int | None = None
    # 신고된 비급여 항목 목록(15001700). 급여 본질진료 → 비급여 전향 객관 신호.
    nonpay_items: list[NonPayItem] = []


class CrawlData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hospital_id: str
    website_url: str
    pages: list[CrawledPage]
    images: list[CrawledImage]
    public_data: PublicData | None = None


# ---------------------------------------------------------------------------
# 4 시그널 세부 데이터
# ---------------------------------------------------------------------------

class SelfClaimSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keywords: list[str]
    primary_focus: list[str]
    spam_score: float  # 0~1, 높을수록 도배 의심


class VisionSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detected_devices: list[str]
    image_categories: dict[str, float]  # category -> 비율 (합계 1.0)
    total_images_analyzed: int
    # 장면 해석(scene·procedures·in_image_text)에서 추출한 의료 키워드 빈도(레거시·표시용).
    keyword_frequency: dict[str, int] = {}
    # 장면 해석 원문 합본(scene+procedures+in_image_text+devices). 교차검증이 진료과
    # taxonomy 키워드로 매칭해 focus 투표에 쓴다 — Vision 이 전 과목에서 보강하게.
    scene_text: str = ""


class BlogSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_posts: int
    keyword_frequency: dict[str, int]  # keyword -> 등장 횟수
    primary_topics: list[str]


class ReviewSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_reviews: int
    keyword_frequency: dict[str, int]
    primary_topics: list[str]


class DetailedSignals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    self_claim: SelfClaimSignal
    vision: VisionSignal | None = None
    blog: BlogSignal
    reviews: ReviewSignal


# ---------------------------------------------------------------------------
# 외부 플랫폼 시그널 소스 (카카오·네이버·구글 정제본)
#
# parse_* 어댑터(be/adapters/kakao_place_adapter.py 등)가 raw JSON 을 정제해
# 돌려주는 구조를 Pydantic 로 승격한 것. BE 가 크롤·파싱하고 AI 가 소비한다.
#
# - extra="ignore": parse_* 가 향후 필드를 더 줘도 모델은 깨지지 않는다
#   (extra="forbid" 인 내부 결과 모델과 의도적으로 다름).
# - PII(후기 작성자 owner·블로그 author)는 parse 단계에서 이미 제거되므로
#   이 모델들에도 필드 자체가 없다 (의료법 §56③ + 개인정보).
# - 후기 본문(contents) 은 DDB 저장·임베딩 입력용으로만 보존. 화면 노출 금지.
# ---------------------------------------------------------------------------

class KakaoReviewItem(BaseModel):
    """카카오 후기 1건 (owner PII 제거됨). 본문은 임베딩 입력용, 화면 노출 금지."""
    model_config = ConfigDict(extra="ignore")

    review_id: int | str | None = None
    contents: str = ""
    star_rating: int | None = None
    strength_labels: list[str] = []
    photo_count: int = 0
    registered_at: str | None = None


class KakaoBlogSeed(BaseModel):
    """카카오 블로그 시드 1건 (author 제거됨). origin_url 은 BlogSignal 시드."""
    model_config = ConfigDict(extra="ignore")

    review_id: int | str | None = None
    title: str = ""
    contents: str = ""
    origin_url: str | None = None
    photo_count: int = 0
    registered_at: str | None = None


class KakaoHira(BaseModel):
    """panel3.medical.hira 정제본 (보조 — HIRA 직접 호출이 우선)."""
    model_config = ConfigDict(extra="ignore")

    medical_center_type: str | None = None
    specialized_field: str | None = None
    doctor_count: dict[str, int] = {}
    established_at: str | None = None


class KakaoCategory(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full: str | None = None
    depth1: str | None = None
    depth2: str | None = None
    depth3: str | None = None


class KakaoPlace(BaseModel):
    """parse_place() 출력 — DDB KAKAO#PLACE entity. 자칭 키워드(tags)·대표 이미지·HIRA 보조본."""
    model_config = ConfigDict(extra="ignore")

    place_id: str
    name: str | None = None
    address: str | None = None
    phone_numbers: list[str] = []
    homepage_url: str | None = None
    homepages_raw: list[str] = []
    category: KakaoCategory = KakaoCategory()
    tags: list[str] = []                     # 자칭 키워드 시드 (primary_focus 입력)
    facilities: dict = {}
    mystore_intro: str | None = None
    hira: KakaoHira = KakaoHira()
    representative_image_url: str | None = None  # FE 대표 이미지 (Vision 입력 아님)
    photo_counts: dict = {}
    review_count: int | None = None
    average_score: float | None = None


class KakaoReviews(BaseModel):
    """parse_reviews() 출력 — DDB KAKAO#REVIEWS entity. 키워드 빈도는 화면 노출 가능."""
    model_config = ConfigDict(extra="ignore")

    total_reviews: int | None = None
    average_score: float | None = None
    keyword_frequency: dict[str, int] = {}
    reviews: list[KakaoReviewItem] = []
    has_next: bool = False


class KakaoBlog(BaseModel):
    """parse_blog() 출력 — DDB KAKAO#BLOG entity. origin_url 100% blog.naver.com 시드."""
    model_config = ConfigDict(extra="ignore")

    total_posts: int | None = None
    seeds: list[KakaoBlogSeed] = []


class NaverBlogPost(BaseModel):
    """네이버 블로그 검색 결과 1건. v1/search/blog 응답 정제 (HTML 태그 제거)."""
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    link: str = ""           # 블로그 포스트 URL (BlogSignal 시드)
    description: str = ""    # 검색 API 발췌 본문 (키워드 추출 입력, 화면 노출 금지)
    post_date: str | None = None


class NaverBlog(BaseModel):
    """parse_naver_blog() 출력 — DDB NAVER#BLOG entity. 블로그 시그널(20%)."""
    model_config = ConfigDict(extra="ignore")

    total: int | None = None
    keyword_frequency: dict[str, int] = {}  # 발췌 본문 키워드 빈도 (자체 추출)
    posts: list[NaverBlogPost] = []


class NaverPlace(BaseModel):
    """네이버 플레이스 정제본 — DDB NAVER#PLACE / NAVER#PLACE#REVIEWS.

    네이버 병원 카테고리는 키워드 통계를 노출하지 않으므로(task-queue 사실 8)
    keyword_stats 는 우리 측에서 후기 본문으로 직접 추출한 결과를 담는다.
    """
    model_config = ConfigDict(extra="ignore")

    place_id: str | None = None
    name: str | None = None
    visitor_count: int | None = None      # 누적 방문자 수
    keyword_stats: dict[str, int] = {}    # 후기 키워드 빈도 (자체 추출)
    blog_seeds: list[str] = []            # photoViewer ugc externalLink 블로그 시드 URL


class GoogleReviewItem(BaseModel):
    """구글 Places 리뷰 1건. author_name 은 보존하지 않는다 (PII)."""
    model_config = ConfigDict(extra="ignore")

    rating: int | None = None
    text: str = ""
    relative_time: str | None = None      # "2개월 전" 등 상대 시각 (절대 시각·작성자 미보존)


class GoogleReviews(BaseModel):
    """parse_google_reviews() 출력 — DDB GOOGLE#PLACE / GOOGLE#REVIEWS.

    Places Details `reviews` 필드는 무료 tier 에서 최대 5건. rating 평균은 별도.
    """
    model_config = ConfigDict(extra="ignore")

    place_id: str | None = None
    name: str | None = None
    rating: float | None = None           # 전체 평점 평균 (Places `rating`)
    user_ratings_total: int | None = None
    keyword_frequency: dict[str, int] = {}  # 리뷰 본문 키워드 빈도 (자체 추출)
    reviews: list[GoogleReviewItem] = []


# 외부 시그널은 묶음 모델 대신 개별 인자로 전달한다 — classify_hospital /
# build_signal_chunks 가 kakao_place·kakao_reviews·kakao_blog·naver_reviews·
# naver_blog·google_reviews 를 키워드 인자로 받고, 핸들러는 DynamoAdapter.
# load_external_signals() 가 돌려준 dict 를 ``**`` 로 전개한다(옛 ExternalSignalBundle
# 컨테이너는 미사용이라 제거, 2026-05-28).


# ---------------------------------------------------------------------------
# 분류 결과
# ---------------------------------------------------------------------------

class SignalContributions(BaseModel):
    """각 시그널이 신뢰도 점수에 기여한 비중 (0~100).

    값의 의미를 두 가지로 구분한다 (confidence-missing-signals 결정):
      - ``int`` (0~100): 해당 시그널이 **수집됨(present)**. 0 은 "수집은 됐으나
        주력과 엇갈려 기여 0%"(엇갈림)를 뜻한다.
      - ``None``: 해당 시그널이 **미수집(결손)**. 화면엔 "수집 안 됨" 배지로 렌더.
        가짜 비율을 노출하지 않기 위해 0 과 명시적으로 구분한다.
    """
    model_config = ConfigDict(extra="forbid")

    self_claim: int | None = None
    vision: int | None = None
    blog: int | None = None
    reviews: int | None = None


class Confidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int  # 0~100
    level: Literal["확실", "추정", "정보 부족"]
    signals: SignalContributions


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hospital_id: str
    standard_specialty: str
    primary_focus: list[str]
    confidence: Confidence
    detailed_signals: DetailedSignals
    classified_at: datetime
    classifier_version: str


# ---------------------------------------------------------------------------
# AI 통합 상세 설명 ⭐ 핵심 결과물
# ---------------------------------------------------------------------------

class DescriptionParagraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    citations: list[Literal["self_claim", "vision", "blog", "reviews", "public_data"]]


class HospitalDescription(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hospital_id: str
    headline: str
    paragraphs: list[DescriptionParagraph]
    one_line_summary: str
    generated_at: datetime
    generator_model: str


# ---------------------------------------------------------------------------
# 검색
# ---------------------------------------------------------------------------

class SearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_text: str | None = None
    lat: float | None = None
    lng: float | None = None
    radius_km: float = 3.0
    sido: str | None = None
    sigungu: str | None = None
    specialty: str | None = None
    min_confidence: int = 0  # 0=신뢰도 하드필터 없음(전체 노출). >0 일 때만 거른다.
    sort: Literal["distance", "confidence", "relevance"] = "relevance"
    limit: int = 20

    @model_validator(mode="after")
    def require_query_or_location(self) -> SearchQuery:
        if self.query_text is None and (self.lat is None or self.lng is None):
            raise ValueError("query_text 또는 (lat, lng) 중 최소 하나 필요")
        return self


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hospital_id: str
    similarity_score: float | None = None
    distance_km: float | None = None
    matched_focus: list[str]
    query_interpretation: str | None = None


# ---------------------------------------------------------------------------
# 이미지 분석
# ---------------------------------------------------------------------------

class ImageAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_url: str  # http/https/s3 URL 또는 스크린샷 합성 라벨("screenshot:tile-N")
    detected_devices: list[str]
    image_category: Literal["일반 진료", "미용 시술", "장비 사진", "건물·내부", "기타"]
    confidence: float  # 0~1
    # ── 장면 해석(OCR 아님) — 이미지가 시각적으로 무엇을 보여주는지 ──────────
    # Vision 이 글자만 읽는 게 아니라 화면 자체를 해석한 결과. 기본값으로 둬서
    # 구 VISION#RESULTS(이 필드들 없음) 도 그대로 로드된다.
    scene: str = ""                              # 보이는 장면 1~3문장 묘사
    detected_procedures: list[str] = []          # 시각적으로 드러나는 시술·진료 항목
    in_image_text: str = ""                       # 이미지·배너·간판에 박힌 텍스트(보이는 그대로)


# ---------------------------------------------------------------------------
# 피드백
# ---------------------------------------------------------------------------

class FeedbackEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback_id: str
    hospital_id: str
    device_id: str
    primary_focus: str
    verdict: Literal["agree", "disagree"]
    received_at: datetime
    review_text: str | None = None
    age_bucket: str | None = None
    gender_bucket: str | None = None


class ReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal["agree", "disagree"]
    review_text: str
    age_bucket: str | None = None
    gender_bucket: str | None = None
    received_at: datetime


class FeedbackStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    agree_count: int
    disagree_count: int
    agree_ratio: float
    last_feedback_at: datetime | None = None
    recent_reviews: list["ReviewItem"] = []


# ---------------------------------------------------------------------------
# 상세 페이지 구성 요소
# ---------------------------------------------------------------------------

class Service(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category: str
    source: Literal["self_claim", "vision", "blog", "reviews", "public_data"]


class ExcludedService(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    reason: str
    # 이 병원이 다루지 않는 분야의 동네 대안 병원 ID — find_related_hospitals 가 역으로 채움.
    # 상세페이지 ⑧ "안 다루는 분야 옆 대안" 링크용. 비면 대안 미발견.
    alternative_hospital_ids: list[str] = []


class Equipment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    source: Literal["vision", "public_data"]
    confidence: float  # 0~1


class PriceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_name: str
    price_text: str  # 원문 그대로 ("50,000원~")


class Doctor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    specialty: str | None = None
    qualifications: list[str] = []
    sub_specialty: str | None = None


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: str
    lat: float | None = None
    lng: float | None = None
    sido: str
    sigungu: str


class OperatingHours(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekday: str | None = None
    saturday: str | None = None
    sunday: str | None = None
    holiday: str | None = None
    lunch_break: str | None = None


class Contact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str | None = None
    website_url: str | None = None
    reservation_url: str | None = None


class HospitalMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hospital_id: str
    name: str
    location: Location
    contact: Contact
    operating_hours: OperatingHours | None = None
    parking: bool | None = None
    # HIRA 종별/병원명 기반 표준 진료과목 (22 후보 중 하나). 분류기가 추론 대신 이 값을 권위로 사용.
    standard_specialty: str | None = None
    # 카드·상세 헤더 좌측 대표 이미지 URL. 카카오/네이버 대표사진(KAKAO#PLACE) 우선,
    # 없으면 크롤한 사이트의 https 이미지 1장. backfill_thumbnails.py 가 채운다.
    # None 이면 FE 가 그라데이션+이니셜 플레이스홀더(HospitalThumbnail). Vision 입력과 무관(표시 전용).
    thumbnail_url: str | None = None


class ServicesAndDoctors(BaseModel):
    model_config = ConfigDict(extra="forbid")

    services: list[Service]
    excluded_services: list[ExcludedService]
    equipment: list[Equipment]
    prices: list[PriceItem]
    doctors: list[Doctor]


# ---------------------------------------------------------------------------
# 관련 병원 추천
# ---------------------------------------------------------------------------

class RelatedHospital(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hospital_id: str
    name: str
    primary_focus: list[str]
    similarity_score: float
    recommendation_type: Literal["same_focus", "fills_gap"]
    distance_km: float | None = None


# ---------------------------------------------------------------------------
# 변경 이력 / 메타
# ---------------------------------------------------------------------------

class ClassificationChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hospital_id: str
    changed_at: datetime
    from_focus: list[str]
    to_focus: list[str]
    reason: Literal["feedback_accumulated", "human_review", "vision_reanalysis", "scheduled_recrawl"]
    notes: str | None = None
    classifier_version: str


class DataMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hospital_id: str
    last_crawled_at: datetime | None = None
    last_classified_at: datetime | None = None
    data_sources: list[str]
    confidence_warning: bool = False


# ---------------------------------------------------------------------------
# 하위 호환 alias — dynamo_adapter 에서 ChangeRecord 로 참조 중
# ---------------------------------------------------------------------------

ChangeRecord: TypeAlias = ClassificationChange


# ---------------------------------------------------------------------------
# 검색 이벤트 (데이터 해자 — 사용자 행동 신호)
# ---------------------------------------------------------------------------

class SearchEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: Literal["impression", "click", "select"]
    session_id: str          # 익명 식별자 (localStorage UUID)
    hospital_id: str
    query: str | None = None  # 검색어 (지도 탐색 시 null)
    position: int | None = None  # 검색 결과 내 순위 (0-based)
    created_at: datetime


class SearchEventStats(BaseModel):
    """병원별 이벤트 집계 — compute_event_scores.py 스크립트가 생성."""
    model_config = ConfigDict(extra="forbid")

    hospital_id: str
    impressions: int = 0
    clicks: int = 0
    selects: int = 0
    ctr: float = 0.0   # clicks / impressions
    scr: float = 0.0   # selects / clicks (방문 전환율)
    updated_at: datetime
