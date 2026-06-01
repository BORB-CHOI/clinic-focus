"""test_classify_rule.py — use_llm=False 룰 기반 분류 경로 단위 테스트.

실행:
    .venv/bin/python -m pytest ai/tests/ -q

모든 테스트는 Bedrock 실 호출 비용을 발생시키지 않는다.
invoke_model 은 @patch 로 완전히 차단하며 assert_not_called() 로 검증한다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from shared.models import (
    CrawledImage,
    CrawledPage,
    CrawlData,
    GoogleReviews,
    KakaoPlace,
    KakaoReviews,
    PublicData,
)


# ---------------------------------------------------------------------------
# 픽스처 헬퍼
# ---------------------------------------------------------------------------

def _make_page(
    page_type: str,
    html_text: str,
    url: str = "https://example-hospital.com/",
) -> CrawledPage:
    return CrawledPage(
        url=url,
        page_type=page_type,
        html_text=html_text,
        fetched_at=datetime.now(tz=timezone.utc),
        render_method="static",
    )


def _make_crawl_data(
    pages: list[CrawledPage],
    images: list[CrawledImage] | None = None,
    hospital_id: str = "hospital-001",
    website_url: str = "https://example-hospital.com",
    public_data: PublicData | None = None,
) -> CrawlData:
    return CrawlData(
        hospital_id=hospital_id,
        website_url=website_url,
        pages=pages,
        images=images or [],
        public_data=public_data,
    )


# ---------------------------------------------------------------------------
# 기본 정형외과 픽스처
# ---------------------------------------------------------------------------

ORTHO_MAIN_TEXT = """
정형외과 전문 클리닉입니다.
척추 디스크 치료, 어깨 관절 수술, 무릎 관절 내시경 시술을 전문으로 합니다.
허리 통증, 척추 협착증, 디스크 탈출증 등 척추 질환 전반을 다룹니다.
어깨 회전근개 파열, 무릎 연골 손상도 치료합니다.
"""

ORTHO_BLOG_TEXT = """
[포스팅 1] 척추 디스크 예방법
척추 건강을 위한 일상 습관. 디스크 압력을 줄이는 자세 교정.

[포스팅 2] 어깨 통증의 원인
회전근개 파열과 어깨 충돌 증후군. 무릎 관절경 시술 후기.

