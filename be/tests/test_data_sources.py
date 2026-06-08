"""metadata.data_sources 동적 산출 로직 단위 테스트.

_build_data_sources 함수가 이미 로드된 데이터를 기반으로
실제 존재하는 출처만 반환하는지 검증한다.
AWS / DynamoDB 호출 없음.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from shared.models import (
    BlogSignal,
    Classification,
    Confidence,
    DetailedSignals,
    ReviewSignal,
    SelfClaimSignal,
    SignalContributions,
    VisionSignal,
)

from be.api.hospital import _build_data_sources

_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 픽스처 헬퍼
# ---------------------------------------------------------------------------

def _make_signals(
    *,
    review_count: int = 0,
    blog_count: int = 0,
    has_vision: bool = False,
) -> DetailedSignals:
    """DetailedSignals 생성 헬퍼 — 필요한 수치만 조정."""
    return DetailedSignals(
        self_claim=SelfClaimSignal(keywords=[], primary_focus=[], spam_score=0.0),
        vision=(
            VisionSignal(
                detected_devices=[],
                image_categories={},
                total_images_analyzed=5,
            )
            if has_vision
            else None
        ),
        blog=BlogSignal(total_posts=blog_count, keyword_frequency={}, primary_topics=[]),
        reviews=ReviewSignal(total_reviews=review_count, keyword_frequency={}, primary_topics=[]),
    )


def _make_classification(signals: DetailedSignals) -> Classification:
    """Classification 생성 헬퍼."""
    return Classification(
        hospital_id="test_h",
        standard_specialty="피부과",
        primary_focus=["일반 진료"],
        confidence=Confidence(score=85.0, level="확실", signals=SignalContributions(
            self_claim=40, vision=0, blog=30, reviews=15,
        )),
        detailed_signals=signals,
        classified_at=_TS,
        classifier_version="rule-v1",
    )


# ---------------------------------------------------------------------------
# 기본 동작
# ---------------------------------------------------------------------------

class TestBuildDataSourcesBaseline:
    def test_always_includes_public_registry(self):
        """META 항상 존재 → public_registry 항상 포함."""
        result = _build_data_sources(
            classification=None,
            public_doctors={},
            public_nonpay=[],
            site_pages=None,
        )
        assert "public_registry" in result

    def test_no_extra_sources_when_only_meta(self):
        """분류·크롤 데이터 없으면 public_registry 단 하나."""
        result = _build_data_sources(
            classification=None,
            public_doctors={},
            public_nonpay=[],
            site_pages=None,
        )
        assert result == ["public_registry"]

    def test_no_duplicates(self):
        """출처 중복 없음."""
        signals = _make_signals(review_count=10, blog_count=5, has_vision=True)
        classification = _make_classification(signals)
        result = _build_data_sources(
            classification=classification,
            public_doctors={"specialists_by_dept": {"피부과": 1}},
            public_nonpay=[object()],  # 빈 NonPayItem 대신 sentinel
            site_pages={"some": "data"},
        )
        assert len(result) == len(set(result)), "출처 중복이 있습니다"


# ---------------------------------------------------------------------------
# self_site
# ---------------------------------------------------------------------------

class TestSelfSite:
    def test_site_pages_present_adds_self_site(self):
        """SITE#PAGES entity 있으면 self_site 포함."""
        result = _build_data_sources(
            classification=None,
            public_doctors={},
            public_nonpay=[],
            site_pages={"hospital_id": "x", "entity": "SITE#PAGES", "pages": []},
        )
        assert "self_site" in result

    def test_site_pages_none_excludes_self_site(self):
        """SITE#PAGES entity 없으면 self_site 미포함."""
        result = _build_data_sources(
            classification=None,
            public_doctors={},
            public_nonpay=[],
            site_pages=None,
        )
        assert "self_site" not in result


# ---------------------------------------------------------------------------
# user_reviews
# ---------------------------------------------------------------------------

