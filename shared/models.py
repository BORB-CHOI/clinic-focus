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


class CrawledImage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    page_url: str
    alt_text: str | None = None


class PublicData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    license_number: str
    specialists: list[str]
    registered_devices: list[str]


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
# 분류 결과
# ---------------------------------------------------------------------------

class SignalContributions(BaseModel):
    """각 시그널이 신뢰도 점수에 기여한 비중 (0~100)."""
    model_config = ConfigDict(extra="forbid")

    self_claim: int
    vision: int
    blog: int
    reviews: int


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
    min_confidence: int = 70
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

    image_url: str
    detected_devices: list[str]
    image_category: Literal["일반 진료", "미용 시술", "장비 사진", "건물·내부", "기타"]
    confidence: float  # 0~1


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


class FeedbackStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    agree_count: int
    disagree_count: int
    agree_ratio: float
    last_feedback_at: datetime | None = None


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
    previous_focus: list[str]
    new_focus: list[str]
    reason: Literal["feedback", "human_review", "vision_reanalysis", "recrawl"]
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