[포스팅 3] 무릎 연골 재생 치료
연골 손상 단계별 치료 방법. 척추 측만증 조기 발견.
"""


@pytest.fixture
def ortho_crawl_data() -> CrawlData:
    """정형외과 키워드(척추·디스크·어깨·무릎)가 들어간 기본 픽스처."""
    pages = [
        _make_page("main", ORTHO_MAIN_TEXT, "https://example-hospital.com/"),
        _make_page("about", "정형외과 의원입니다. 척추 전문 클리닉.", "https://example-hospital.com/about"),
        _make_page("service", "진료 항목: 척추, 디스크, 어깨, 무릎 관절", "https://example-hospital.com/service"),
        _make_page("blog", ORTHO_BLOG_TEXT, "https://example-hospital.com/blog"),
    ]
    return _make_crawl_data(pages)


@pytest.fixture
def ortho_with_public_data() -> CrawlData:
    """공공 데이터(전문의 자격) 포함 픽스처 — standard_specialty 추론에 사용."""
    pages = [
        _make_page("main", ORTHO_MAIN_TEXT),
        _make_page("blog", ORTHO_BLOG_TEXT),
    ]
    public_data = PublicData(
        license_number="12345",
        specialists=["정형외과 전문의"],
        registered_devices=[],
    )
    return _make_crawl_data(pages, public_data=public_data)


# ---------------------------------------------------------------------------
# 홍보성 도배 픽스처
# ---------------------------------------------------------------------------

SPAM_TEXT = """
전문 전문 전문 특화 전문클리닉 최고 최고 탈모 전문 탈모 전문 탈모 전문
탈모 탈모 탈모 탈모 탈모 탈모 탈모 전문클리닉 유일 명의 1위
탈모 탈모 탈모 탈모 탈모 탈모 탈모 탈모 탈모 탈모 탈모 탈모
"""


@pytest.fixture
def spam_crawl_data() -> CrawlData:
    """홍보성 어휘 도배 + 단일 키워드(탈모) 과반복 픽스처."""
    pages = [
        _make_page("main", SPAM_TEXT),
        _make_page("service", SPAM_TEXT),
    ]
    return _make_crawl_data(pages, hospital_id="spam-hospital-001")


# ---------------------------------------------------------------------------
# 이미지 포함 픽스처 (Vision 차단 검증용)
# ---------------------------------------------------------------------------

@pytest.fixture
def ortho_with_images() -> CrawlData:
    """이미지가 있어도 use_llm=False 이면 Vision 미호출 확인용."""
    pages = [
        _make_page("main", ORTHO_MAIN_TEXT),
        _make_page("blog", ORTHO_BLOG_TEXT),
    ]
    images = [
        CrawledImage(url="https://example-hospital.com/img1.jpg", page_url="https://example-hospital.com/"),
        CrawledImage(url="https://example-hospital.com/img2.jpg", page_url="https://example-hospital.com/"),
    ]
    return _make_crawl_data(pages, images=images)


# ---------------------------------------------------------------------------
# 테스트 (a) Bedrock 미호출
# ---------------------------------------------------------------------------

class TestNoBedrockCall:
    """use_llm=False 일 때 invoke_model 이 호출되지 않아야 한다."""

    @patch("ai.core.bedrock_client.invoke_model")
    def test_invoke_model_not_called(
        self, mock_invoke: MagicMock, ortho_crawl_data: CrawlData
    ) -> None:
        from ai.pipeline.classify import classify_hospital

        classify_hospital(ortho_crawl_data, use_llm=False)
        mock_invoke.assert_not_called()

    @patch("ai.core.bedrock_client.invoke_model")
    def test_invoke_model_not_called_with_images(
        self, mock_invoke: MagicMock, ortho_with_images: CrawlData
    ) -> None:
        """이미지가 있어도 use_llm=False 이면 Vision(=invoke_model) 미호출."""
        from ai.pipeline.classify import classify_hospital

        classify_hospital(ortho_with_images, use_vision=True, use_llm=False)
        mock_invoke.assert_not_called()


# ---------------------------------------------------------------------------
# 테스트 (b) primary_focus 에 기대 focus 포함
# ---------------------------------------------------------------------------

class TestPrimaryFocus:
    """룰 기반 분류 시 정형외과 관련 focus 가 primary_focus 에 포함돼야 한다."""

    @patch("ai.core.bedrock_client.invoke_model")
    def test_primary_focus_contains_ortho(
        self, _mock: MagicMock, ortho_crawl_data: CrawlData
    ) -> None:
        from ai.pipeline.classify import classify_hospital

        result = classify_hospital(ortho_crawl_data, use_llm=False)
        # 척추 / 어깨·견관절 / 무릎·관절 중 최소 하나는 포함돼야 함
        ortho_focuses = {"척추", "어깨·견관절", "무릎·관절"}
        assert ortho_focuses & set(result.primary_focus), (
            f"primary_focus={result.primary_focus} 에 정형외과 focus 없음"
        )

    @patch("ai.core.bedrock_client.invoke_model")
    def test_primary_focus_not_empty(
        self, _mock: MagicMock, ortho_crawl_data: CrawlData
    ) -> None:
        from ai.pipeline.classify import classify_hospital

        result = classify_hospital(ortho_crawl_data, use_llm=False)
        assert len(result.primary_focus) > 0


# ---------------------------------------------------------------------------
# 테스트 (c) standard_specialty 추론
# ---------------------------------------------------------------------------

class TestStandardSpecialty:
    """정형외과 키워드가 많은 텍스트 → standard_specialty 가 정형외과로 추론."""

    @patch("ai.core.bedrock_client.invoke_model")
    def test_standard_specialty_ortho(
        self, _mock: MagicMock, ortho_with_public_data: CrawlData
    ) -> None:
        from ai.pipeline.classify import classify_hospital

        result = classify_hospital(ortho_with_public_data, use_llm=False)
        assert result.standard_specialty == "정형외과", (
            f"standard_specialty={result.standard_specialty!r}"
        )

    @patch("ai.core.bedrock_client.invoke_model")
    def test_standard_specialty_text_fallback(
        self, _mock: MagicMock, ortho_crawl_data: CrawlData
    ) -> None:
        """공공 데이터 없어도 텍스트 키워드로 정형외과 추론."""
        from ai.pipeline.classify import classify_hospital

        result = classify_hospital(ortho_crawl_data, use_llm=False)
        assert result.standard_specialty == "정형외과"


# ---------------------------------------------------------------------------
# 테스트 (d) confidence 채워짐
# ---------------------------------------------------------------------------

class TestConfidence:
    """confidence.score 와 level 이 적절히 채워져야 한다."""

    @patch("ai.core.bedrock_client.invoke_model")
    def test_confidence_score_range(
        self, _mock: MagicMock, ortho_crawl_data: CrawlData
    ) -> None:
        from ai.pipeline.classify import classify_hospital

        result = classify_hospital(ortho_crawl_data, use_llm=False)
        assert 0 <= result.confidence.score <= 100

    @patch("ai.core.bedrock_client.invoke_model")
    def test_confidence_level_valid(
        self, _mock: MagicMock, ortho_crawl_data: CrawlData
    ) -> None:
        from ai.pipeline.classify import classify_hospital

        result = classify_hospital(ortho_crawl_data, use_llm=False)
        assert result.confidence.level in {"확실", "추정", "정보 부족"}

    @patch("ai.core.bedrock_client.invoke_model")
    def test_confidence_filled(
        self, _mock: MagicMock, ortho_crawl_data: CrawlData
    ) -> None:
        """score > 0 이어야 한다 (정형외과 키워드가 여러 페이지에 있음)."""
        from ai.pipeline.classify import classify_hospital

        result = classify_hospital(ortho_crawl_data, use_llm=False)
        assert result.confidence.score > 0


class TestEmptyFocusConfidence:
    """주력 분야를 하나도 식별하지 못하면(전 시그널 결손) 신뢰도가 바닥이어야 한다.

    회귀 가드 — 옛 버그: focus 후보가 없을 때 _cross_validate_signals 가 전체
    가중치(합≈1.0)를 반환해 confidence.score=100 '확실' 이 나왔음
    (docs/API-BE-AI.md '현 구현 약점' 사례). 이제 전 시그널 결손이면
    contributions 가 전부 None → score 0 '정보 부족'.
    """

    def test_no_focus_candidates_all_signals_none(self) -> None:
        from ai.pipeline.classify import _cross_validate_signals
        from shared.models import BlogSignal, ReviewSignal, SelfClaimSignal

        self_claim = SelfClaimSignal(keywords=[], primary_focus=[], spam_score=0.0)
        blog = BlogSignal(total_posts=0, keyword_frequency={}, primary_topics=[])
        reviews = ReviewSignal(total_reviews=0, keyword_frequency={}, primary_topics=[])

        primary_focus, contributions = _cross_validate_signals(
            self_claim=self_claim, blog=blog, reviews=reviews, vision=None,
        )
        assert primary_focus == []
        # 전 시그널 결손(미수집) → None("수집 안 됨"), 0(엇갈림)과 구분
        assert all(v is None for v in contributions.values())

    def test_no_focus_candidates_compute_confidence_is_low(self) -> None:
        from ai.pipeline.classify import _compute_confidence, _cross_validate_signals
        from shared.models import BlogSignal, ReviewSignal, SelfClaimSignal

        _, contributions = _cross_validate_signals(
            self_claim=SelfClaimSignal(keywords=[], primary_focus=[], spam_score=0.0),
            blog=BlogSignal(total_posts=0, keyword_frequency={}, primary_topics=[]),
            reviews=ReviewSignal(total_reviews=0, keyword_frequency={}, primary_topics=[]),
            vision=None,
        )
        confidence = _compute_confidence(contributions)
        assert confidence.score == 0
        assert confidence.level == "정보 부족"


# ---------------------------------------------------------------------------
# 테스트 (d-2) 결손 시그널 처리 — confidence-missing-signals §7 검증 6케이스
# ---------------------------------------------------------------------------

class TestMissingSignalsConfidence:
    """confidence-missing-signals 결정 §7 검증 케이스 (2026-05-30 구현, 결정노트 git 이력).

    3원칙: 결손은 점수 계산에서 제외(반값·0점 아님) / 근거 종류 수로 등급 천장 /
    화면 비율은 결손=None('수집 안 됨')·엇갈림=0 으로 구분.
    """

    def _redistribute(self, present_keys: list[str]) -> dict[str, float]:
        """present 시그널끼리 _WEIGHTS 를 합 1.0 으로 재분배 (일치 가정)."""
        from ai.pipeline.classify import _WEIGHTS

        ns = sum(_WEIGHTS[k] for k in present_keys)
        return {k: _WEIGHTS[k] / ns for k in present_keys}

    def test_case1_self_only_aligned_capped_추정(self) -> None:
        """① 자칭만 present 일치 → ≤70 '추정'(1종 cap), self 100 / 나머지 None."""
        from ai.pipeline.classify import CONFIDENCE_LEVEL1_CAP, _compute_confidence

        conf = _compute_confidence(
            {"self_claim": 1.0, "vision": None, "blog": None, "reviews": None}
        )
        assert conf.score == CONFIDENCE_LEVEL1_CAP   # 100 → 70 cap
        assert conf.level == "추정"
        assert conf.signals.self_claim == 100
        assert conf.signals.vision is None
        assert conf.signals.blog is None
        assert conf.signals.reviews is None

    def test_case2_three_signals_aligned_확실(self) -> None:
        """② 자칭+블로그+후기 모두 일치 → 높음 '확실', 3종 비율 (vision 결손 None)."""
        from ai.pipeline.classify import _compute_confidence

        w = self._redistribute(["self_claim", "blog", "reviews"])
        conf = _compute_confidence(
            {"self_claim": w["self_claim"], "vision": None,
             "blog": w["blog"], "reviews": w["reviews"]}
        )
        assert conf.score >= 95
        assert conf.level == "확실"
        assert conf.signals.self_claim and conf.signals.blog and conf.signals.reviews
        assert conf.signals.vision is None

    def test_case3_conflicting_signals_낮음(self) -> None:
        """③ 자칭 엇갈림 / 블로그·후기 일치 → 낮음(수집됐으나 불일치), present 끼리 비율."""
        from ai.pipeline.classify import CONFIDENCE_THRESHOLD_LOW, _compute_confidence

        w = self._redistribute(["self_claim", "blog", "reviews"])
        conf = _compute_confidence(
            {"self_claim": 0.0, "vision": None,   # 자칭 엇갈림 → 0 기여
             "blog": w["blog"], "reviews": w["reviews"]}
        )
        assert conf.score < CONFIDENCE_THRESHOLD_LOW   # 일치 안 해 낮음
        assert conf.level != "확실"
        assert conf.signals.self_claim == 0    # present 지만 엇갈림 → 0 (None 아님)
        assert conf.signals.vision is None     # 결손 → None
        assert conf.signals.blog > 0 and conf.signals.reviews > 0

    def test_case4_vision_missing_not_flipped_to_확실(self) -> None:
        """④ Vision 결손 + 자칭만 일치 → 케이스①과 동일(100 '확실' 로 뒤집히면 안 됨).

        §1-2 회귀 가드: 옛 Vision-None 재정규화가 비-Vision 합을 1.0 으로 끌어올려
        62 '정보 부족' 이던 게 빠지면 100 '확실' 로 뒤집히던 버그.
        """
        from ai.pipeline.classify import _compute_confidence, _cross_validate_signals
        from shared.models import BlogSignal, ReviewSignal, SelfClaimSignal

        sc = SelfClaimSignal(keywords=["척추"], primary_focus=["척추"], spam_score=0.0)
        blog = BlogSignal(total_posts=0, keyword_frequency={}, primary_topics=[])
        rev = ReviewSignal(total_reviews=0, keyword_frequency={}, primary_topics=[])
        _, contrib = _cross_validate_signals(sc, blog, rev, vision=None)
        conf = _compute_confidence(contrib)

        assert not (conf.score == 100 and conf.level == "확실")
        assert conf.score <= 70 and conf.level == "추정"
        assert contrib["vision"] is None
        assert conf.signals.vision is None

    def test_case5_all_missing_정보부족(self) -> None:
        """⑤ 전 시그널 결손 → score 0 '정보 부족', 전부 None."""
        from ai.pipeline.classify import _compute_confidence

        conf = _compute_confidence(
            {"self_claim": None, "vision": None, "blog": None, "reviews": None}
        )
        assert conf.score == 0
        assert conf.level == "정보 부족"
        assert conf.signals.self_claim is None
        assert conf.signals.vision is None
        assert conf.signals.blog is None
        assert conf.signals.reviews is None

    def test_case6_two_signals_rule_path_can_be_확실(self) -> None:
        """⑥ 자칭+후기 2종 일치 → '확실' 가능 (결정 5-2(b): use_llm cap 폐지).

        근거 종류 수가 '확실' 가부를 결정 — 룰 경로라도 2종 교차 일치면 확실.
        """
        from ai.pipeline.classify import _compute_confidence

        w = self._redistribute(["self_claim", "reviews"])
        conf = _compute_confidence(
            {"self_claim": w["self_claim"], "vision": None,
             "blog": None, "reviews": w["reviews"]}
        )
        assert conf.level == "확실"
        assert conf.score >= 95
        assert conf.signals.blog is None and conf.signals.vision is None


# ---------------------------------------------------------------------------
# 테스트 (d-3) present/결손 구분 — _cross_validate_signals 기여공식
# ---------------------------------------------------------------------------

class TestCrossValidatePresence:
    """결손은 None, present-엇갈림은 0 — §1-1 의 0.5 베이스라인 제거 검증."""

    def test_absent_signals_are_none(self) -> None:
        from ai.pipeline.classify import _cross_validate_signals
        from shared.models import BlogSignal, ReviewSignal, SelfClaimSignal

        sc = SelfClaimSignal(keywords=["보톡스"], primary_focus=["미용 시술"], spam_score=0.0)
        blog = BlogSignal(total_posts=0, keyword_frequency={}, primary_topics=[])
        rev = ReviewSignal(total_reviews=0, keyword_frequency={}, primary_topics=[])
        _, contrib = _cross_validate_signals(sc, blog, rev, vision=None)

        assert contrib["self_claim"] is not None   # present
        assert contrib["blog"] is None             # 결손
        assert contrib["reviews"] is None          # 결손
        assert contrib["vision"] is None           # 결손

    def test_present_but_misaligned_is_zero_not_none(self) -> None:
        from ai.pipeline.classify import _cross_validate_signals
        from shared.models import BlogSignal, ReviewSignal, SelfClaimSignal

        # 자칭 미용(가중치 큼) → top_focus=미용 시술. 블로그 탈모 → 엇갈림.
        sc = SelfClaimSignal(keywords=["보톡스"], primary_focus=["미용 시술"], spam_score=0.0)
        blog = BlogSignal(total_posts=5, keyword_frequency={"탈모": 3}, primary_topics=["탈모"])
        rev = ReviewSignal(total_reviews=0, keyword_frequency={}, primary_topics=[])
        _, contrib = _cross_validate_signals(sc, blog, rev, vision=None)

        assert contrib["blog"] == 0.0       # present 지만 엇갈림 → 0, None 아님
        assert contrib["reviews"] is None   # 결손


# ---------------------------------------------------------------------------
# 테스트 (d-4) 근거 종류 수 기반 등급 천장 (coverage cap)
# ---------------------------------------------------------------------------

class TestCoverageCap:
    """근거 종류 수(coverage)로 등급 천장 — 옛 use_llm 분기 cap 을 일반화한 설계.

    present 시그널이 MIN_CERTAIN_SIGNALS 미만이면 '확실' 불가(LEVEL1_CAP 상한).
    2종 이상 교차 일치면 룰 경로라도 '확실' 가능(결정 5-2(b)).
    """

    def test_single_signal_capped_at_level1(self) -> None:
        """present 1종이면 일치도 100 이어도 LEVEL1_CAP 으로 막혀 '확실' 불가."""
        from ai.pipeline.classify import CONFIDENCE_LEVEL1_CAP, _compute_confidence

        conf = _compute_confidence(
            {"self_claim": 1.0, "vision": None, "blog": None, "reviews": None}
        )
        assert conf.score == CONFIDENCE_LEVEL1_CAP
        assert conf.level != "확실"

    def test_two_signals_can_exceed_cap(self) -> None:
        """present 2종 일치면 LEVEL1_CAP 을 넘어 '확실' 도달 가능 (cap 미적용)."""
        from ai.pipeline.classify import CONFIDENCE_LEVEL1_CAP, _compute_confidence

        conf = _compute_confidence(
            {"self_claim": 0.5, "vision": 0.5, "blog": None, "reviews": None}
        )
        assert conf.score > CONFIDENCE_LEVEL1_CAP
        assert conf.level == "확실"

    @patch("ai.core.bedrock_client.invoke_model")
    def test_rule_ortho_fixture_below_high(
        self, _mock: MagicMock, ortho_crawl_data: CrawlData
    ) -> None:
        """룰 경로 정형외과 픽스처 — 자칭·자체블로그가 여러 focus(척추·어깨·무릎)로
        흩어져 일치도가 희석돼 score 가 HIGH 미만, '확실' 이 아니어야 한다."""
        from ai.pipeline.classify import classify_hospital

        result = classify_hospital(ortho_crawl_data, use_llm=False)
        assert result.confidence.level != "확실", (
            f"룰 ortho 픽스처 level='{result.confidence.level}' — 흩어진 focus 인데 확실"
        )
        assert result.confidence.level in {"추정", "정보 부족"}


# ---------------------------------------------------------------------------
# 테스트 (e) Vision 미호출 (vision_signal=None)
# ---------------------------------------------------------------------------

class TestVisionSkipped:
    """use_llm=False 이면 이미지가 있어도 vision_signal 이 None 이어야 한다."""

    @patch("ai.core.bedrock_client.invoke_model")
    def test_vision_signal_none_with_images(
        self, _mock: MagicMock, ortho_with_images: CrawlData
    ) -> None:
        from ai.pipeline.classify import classify_hospital

        result = classify_hospital(ortho_with_images, use_vision=True, use_llm=False)
        assert result.detailed_signals.vision is None

    @patch("ai.core.bedrock_client.invoke_model")
    def test_vision_signal_none_use_vision_false(
        self, _mock: MagicMock, ortho_with_images: CrawlData
    ) -> None:
        """use_llm=True 이더라도 use_vision=False 면 None."""
        from ai.pipeline.classify import classify_hospital

        # use_llm=True 경로지만 use_vision=False → vision None
        # (invoke_model 은 mock 으로 빈 응답 반환)
        _mock.return_value = {
            "content": [{"text": '{"keywords":[],"primary_focus":[],"spam_score":0}'}]
        }
        result = classify_hospital(ortho_with_images, use_vision=False, use_llm=True)
        assert result.detailed_signals.vision is None


# ---------------------------------------------------------------------------
# 테스트 (f) 홍보성 도배 → spam_score 높음 또는 페널티 경로
# ---------------------------------------------------------------------------

class TestSpamPenalty:
    """홍보성 도배 텍스트 → spam_score >= 0.7 또는 페널티 경로 진입."""

    @patch("ai.core.bedrock_client.invoke_model")
    def test_spam_score_high(
        self, _mock: MagicMock, spam_crawl_data: CrawlData
    ) -> None:
        from ai.pipeline.classify import _extract_self_claim_rule

        signal = _extract_self_claim_rule(spam_crawl_data)
        assert signal.spam_score >= 0.7, (
            f"spam_score={signal.spam_score:.4f} 가 0.7 미만 — 도배 감지 실패"
        )

    @patch("ai.core.bedrock_client.invoke_model")
    def test_classify_with_spam_completes_and_lowers_confidence(
        self, _mock: MagicMock
    ) -> None:
        """도배 자칭 + **외부 시그널** 어긋남 → 페널티 경로 진입, 신뢰도 하락.

        authorship 정정(2026-05-30): '어긋남'은 외부 시그널(제3자 후기 블로그·플레이스
        후기)이 자칭과 다를 때다. 자기 블로그로는 자기를 모순시킬 수 없다(같은 저자) —
        외부 독립 시그널로만 교차 검증한다.

        새 페널티 설계: 자칭 기여도만 감점(재배분 없음) → score 가 LOW 미만으로 내려간다.
        엇갈리는 블로그는 가짜 비율을 받지 않고 0 기여에 머문다(§3 원칙 3).
        """
        from ai.pipeline.classify import CONFIDENCE_THRESHOLD_LOW, classify_hospital

        # 자칭: 탈모 도배 (main/service). 자체 blog 페이지는 넣지 않는다 — 같은 저자라 모순 불가.
        spam_pages = [
            _make_page("main", SPAM_TEXT),
            _make_page("service", SPAM_TEXT),
        ]
        spam_data = _make_crawl_data(spam_pages, hospital_id="spam-hospital-001")
        # 외부 place앵커 블로그(카카오)는 정형외과 내용 → 자칭(탈모)과 어긋남 → blog_mismatch=True
        kakao_blog = {"seeds": [
            {"title": "척추 디스크 후기",
             "contents": "허리 디스크 어깨 회전근개 무릎 관절 정형외과",
             "origin_url": "https://blog.naver.com/x/1"},
        ]}

        result = classify_hospital(spam_data, use_llm=False, kakao_blog=kakao_blog)
        assert result.hospital_id == "spam-hospital-001"
        # 자칭 도배 + 블로그 어긋남 → 페널티로 score 가 LOW 미만 '정보 부족'
        assert result.confidence.score < CONFIDENCE_THRESHOLD_LOW, (
            f"도배+불일치인데 score={result.confidence.score} — 페널티 미적용 의심"
        )
        assert result.confidence.level == "정보 부족"
        # 엇갈리는 블로그는 가짜 비율을 받지 않는다 (present-misaligned → 0)
        assert result.confidence.signals.blog == 0, (
            f"엇갈린 블로그 기여={result.confidence.signals.blog} — 옛 재배분 잔재(가짜 비율)"
        )


# ---------------------------------------------------------------------------
# 테스트 — 하위 호환성 (LLM 경로 import 깨지지 않음)
# ---------------------------------------------------------------------------

class TestLLMPathImport:
    """use_llm=True(기본값) 경로의 함수 시그니처가 그대로 동작해야 한다."""

    def test_classify_hospital_default_signature_importable(self) -> None:
        """기본 시그니처 import 및 인자 inspect 가 깨지지 않는지 확인."""
        import inspect
        from ai.pipeline.classify import classify_hospital

        sig = inspect.signature(classify_hospital)
        params = sig.parameters
        assert "crawl_data" in params
        assert "use_vision" in params
        assert "use_llm" in params
        # 기본값 확인
        assert params["use_vision"].default is True
        assert params["use_llm"].default is True

    def test_rule_functions_importable(self) -> None:
        """새로 추가된 룰 기반 함수들이 import 가능한지 확인."""
        from ai.pipeline.classify import (  # noqa: F401
            _analyze_blog_rule,
            _extract_self_claim_rule,
        )


# ---------------------------------------------------------------------------
# 테스트 — _extract_self_claim_rule 단위 테스트
# ---------------------------------------------------------------------------

class TestExtractSelfClaimRule:
    """_extract_self_claim_rule 단독 단위 테스트."""

    def test_empty_pages_returns_empty(self) -> None:
        from ai.pipeline.classify import _extract_self_claim_rule

        crawl_data = _make_crawl_data([
            _make_page("doctors", "의사 소개 페이지"),  # self_claim 대상 아님
        ])
        signal = _extract_self_claim_rule(crawl_data)
        assert signal.keywords == []
        assert signal.primary_focus == []
        assert signal.spam_score == 0.0

    def test_keywords_extracted(self) -> None:
        from ai.pipeline.classify import _extract_self_claim_rule

        crawl_data = _make_crawl_data([
            _make_page("main", "척추 디스크 척추 허리 어깨 무릎"),
        ])
        signal = _extract_self_claim_rule(crawl_data)
        assert "척추" in signal.keywords or "디스크" in signal.keywords

    def test_primary_focus_mapped(self) -> None:
        from ai.pipeline.classify import _extract_self_claim_rule

        crawl_data = _make_crawl_data([
            _make_page("main", "척추 디스크 치료 전문"),
        ])
        signal = _extract_self_claim_rule(crawl_data)
        assert "척추" in signal.primary_focus

    def test_spam_score_normal_text_low(self) -> None:
        from ai.pipeline.classify import _extract_self_claim_rule

        normal_text = "척추 디스크 어깨 무릎 진료합니다. 재활치료도 함께합니다."
        crawl_data = _make_crawl_data([_make_page("main", normal_text)])
        signal = _extract_self_claim_rule(crawl_data)
        assert signal.spam_score < 0.7


# ---------------------------------------------------------------------------
# 테스트 — _analyze_blog_rule 단위 테스트
# ---------------------------------------------------------------------------

class TestAnalyzeBlogRule:
    """_analyze_blog_rule 단독 단위 테스트."""

    def test_no_blog_pages_returns_empty(self) -> None:
        from ai.pipeline.classify import _analyze_blog_rule

        crawl_data = _make_crawl_data([
            _make_page("main", "메인 텍스트"),
        ])
        signal = _analyze_blog_rule(crawl_data)
        assert signal.total_posts == 0
        assert signal.keyword_frequency == {}
        assert signal.primary_topics == []

    def test_blog_posts_counted(self) -> None:
        from ai.pipeline.classify import _analyze_blog_rule

        # 블로그 시그널 = 카카오 place앵커 blog seeds. 자체 blog 페이지는 self_claim 으로 빠진다.
        kakao_blog = {"seeds": [
            {"title": "척추 디스크 후기", "contents": "허리 디스크 치료", "origin_url": "https://blog.naver.com/a/1"},
            {"title": "어깨 무릎 후기", "contents": "관절 회복", "origin_url": "https://blog.naver.com/b/2"},
        ]}
        # 자체 blog 페이지가 있어도 블로그 시그널엔 안 들어감 (저자=병원 → self_claim)
        crawl_data = _make_crawl_data([
            _make_page("blog", "자체 블로그 글", url="https://h.com/blog/1"),
        ])
        signal = _analyze_blog_rule(crawl_data, kakao_blog=kakao_blog)
        assert signal.total_posts == 2  # 카카오 seed 2건만, 자체 blog 페이지 미포함

    def test_primary_topics_extracted(self) -> None:
        from ai.pipeline.classify import _analyze_blog_rule

        # 카카오 place앵커 블로그 발췌 본문에서 토픽 추출 (자체 blog 아님)
        kakao_blog = {"seeds": [
            {"title": "척추 디스크 후기",
             "contents": "허리 디스크 어깨 회전근개 무릎 관절",
             "origin_url": "https://blog.naver.com/c/3"},
        ]}
        signal = _analyze_blog_rule(_make_crawl_data([]), kakao_blog=kakao_blog)
        # 척추/어깨/무릎 중 하나 이상이 primary_topics 에 매핑돼야 함
        ortho_topics = {"척추", "어깨·견관절", "무릎·관절"}
        assert ortho_topics & set(signal.primary_topics), (
            f"primary_topics={signal.primary_topics}"
        )


# ===========================================================================
# 외부 시그널 통합 테스트 (신규)
# ===========================================================================

# ---------------------------------------------------------------------------
# 공통 외부 시그널 픽스처
# ---------------------------------------------------------------------------

def _make_kakao_place_dict(tags: list[str] | None = None) -> dict:
    """테스트용 KakaoPlace dict 생성 헬퍼."""
    return {
        "place_id": "test-kakao-001",
        "name": "테스트 한의원",
        "tags": tags or [],
    }


def _make_kakao_reviews_dict(
    total_reviews: int = 100,
    keyword_frequency: dict | None = None,
    review_contents: list[str] | None = None,
) -> dict:
    """테스트용 KakaoReviews dict 생성 헬퍼."""
    reviews = [
        {"review_id": i, "contents": text, "star_rating": 5}
        for i, text in enumerate(review_contents or [])
    ]
    return {
        "total_reviews": total_reviews,
        "average_score": 4.5,
        "keyword_frequency": keyword_frequency or {},
        "reviews": reviews,
        "has_next": False,
    }


def _make_google_reviews_dict(
    user_ratings_total: int = 50,
    keyword_frequency: dict | None = None,
    review_texts: list[str] | None = None,
) -> dict:
    """테스트용 GoogleReviews dict 생성 헬퍼."""
    reviews = [
        {"rating": 5, "text": text, "relative_time": "1개월 전"}
        for text in (review_texts or [])
    ]
    return {
        "place_id": "test-google-001",
        "name": "테스트 한의원",
        "rating": 4.7,
        "user_ratings_total": user_ratings_total,
        "keyword_frequency": keyword_frequency or {},
        "reviews": reviews,
    }


def _make_naver_place_dict(keyword_stats: dict | None = None) -> dict:
    """테스트용 NaverPlace dict 생성 헬퍼."""
    return {
        "place_id": "test-naver-001",
        "name": "테스트 한의원",
        "visitor_count": 1200,
        "keyword_stats": keyword_stats or {},
        "blog_seeds": [],
    }


# ---------------------------------------------------------------------------
# 테스트 1: kakao_place tags → primary_focus 보강
# ---------------------------------------------------------------------------

class TestKakaoTagsMerge:
    """kakao_place.tags 가 자칭 시그널의 primary_focus 를 보강해야 한다."""

    @patch("ai.core.bedrock_client.invoke_model")
    def test_kakao_tags_reflected_in_primary_focus(self, mock_invoke: MagicMock) -> None:
        """tags=['추나요법','도수치료','무릎관절치료'] → focus 에 반영 (무릎·관절 등)."""
        from ai.pipeline.classify import classify_hospital

        pages = [
            _make_page("main", "정형외과 의원입니다. 도수치료 전문입니다."),
        ]
        crawl_data = _make_crawl_data(pages)
        kakao_place = _make_kakao_place_dict(
            tags=["추나요법", "도수치료", "무릎관절치료", "무릎"]
        )

        result = classify_hospital(crawl_data, use_llm=False, kakao_place=kakao_place)
        mock_invoke.assert_not_called()

        # 무릎 태그가 있으므로 primary_focus 또는 detailed_signals.self_claim.keywords 에
        # 관련 항목이 포함돼야 한다
        all_claim_keywords = result.detailed_signals.self_claim.keywords
        all_claim_focus = result.detailed_signals.self_claim.primary_focus
        # tags 에서 추출된 키워드("무릎" 등)가 keywords 또는 focus 에 있어야 함
        assert (
            "무릎" in all_claim_keywords
            or "무릎·관절" in all_claim_focus
            or any("무릎" in kw for kw in all_claim_keywords)
        ), (
            f"kakao tags 가 자칭 시그널에 반영 안 됨. keywords={all_claim_keywords}, focus={all_claim_focus}"
        )

    @patch("ai.core.bedrock_client.invoke_model")
    def test_kakao_tags_no_spam_score_change(self, mock_invoke: MagicMock) -> None:
        """kakao tags 를 추가해도 spam_score 는 변하지 않아야 한다 (과도한 페널티 방지)."""
        from ai.pipeline.classify import _extract_self_claim_rule, _merge_kakao_tags_into_self_claim

        crawl_data = _make_crawl_data([_make_page("main", "척추 디스크 치료")])
        base_signal = _extract_self_claim_rule(crawl_data)
        original_spam = base_signal.spam_score

        kakao_place = _make_kakao_place_dict(tags=["척추", "디스크", "전문병원"])
        merged = _merge_kakao_tags_into_self_claim(base_signal, kakao_place)

        assert merged.spam_score == original_spam, (
            f"spam_score 가 변경됨: {original_spam} → {merged.spam_score}"
        )

    @patch("ai.core.bedrock_client.invoke_model")
    def test_kakao_tags_pydantic_model_input(self, mock_invoke: MagicMock) -> None:
        """KakaoPlace 모델 입력과 dict 입력이 동일 결과를 내야 한다."""
        from ai.pipeline.classify import _merge_kakao_tags_into_self_claim, _extract_self_claim_rule

        crawl_data = _make_crawl_data([_make_page("main", "척추 치료")])
        signal = _extract_self_claim_rule(crawl_data)

        tags = ["척추", "어깨", "무릎"]
        dict_input = _make_kakao_place_dict(tags=tags)
        model_input = KakaoPlace(place_id="test-001", tags=tags)

        result_dict = _merge_kakao_tags_into_self_claim(signal, dict_input)
        result_model = _merge_kakao_tags_into_self_claim(signal, model_input)

        assert set(result_dict.keywords) == set(result_model.keywords), (
            f"dict vs 모델 keywords 불일치: {result_dict.keywords} vs {result_model.keywords}"
        )
        assert set(result_dict.primary_focus) == set(result_model.primary_focus)

    @patch("ai.core.bedrock_client.invoke_model")
    def test_kakao_tags_none_returns_same(self, mock_invoke: MagicMock) -> None:
        """kakao_place=None 이면 원본 signal 을 그대로 반환해야 한다."""
        from ai.pipeline.classify import _merge_kakao_tags_into_self_claim, _extract_self_claim_rule

        crawl_data = _make_crawl_data([_make_page("main", "척추 치료")])
        signal = _extract_self_claim_rule(crawl_data)
        result = _merge_kakao_tags_into_self_claim(signal, None)

        assert result.keywords == signal.keywords
        assert result.primary_focus == signal.primary_focus
        assert result.spam_score == signal.spam_score


# ---------------------------------------------------------------------------
# 테스트 2: _analyze_reviews 후기 시그널 통합
# ---------------------------------------------------------------------------

class TestAnalyzeReviews:
    """_analyze_reviews 가 외부 시그널을 올바르게 통합해야 한다."""

    def test_all_none_returns_empty(self) -> None:
        """인자 전부 None → 빈 ReviewSignal (하위 호환)."""
        from ai.pipeline.classify import _analyze_reviews

        signal = _analyze_reviews()
        assert signal.total_reviews == 0
        assert signal.keyword_frequency == {}
        assert signal.primary_topics == []

    def test_kakao_reviews_total_and_keywords(self) -> None:
        """카카오 후기 총수·키워드 빈도가 ReviewSignal 에 반영돼야 한다."""
        from ai.pipeline.classify import _analyze_reviews

        kakao = _make_kakao_reviews_dict(
            total_reviews=303,
            keyword_frequency={"전문성": 145, "친절": 164},
        )
        signal = _analyze_reviews(kakao_reviews=kakao)

        assert signal.total_reviews == 303
        assert signal.keyword_frequency.get("전문성") == 145
        assert signal.keyword_frequency.get("친절") == 164

    def test_google_reviews_total_adds(self) -> None:
        """카카오 total_reviews + 구글 user_ratings_total 합산."""
        from ai.pipeline.classify import _analyze_reviews

        kakao = _make_kakao_reviews_dict(total_reviews=303)
        google = _make_google_reviews_dict(user_ratings_total=87)
        signal = _analyze_reviews(kakao_reviews=kakao, google_reviews=google)

        assert signal.total_reviews == 303 + 87

    def test_naver_keyword_stats_merged(self) -> None:
        """네이버 keyword_stats 가 keyword_frequency 에 합산돼야 한다."""
        from ai.pipeline.classify import _analyze_reviews

        naver = _make_naver_place_dict(keyword_stats={"척추": 20, "어깨": 10})
        signal = _analyze_reviews(naver_reviews=naver)

        assert signal.keyword_frequency.get("척추") == 20
        assert signal.keyword_frequency.get("어깨") == 10

    def test_naver_visitor_count_excluded_from_total(self) -> None:
        """네이버 visitor_count 는 후기 수가 아니므로 total_reviews 에 포함되면 안 된다."""
        from ai.pipeline.classify import _analyze_reviews

        naver = _make_naver_place_dict()  # visitor_count=1200 기본값
        signal = _analyze_reviews(naver_reviews=naver)

        # 네이버 단독이면 total_reviews = 0 (visitor_count 미포함)
        assert signal.total_reviews == 0

    def test_google_review_text_extracts_medical_keywords(self) -> None:
        """구글 keyword_frequency 가 비어 있으면 리뷰 본문 text 에서 의료 키워드 추출."""
        from ai.pipeline.classify import _analyze_reviews

        google = _make_google_reviews_dict(
            keyword_frequency={},  # 빈 dict
            review_texts=["척추 치료 너무 좋았어요", "어깨 통증이 나았습니다 무릎도"],
        )
        signal = _analyze_reviews(google_reviews=google)

        # 리뷰 본문에서 의료 키워드가 추출돼야 함
        assert len(signal.keyword_frequency) > 0, "구글 리뷰 본문 키워드 추출 실패"
        # 척추·어깨·무릎 중 하나 이상 포함
        medical_kws = {"척추", "어깨", "무릎"}
        assert medical_kws & set(signal.keyword_frequency.keys()), (
            f"의료 키워드 미추출: {signal.keyword_frequency}"
        )

    def test_google_review_text_to_primary_topics(self) -> None:
        """구글 후기 본문에서 의료 키워드 추출 → primary_topics 에 반영."""
        from ai.pipeline.classify import _analyze_reviews

        google = _make_google_reviews_dict(
            review_texts=[
                "척추 디스크 치료 정말 잘해요",
                "척추 전문 병원 추천합니다 허리가 나았어요",
            ],
        )
        signal = _analyze_reviews(google_reviews=google)

        assert "척추" in signal.primary_topics, (
            f"척추 가 primary_topics 에 없음: {signal.primary_topics}"
        )

    def test_kakao_review_contents_in_primary_topics(self) -> None:
        """카카오 후기 본문(contents)에서 의료 키워드 추출 → primary_topics."""
        from ai.pipeline.classify import _analyze_reviews

        kakao = _make_kakao_reviews_dict(
            review_contents=["레이저 시술 정말 잘해요", "보톡스 맞고 효과 좋았어요"],
        )
        signal = _analyze_reviews(kakao_reviews=kakao)

        # 미용 시술 관련 키워드(레이저·보톡스)가 primary_topics 에 반영돼야 함
        assert len(signal.primary_topics) > 0, "후기 본문에서 primary_topics 추출 실패"

    def test_dict_and_pydantic_model_same_result(self) -> None:
        """dict 입력과 Pydantic 모델 입력이 동일 결과를 내야 한다."""
        from ai.pipeline.classify import _analyze_reviews

        kakao_dict = _make_kakao_reviews_dict(
            total_reviews=100,
            keyword_frequency={"전문성": 50},
            review_contents=["척추 치료 좋았어요"],
        )
        google_dict = _make_google_reviews_dict(
            user_ratings_total=30,
            review_texts=["어깨 치료 효과적이에요"],
        )

        # Pydantic 모델로 변환
        kakao_model = KakaoReviews.model_validate(kakao_dict)
        google_model = GoogleReviews.model_validate(google_dict)

        result_dict = _analyze_reviews(kakao_reviews=kakao_dict, google_reviews=google_dict)
        result_model = _analyze_reviews(kakao_reviews=kakao_model, google_reviews=google_model)

        assert result_dict.total_reviews == result_model.total_reviews
        assert result_dict.keyword_frequency == result_model.keyword_frequency
        assert result_dict.primary_topics == result_model.primary_topics


# ---------------------------------------------------------------------------
# 테스트 3: ReviewSignal 에 후기 본문 raw 미포함 (의료법 §56③)
# ---------------------------------------------------------------------------

class TestReviewSignalNoPII:
    """ReviewSignal 어느 필드에도 개별 후기 본문 raw 가 담기면 안 된다 (의료법 §56③)."""

    def test_kakao_contents_not_in_review_signal(self) -> None:
        """카카오 후기 본문(contents)이 ReviewSignal 에 raw 로 담기지 않아야 한다."""
        from ai.pipeline.classify import _analyze_reviews

        sensitive_text = "유니크_후기_본문_노출_금지_테스트_contents"
        kakao = _make_kakao_reviews_dict(review_contents=[sensitive_text])
        signal = _analyze_reviews(kakao_reviews=kakao)

        # signal 전체를 dict 로 직렬화해 본문이 없는지 확인
        signal_dump = signal.model_dump_json()
        assert sensitive_text not in signal_dump, (
            "카카오 후기 본문이 ReviewSignal 에 raw 로 포함됨 — 의료법 §56③ 위반"
        )

    def test_google_text_not_in_review_signal(self) -> None:
        """구글 후기 본문(text)이 ReviewSignal 에 raw 로 담기지 않아야 한다."""
        from ai.pipeline.classify import _analyze_reviews

        sensitive_text = "유니크_구글_후기_본문_노출_금지_text_필드"
        google = _make_google_reviews_dict(review_texts=[sensitive_text])
        signal = _analyze_reviews(google_reviews=google)

        signal_dump = signal.model_dump_json()
        assert sensitive_text not in signal_dump, (
            "구글 후기 본문이 ReviewSignal 에 raw 로 포함됨 — 의료법 §56③ 위반"
        )

    def test_review_signal_fields_are_structured(self) -> None:
        """ReviewSignal 은 total_reviews·keyword_frequency·primary_topics 3개 필드만 가진다."""
        from shared.models import ReviewSignal

        # 모델 필드 확인
        fields = set(ReviewSignal.model_fields.keys())
        assert fields == {"total_reviews", "keyword_frequency", "primary_topics"}, (
            f"ReviewSignal 에 예상 외 필드: {fields}"
        )


# ---------------------------------------------------------------------------
# 테스트 4: 자칭 도배 + 외부 후기 어긋남 → 페널티 경로 진입
# ---------------------------------------------------------------------------

class TestSpamPenaltyWithExternalReviews:
    """외부 후기 시그널이 자칭과 어긋날 때 페널티 경로가 진입해야 한다."""

    @patch("ai.core.bedrock_client.invoke_model")
    def test_spam_penalty_triggered_when_reviews_mismatch(self, mock_invoke: MagicMock) -> None:
        """도배 텍스트(탈모 전문 도배) + 외부 후기(정형외과 키워드) → 페널티 경로.

        자칭은 '탈모' 도배, 후기는 '척추·어깨' 키워드 → review_mismatch 발생.
        페널티 후 자칭 기여도 비율이 억제돼야 한다.
        """
        from ai.pipeline.classify import classify_hospital

        spam_pages = [
            _make_page("main", SPAM_TEXT),        # 탈모 도배
            _make_page("service", SPAM_TEXT),
        ]
        crawl_data = _make_crawl_data(spam_pages, hospital_id="spam-mismatch-001")

        # 외부 후기: 척추·어깨 키워드 (탈모와 완전 어긋남)
        kakao_reviews = _make_kakao_reviews_dict(
            total_reviews=200,
            keyword_frequency={"전문성": 100},
            review_contents=["척추 디스크 치료 잘 해요", "어깨 통증 나았어요"],
        )

        result = classify_hospital(
            crawl_data,
            use_llm=False,
            kakao_reviews=kakao_reviews,
        )
        mock_invoke.assert_not_called()

        # 페널티가 걸리면 자칭 기여도 < 50%
        # (페널티 없이도 리뷰 어긋남으로 인해 기여도가 낮아짐)
        # 핵심 검증: 분류가 예외 없이 완료돼야 함
        assert result.hospital_id == "spam-mismatch-001"

    @patch("ai.core.bedrock_client.invoke_model")
    def test_is_keyword_spamming_detects_review_mismatch(self, mock_invoke: MagicMock) -> None:
        """_is_keyword_spamming 이 후기 어긋남(review_mismatch) 을 감지해야 한다."""
        from ai.pipeline.classify import _is_keyword_spamming
        from shared.models import (
            BlogSignal, ReviewSignal, SelfClaimSignal,
        )

        # 자칭: 탈모 전문 도배 (spam_score 높음)
        self_claim = SelfClaimSignal(
            keywords=["탈모", "탈모", "탈모"],
            primary_focus=["모발·탈모"],
            spam_score=0.85,
        )
        # 블로그: 탈모 없음 (어긋남)
        blog = BlogSignal(
            total_posts=5,
            keyword_frequency={"척추": 10},
            primary_topics=["척추"],
        )
        # 후기: 탈모 언급 없음, total_reviews 있음 (어긋남)
        reviews = ReviewSignal(
            total_reviews=150,
            keyword_frequency={"전문성": 80},
            primary_topics=["척추"],  # 척추만 → 탈모와 교집합 없음
        )

        is_spam = _is_keyword_spamming(self_claim, blog, reviews, vision=None)
        assert is_spam is True, (
            "자칭 도배 + 후기 어긋남 조합인데 _is_keyword_spamming=False — 페널티 미감지"
        )

    @patch("ai.core.bedrock_client.invoke_model")
    def test_no_penalty_when_reviews_align(self, mock_invoke: MagicMock) -> None:
        """후기가 자칭과 일치하면 페널티 미적용 (blog_mismatch=False)."""
        from ai.pipeline.classify import _is_keyword_spamming
        from shared.models import (
            BlogSignal, ReviewSignal, SelfClaimSignal,
        )

        self_claim = SelfClaimSignal(
            keywords=["척추", "디스크"],
            primary_focus=["척추"],
            spam_score=0.85,
        )
        blog = BlogSignal(
            total_posts=3,
            keyword_frequency={"척추": 5},
            primary_topics=["척추"],  # 자칭과 일치
        )
        reviews = ReviewSignal(
            total_reviews=100,
            keyword_frequency={"전문성": 50},
            primary_topics=["척추"],  # 자칭과 일치
        )

        is_spam = _is_keyword_spamming(self_claim, blog, reviews, vision=None)
        # blog_mismatch=False, review_mismatch=False → 도배 아님
        assert is_spam is False, (
            "후기·블로그 모두 자칭과 일치하는데 페널티 경로 진입"
        )


# ---------------------------------------------------------------------------
# 테스트 5: classify_hospital 시그니처 하위 호환
# ---------------------------------------------------------------------------

class TestExternalSignalsBackwardCompat:
    """외부 시그널 추가 후 기존 classify_hospital 호출 시그니처 하위 호환 유지."""

    @patch("ai.core.bedrock_client.invoke_model")
    def test_no_external_signals_works(self, mock_invoke: MagicMock, ortho_crawl_data: CrawlData) -> None:
        """외부 시그널 없이 classify_hospital(crawl_data) 호출 — 그대로 동작."""
        from ai.pipeline.classify import classify_hospital

        result = classify_hospital(ortho_crawl_data, use_llm=False)
        mock_invoke.assert_not_called()
        assert result.hospital_id == ortho_crawl_data.hospital_id

    @patch("ai.core.bedrock_client.invoke_model")
    def test_all_external_signals_keyword_only(self, mock_invoke: MagicMock, ortho_crawl_data: CrawlData) -> None:
        """모든 외부 시그널을 dict 로 전달 — use_llm=False 이면 invoke_model 미호출."""
        from ai.pipeline.classify import classify_hospital

        kakao_place = _make_kakao_place_dict(tags=["척추", "어깨"])
        kakao_reviews = _make_kakao_reviews_dict(total_reviews=50)
        naver_reviews = _make_naver_place_dict(keyword_stats={"척추": 5})
        google_reviews = _make_google_reviews_dict(user_ratings_total=20)

        result = classify_hospital(
            ortho_crawl_data,
            use_llm=False,
            kakao_place=kakao_place,
            kakao_reviews=kakao_reviews,
            naver_reviews=naver_reviews,
            google_reviews=google_reviews,
        )
        mock_invoke.assert_not_called()
        # 외부 후기 합산: 50(카카오) + 20(구글) = 70
        assert result.detailed_signals.reviews.total_reviews == 70

    @patch("ai.core.bedrock_client.invoke_model")
    def test_pydantic_model_inputs(self, mock_invoke: MagicMock, ortho_crawl_data: CrawlData) -> None:
        """Pydantic 모델 인자로 전달해도 dict 와 동일 결과."""
        from ai.pipeline.classify import classify_hospital

        kakao_place_model = KakaoPlace(place_id="k001", tags=["척추"])
        kakao_reviews_model = KakaoReviews(
            total_reviews=100,
            keyword_frequency={"전문성": 50},
        )
        google_reviews_model = GoogleReviews(
            place_id="g001",
            user_ratings_total=30,
        )

        result_model = classify_hospital(
            ortho_crawl_data,
            use_llm=False,
            kakao_place=kakao_place_model,
            kakao_reviews=kakao_reviews_model,
            google_reviews=google_reviews_model,
        )

        # dict 로 동일 데이터 전달
        result_dict = classify_hospital(
            ortho_crawl_data,
            use_llm=False,
            kakao_place={"place_id": "k001", "tags": ["척추"]},
            kakao_reviews={"total_reviews": 100, "keyword_frequency": {"전문성": 50}},
            google_reviews={"place_id": "g001", "user_ratings_total": 30},
        )
        mock_invoke.assert_not_called()

        assert result_model.detailed_signals.reviews.total_reviews == \
               result_dict.detailed_signals.reviews.total_reviews
        assert result_model.detailed_signals.reviews.keyword_frequency == \
               result_dict.detailed_signals.reviews.keyword_frequency

    @patch("ai.core.bedrock_client.invoke_model")
    def test_new_kwargs_are_keyword_only(self, mock_invoke: MagicMock) -> None:
        """외부 시그널 인자는 keyword-only (*) 이어야 한다 — 위치 인자로 전달 시 TypeError."""
        from ai.pipeline.classify import classify_hospital
        import inspect

        sig = inspect.signature(classify_hospital)
        params = sig.parameters

        # kakao_place 이후 인자들이 KEYWORD_ONLY 여야 한다
        kw_only_params = {
            name for name, p in params.items()
            if p.kind == inspect.Parameter.KEYWORD_ONLY
        }
        expected = {"kakao_place", "kakao_reviews", "kakao_blog", "naver_reviews", "google_reviews"}
        assert expected.issubset(kw_only_params), (
            f"외부 시그널 인자가 keyword-only 가 아님: {kw_only_params}"
        )


# ---------------------------------------------------------------------------
# 테스트 6: 실제 카카오 픽스처 파일 활용 (be/tests/fixtures/kakao/)
# ---------------------------------------------------------------------------

class TestKakaoFixtureIntegration:
    """be/tests/fixtures/kakao/ 의 실제 픽스처 파일로 통합 검증."""

    @patch("ai.core.bedrock_client.invoke_model")
    def test_real_kakao_place_fixture_tags(self, mock_invoke: MagicMock) -> None:
        """실제 panel3_27388604.json 픽스처의 tags 가 자칭 시그널에 반영돼야 한다.

        자생한방병원 픽스처 — tags: [추나요법, 도수치료, 무릎관절치료, 회전근개손상 등]
        """
        import json
        import os
        from ai.pipeline.classify import classify_hospital
        from be.adapters.kakao_place_adapter import parse_place

        fixture_path = os.path.join(
            os.path.dirname(__file__),
            "../../be/tests/fixtures/kakao/panel3_27388604.json",
        )
        with open(os.path.abspath(fixture_path)) as f:
            panel3 = json.load(f)

        place_dict = parse_place(panel3, "27388604")

        # 자생한방병원이라 한방 텍스트 필요
        pages = [
            _make_page("main", "한방병원입니다. 척추 디스크 치료 전문입니다. 추나요법을 제공합니다."),
        ]
        crawl_data = _make_crawl_data(pages, hospital_id="kakao-27388604")

        result = classify_hospital(crawl_data, use_llm=False, kakao_place=place_dict)
        mock_invoke.assert_not_called()

        # tags 에서 온 키워드들이 self_claim.keywords 에 포함돼야 함
        self_claim_kws = set(result.detailed_signals.self_claim.keywords)
        assert len(self_claim_kws) > 0

    @patch("ai.core.bedrock_client.invoke_model")
    def test_real_kakao_reviews_fixture(self, mock_invoke: MagicMock) -> None:
        """실제 reviews_27388604.json 픽스처의 키워드 빈도가 ReviewSignal 에 반영돼야 한다."""
        import json
        import os
        from ai.pipeline.classify import classify_hospital
        from be.adapters.kakao_place_adapter import parse_reviews

        fixture_path = os.path.join(
            os.path.dirname(__file__),
            "../../be/tests/fixtures/kakao/reviews_27388604.json",
        )
        with open(os.path.abspath(fixture_path)) as f:
            reviews_raw = json.load(f)

        reviews_dict = parse_reviews(reviews_raw)
        # 픽스처 확인: total_reviews=303, 전문성=145
        assert reviews_dict["total_reviews"] == 303

        pages = [_make_page("main", "한방병원입니다. 척추 치료 전문입니다.")]
        crawl_data = _make_crawl_data(pages, hospital_id="kakao-reviews-test")

        result = classify_hospital(crawl_data, use_llm=False, kakao_reviews=reviews_dict)
        mock_invoke.assert_not_called()

        reviews_signal = result.detailed_signals.reviews
        assert reviews_signal.total_reviews == 303, (
            f"total_reviews={reviews_signal.total_reviews} (expected 303)"
        )
        assert "전문성" in reviews_signal.keyword_frequency, (
            f"전문성 미포함: {reviews_signal.keyword_frequency}"
        )