class TestUserReviews:
    def test_reviews_gt_zero_adds_user_reviews(self):
        """total_reviews > 0 이면 user_reviews 포함."""
        signals = _make_signals(review_count=10)
        cls = _make_classification(signals)
        result = _build_data_sources(
            classification=cls,
            public_doctors={},
            public_nonpay=[],
            site_pages=None,
        )
        assert "user_reviews" in result

    def test_reviews_zero_excludes_user_reviews(self):
        """total_reviews == 0 이면 user_reviews 미포함."""
        signals = _make_signals(review_count=0)
        cls = _make_classification(signals)
        result = _build_data_sources(
            classification=cls,
            public_doctors={},
            public_nonpay=[],
            site_pages=None,
        )
        assert "user_reviews" not in result

    def test_no_classification_excludes_user_reviews(self):
        """분류 없으면 user_reviews 미포함."""
        result = _build_data_sources(
            classification=None,
            public_doctors={},
            public_nonpay=[],
            site_pages=None,
        )
        assert "user_reviews" not in result


# ---------------------------------------------------------------------------
# blog
# ---------------------------------------------------------------------------

class TestBlog:
    def test_blog_posts_gt_zero_adds_blog(self):
        """total_posts > 0 이면 blog 포함."""
        signals = _make_signals(blog_count=3)
        cls = _make_classification(signals)
        result = _build_data_sources(
            classification=cls,
            public_doctors={},
            public_nonpay=[],
            site_pages=None,
        )
        assert "blog" in result

    def test_blog_posts_zero_excludes_blog(self):
        """total_posts == 0 이면 blog 미포함."""
        signals = _make_signals(blog_count=0)
        cls = _make_classification(signals)
        result = _build_data_sources(
            classification=cls,
            public_doctors={},
            public_nonpay=[],
            site_pages=None,
        )
        assert "blog" not in result


# ---------------------------------------------------------------------------
# vision
# ---------------------------------------------------------------------------

class TestVision:
    def test_vision_signal_present_adds_vision(self):
        """VisionSignal 있으면 vision 포함."""
        signals = _make_signals(has_vision=True)
        cls = _make_classification(signals)
        result = _build_data_sources(
            classification=cls,
            public_doctors={},
            public_nonpay=[],
            site_pages=None,
        )
        assert "vision" in result

    def test_vision_signal_none_excludes_vision(self):
        """VisionSignal None 이면 vision 미포함."""
        signals = _make_signals(has_vision=False)
        cls = _make_classification(signals)
        result = _build_data_sources(
            classification=cls,
            public_doctors={},
            public_nonpay=[],
            site_pages=None,
        )
        assert "vision" not in result


# ---------------------------------------------------------------------------
# 통합 시나리오
# ---------------------------------------------------------------------------

class TestBuildDataSourcesIntegration:
    def test_full_hospital_all_sources(self):
        """모든 데이터 있는 병원 → 5가지 출처 전부."""
        signals = _make_signals(review_count=50, blog_count=20, has_vision=True)
        cls = _make_classification(signals)
        result = _build_data_sources(
            classification=cls,
            public_doctors={"specialists_by_dept": {"피부과": 2}},
            public_nonpay=[object()],
            site_pages={"pages": ["index"]},
        )
        assert set(result) == {"public_registry", "self_site", "user_reviews", "blog", "vision"}

    def test_minimal_hospital_public_registry_only(self):
        """META만 있는 병원(분류 전) → public_registry 하나."""
        result = _build_data_sources(
            classification=None,
            public_doctors={},
            public_nonpay=[],
            site_pages=None,
        )
        assert result == ["public_registry"]

    def test_classified_no_external_signals(self):
        """분류됐지만 외부 시그널 0건(신규 분류·크롤 전) → public_registry 하나."""
        signals = _make_signals(review_count=0, blog_count=0, has_vision=False)
        cls = _make_classification(signals)
        result = _build_data_sources(
            classification=cls,
            public_doctors={},
            public_nonpay=[],
            site_pages=None,
        )
        assert result == ["public_registry"]

    def test_site_and_reviews_no_blog_no_vision(self):
        """자체사이트 + 리뷰만 있는 경우."""
        signals = _make_signals(review_count=15, blog_count=0, has_vision=False)
        cls = _make_classification(signals)
        result = _build_data_sources(
            classification=cls,
            public_doctors={},
            public_nonpay=[],
            site_pages={"pages": []},
        )
        assert set(result) == {"public_registry", "self_site", "user_reviews"}
        assert "blog" not in result
        assert "vision" not in result

    def test_order_starts_with_public_registry(self):
        """public_registry 는 항상 첫 번째 원소."""
        signals = _make_signals(review_count=5)
        cls = _make_classification(signals)
        result = _build_data_sources(
            classification=cls,
            public_doctors={},
            public_nonpay=[],
            site_pages={"pages": []},
        )
        assert result[0] == "public_registry"
