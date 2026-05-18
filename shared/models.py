"""
공유 Pydantic 모델 — BE·AI 양쪽에서 import.
API 명세의 계약서 역할.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# 크롤링 데이터
# ─────────────────────────────────────────────

class CrawledPage(BaseModel):
    url: str
    page_type: Literal["main", "about", "service", "doctors", "blog", "other"]
    html_text: str
    fetched_at: datetime


class CrawledImage(BaseModel):
    url: str
    page_url: str
    alt_text: str | None = None


class PublicData(BaseModel):
    license_number: str
    name: str = ""
    address: str = ""
    phone: str = ""
    lat: float | None = None
    lng: float | None = None
    specialists: list[str] = Field(default_factory=list)
    registered_devices: list[str] = Field(default_factory=list)


class CrawlData(BaseModel):
    hospital_id: str
    website_url: str
    pages: list[CrawledPage] = Field(default_factory=list)
    images: list[CrawledImage] = Field(default_factory=list)
    public_data: PublicData | None = None


# ─────────────────────────────────────────────
# 분류 결과
# ─────────────────────────────────────────────

class SignalContributions(BaseModel):
    self_claim: int = 0  # 0~100
    vision: int = 0
    blog: int = 0
    reviews: int = 0


class Confidence(BaseModel):
    score: int = 0  # 0~100
    level: Literal["확실", "추정", "정보 부족"] = "정보 부족"
    signals: SignalContributions = Field(default_factory=SignalContributions)


class SelfClaimSignal(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    raw_text_snippet: str = ""


class VisionSignal(BaseModel):
    total_images: int = 0
    category_distribution: dict[str, int] = Field(default_factory=dict)
    detected_devices: list[str] = Field(default_factory=list)


class BlogSignal(BaseModel):
    total_posts: int = 0
    topic_distribution: dict[str, int] = Field(default_factory=dict)


class ReviewSignal(BaseModel):
    total_reviews: int = 0
    keyword_frequency: dict[str, int] = Field(default_factory=dict)


class DetailedSignals(BaseModel):
    self_claim: SelfClaimSignal = Field(default_factory=SelfClaimSignal)
    vision: VisionSignal = Field(default_factory=VisionSignal)
    blog: BlogSignal = Field(default_factory=BlogSignal)
    reviews: ReviewSignal = Field(default_factory=ReviewSignal)


class Classification(BaseModel):
    hospital_id: str
    standard_specialty: str
    primary_focus: list[str] = Field(default_factory=list)
    confidence: Confidence = Field(default_factory=Confidence)
    detailed_signals: DetailedSignals = Field(default_factory=DetailedSignals)
    classified_at: datetime = Field(default_factory=datetime.utcnow)
    classifier_version: str = "v1.0"


# ─────────────────────────────────────────────
# AI 통합 상세 설명
# ─────────────────────────────────────────────

class DescriptionParagraph(BaseModel):
    text: str
    citations: list[Literal["self_claim", "vision", "blog", "reviews", "public_data"]] = Field(
        default_factory=list
    )


class HospitalDescription(BaseModel):
    hospital_id: str
    headline: str
    paragraphs: list[DescriptionParagraph] = Field(default_factory=list)
    one_line_summary: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generator_model: str = ""


# ─────────────────────────────────────────────
# 검색
# ─────────────────────────────────────────────

class SearchQuery(BaseModel):
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


class SearchResult(BaseModel):
    hospital_id: str
    similarity_score: float | None = None
    distance_km: float | None = None
    matched_focus: list[str] = Field(default_factory=list)
    query_interpretation: str | None = None


# ─────────────────────────────────────────────
# 이미지 분석
# ─────────────────────────────────────────────

class ImageAnalysisResult(BaseModel):
    image_url: str
    detected_devices: list[str] = Field(default_factory=list)
    image_category: Literal["일반 진료", "미용 시술", "장비 사진", "건물·내부", "기타"] = "기타"
    confidence: float = 0.0


# ─────────────────────────────────────────────
# 피드백
# ─────────────────────────────────────────────

class FeedbackEntry(BaseModel):
    feedback_id: str
    hospital_id: str
    device_id: str
    primary_focus: str
    verdict: Literal["agree", "disagree"]
    received_at: datetime = Field(default_factory=datetime.utcnow)


class FeedbackStats(BaseModel):
    total_count: int = 0
    agree_count: int = 0
    disagree_count: int = 0
    agree_ratio: float = 0.0
    last_feedback_at: datetime | None = None


# ─────────────────────────────────────────────
# 서비스·의료진 (상세 페이지 영역 ②③)
# ─────────────────────────────────────────────

class Service(BaseModel):
    name: str
    source: Literal["self_claim", "vision", "blog", "reviews", "public_data"]


class ExcludedService(BaseModel):
    name: str
    reason: str  # 예: "사이트·블로그·후기 어디에도 언급 없음"
    confidence: float = 0.0


class Equipment(BaseModel):
    name: str
    source: Literal["vision", "public_data", "both"]
    confirmed: bool = True


class PriceItem(BaseModel):
    name: str
    price: str  # "50,000원" 등 원본 텍스트
    source_url: str = ""


class Doctor(BaseModel):
    name: str
    specialty: str = ""
    sub_specialty: str = ""
    career: list[str] = Field(default_factory=list)
    source: Literal["site", "public_data", "both"] = "site"


class ServicesAndDoctors(BaseModel):
    services: list[Service] = Field(default_factory=list)
    excluded_services: list[ExcludedService] = Field(default_factory=list)
    equipment: list[Equipment] = Field(default_factory=list)
    prices: list[PriceItem] = Field(default_factory=list)
    doctors: list[Doctor] = Field(default_factory=list)


# ─────────────────────────────────────────────
# 관련 병원 추천 (상세 페이지 영역 ⑧)
# ─────────────────────────────────────────────

class RelatedHospital(BaseModel):
    hospital_id: str
    name: str
    primary_focus: list[str] = Field(default_factory=list)
    similarity_score: float = 0.0
    recommendation_type: Literal["same_focus", "fills_gap"] = "same_focus"
    distance_km: float | None = None


# ─────────────────────────────────────────────
# 변경 이력 (상세 페이지 영역 ⑦)
# ─────────────────────────────────────────────

class ChangeRecord(BaseModel):
    hospital_id: str
    changed_at: datetime
    previous_focus: list[str]
    new_focus: list[str]
    reason: Literal["feedback", "human_review", "vision_reanalysis", "scheduled_update"]
    note: str = ""


# ─────────────────────────────────────────────
# 병원 메타 (기본 정보)
# ─────────────────────────────────────────────

class Location(BaseModel):
    lat: float
    lng: float
    address: str = ""


class HospitalMeta(BaseModel):
    hospital_id: str
    name: str
    address: str = ""
    phone: str = ""
    location: Location | None = None
    operating_hours: dict[str, str] = Field(default_factory=dict)
    parking: bool | None = None
    website_url: str = ""
    sido: str = ""
    sigungu: str = ""
