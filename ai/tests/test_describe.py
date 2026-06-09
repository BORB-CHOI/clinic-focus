"""test_describe.py — ai/pipeline/describe.py 단위 테스트.

검증 포인트:
- _serialize_specialists: public_data 없을 때 fallback, 전문의 있을 때/없을 때 렌더
- _serialize_nonpay_items: 없으면 빈 문자열, 항목 있으면 주체 명시 형태
- _build_prompt: public_data 있으면 플레이스홀더 치환, 없으면 기존 문구 그대로
- generate_description 시그니처 backward-compatibility: public_data 인자 없이 호출 가능

Bedrock invoke_model 은 반드시 mock (실 호출 비용 발생 금지, ai/CLAUDE.md).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from shared.models import (
    BlogSignal,
    Classification,
    Confidence,
    Contact,
    DetailedSignals,
    HospitalMeta,
    Location,
    NonPayItem,
    PublicData,
    ReviewSignal,
    SelfClaimSignal,
    SignalContributions,
)
from ai.pipeline.describe import (
    _build_prompt,
    _serialize_nonpay_items,
    _serialize_specialists,
)


# ---------------------------------------------------------------------------
# 픽스처 헬퍼
# ---------------------------------------------------------------------------

def _make_classification(hospital_id: str = "h_001") -> Classification:
    now = datetime.now(tz=timezone.utc)
    return Classification(
        hospital_id=hospital_id,
        standard_specialty="피부과",
        primary_focus=["아토피·습진", "여드름"],
        confidence=Confidence(
            score=72,
            level="추정",
            signals=SignalContributions(self_claim=70, vision=None, blog=60, reviews=65),
        ),
        detailed_signals=DetailedSignals(
            self_claim=SelfClaimSignal(
                keywords=["아토피", "여드름"], primary_focus=["아토피·습진"], spam_score=0.1
            ),
            blog=BlogSignal(
                total_posts=20,
                keyword_frequency={"아토피": 8, "여드름": 5},
                primary_topics=["아토피", "여드름"],
            ),
            reviews=ReviewSignal(
                total_reviews=50,
                keyword_frequency={"친절": 20, "아토피": 10},
                primary_topics=["친절", "아토피"],
            ),
        ),
        classified_at=now,
        classifier_version="v2.0",
    )


def _make_meta(hospital_id: str = "h_001") -> HospitalMeta:
    return HospitalMeta(
        hospital_id=hospital_id,
        name="테스트피부과의원",
        location=Location(
            address="서울 강남구 테헤란로 1",
            lat=37.498,
            lng=127.027,
            sido="서울",
            sigungu="강남구",
        ),
        contact=Contact(phone="02-000-0000"),
    )


def _make_public_data(
    specialists_by_dept: dict[str, int] | None = None,
    total_doctors: int | None = None,
    nonpay_items: list | None = None,
) -> PublicData:
    return PublicData(
        license_number="TEST-001",
        specialists=[],
        registered_devices=[],
        specialists_by_dept=specialists_by_dept or {},
        total_doctors=total_doctors,
        nonpay_items=nonpay_items or [],
    )


# ===========================================================================
# 1. _serialize_specialists
# ===========================================================================

class TestSerializeSpecialists:
    def test_none_returns_fallback(self):
        """public_data=None 이면 '확인된 항목 없음' 반환(하위호환)."""
        result = _serialize_specialists(None)
        assert result == "확인된 항목 없음"

    def test_empty_specialists_by_dept(self):
        """specialists_by_dept 빈 dict → 정보 없음 문구."""
        pd = _make_public_data(specialists_by_dept={})
        result = _serialize_specialists(pd)
        assert "전문의 정보 없음" in result
        assert "심평원 신고 기준" in result

    def test_empty_with_total_doctors(self):
        """전문의 없어도 total_doctors 가 있으면 의사 수 포함."""
        pd = _make_public_data(specialists_by_dept={}, total_doctors=2)
        result = _serialize_specialists(pd)
        assert "2명" in result

    def test_with_specialists(self):
        """전문의 있으면 과목·수 렌더, '심평원 신고 기준' 주체 명시."""
        pd = _make_public_data(specialists_by_dept={"피부과": 1, "가정의학과": 0})
        result = _serialize_specialists(pd)
        assert "심평원 신고 기준" in result
        assert "피부과" in result
        assert "1명" in result
        assert "가정의학과" in result

    def test_does_not_contain_evaluation_words(self):
        """평가·추천 표현('잘 본다', '전문', '탁월') 이 없어야 한다."""
        pd = _make_public_data(specialists_by_dept={"피부과": 2})
        result = _serialize_specialists(pd)
        for banned in ("잘 본다", "전문이다", "탁월", "추천"):
            assert banned not in result, f"금지 표현 '{banned}' 발견: {result}"


# ===========================================================================
# 2. _serialize_nonpay_items
# ===========================================================================

class TestSerializeNonpayItems:
    def test_none_returns_empty_string(self):
        """public_data=None 이면 빈 문자열 반환."""
        assert _serialize_nonpay_items(None) == ""

    def test_empty_items_returns_empty_string(self):
        """비급여 항목 없으면 빈 문자열 반환."""
        pd = _make_public_data(nonpay_items=[])
        assert _serialize_nonpay_items(pd) == ""

    def test_items_rendered_with_subject(self):
        """항목 있으면 '병원이 심평원에 신고한 비급여 항목' 형태로 주체 명시."""
        pd = _make_public_data(nonpay_items=[
            NonPayItem(item_name="도수치료", category="처치 및 수술료 등", amount=80000),
        ])
        result = _serialize_nonpay_items(pd)
        assert "병원이 심평원에 신고한 비급여 항목" in result
        assert "도수치료" in result
        assert "80,000원" in result

    def test_item_without_amount(self):
        """amount=None 인 항목도 정상 렌더(금액 표시 없음)."""
        pd = _make_public_data(nonpay_items=[
            NonPayItem(item_name="영양주사", category="주사료"),
        ])
        result = _serialize_nonpay_items(pd)
        assert "영양주사" in result
        # 금액 없으면 괄호 없어야 함
        assert "None" not in result

    def test_max_10_items(self):
        """항목 수가 10개를 초과해도 최대 10개만 렌더한다 (프롬프트 길이 제어)."""
        items = [NonPayItem(item_name=f"항목{i}", category="기타") for i in range(15)]
        pd = _make_public_data(nonpay_items=items)
        result = _serialize_nonpay_items(pd)
        # 항목10~14 는 미포함
        for i in range(10):
            assert f"항목{i}" in result
        assert "항목10" not in result


# ===========================================================================
# 3. _build_prompt — public_data 주입 확인
# ===========================================================================

class TestBuildPrompt:
    def test_prompt_no_public_data_uses_fallback(self):
        """public_data=None 이면 프롬프트에 '확인된 항목 없음' 문구가 있고 {specialists} 플레이스홀더가 없다."""
        cls = _make_classification()
        meta = _make_meta()
        signals = cls.detailed_signals
        prompt = _build_prompt(cls, signals, meta, public_data=None)
        assert "{specialists}" not in prompt
        assert "확인된 항목 없음" in prompt

    def test_prompt_with_public_data_injects_specialist_info(self):
        """public_data 있으면 전문의 정보가 프롬프트에 주입된다."""
        cls = _make_classification()
        meta = _make_meta()
        pd = _make_public_data(specialists_by_dept={"피부과": 1})
        signals = cls.detailed_signals
        prompt = _build_prompt(cls, signals, meta, public_data=pd)
        assert "심평원 신고 기준" in prompt
        assert "피부과" in prompt

    def test_prompt_with_nonpay_items_injects_items(self):
        """비급여 항목이 있으면 프롬프트에 포함된다."""
        cls = _make_classification()
        meta = _make_meta()
        pd = _make_public_data(nonpay_items=[
            NonPayItem(item_name="라식수술", category="시력교정"),
        ])
        signals = cls.detailed_signals
        prompt = _build_prompt(cls, signals, meta, public_data=pd)
        assert "라식수술" in prompt
        assert "병원이 심평원에 신고한 비급여 항목" in prompt

    def test_prompt_placeholder_fully_replaced(self):
        """{specialists}·{nonpay_items} 플레이스홀더가 남아있으면 안 된다."""
        cls = _make_classification()
        meta = _make_meta()
        prompt = _build_prompt(cls, cls.detailed_signals, meta, public_data=None)
        assert "{specialists}" not in prompt
        assert "{nonpay_items}" not in prompt


# ===========================================================================
# 4. generate_description — backward-compatibility: public_data 없이 호출 가능
# ===========================================================================

class TestGenerateDescriptionBackwardCompat:
    """generate_description 이 public_data 없이도 기존처럼 동작함을 확인.

    Bedrock 은 반드시 mock — 실 호출 비용 발생 금지.
    """

    def _valid_response(self, hospital_id: str) -> dict:
        """유효한 HospitalDescription JSON 을 담은 Bedrock mock 응답."""
        body = {
            "hospital_id": hospital_id,
            "headline": f"{hospital_id} 는 피부과 중심으로 자기 홈페이지에서 안내함",
            "paragraphs": [
                {
                    "text": "이 병원 홈페이지에서 아토피·여드름 진료를 메인으로 안내함.",
                    "citations": ["self_claim"],
                },
                {
                    "text": "미용 시술 관련 데이터가 부족해 직접 확인 권장.",
                    "citations": ["self_claim", "blog"],
                },
            ],
            "one_line_summary": "아토피·여드름 중심 동네 피부과, 미용 시술 데이터 없음",
            "generated_at": datetime.utcnow().isoformat(),
            "generator_model": "test-model",
        }
        return {"content": [{"type": "text", "text": json.dumps(body)}]}

    @patch("ai.pipeline.describe.invoke_model")
    def test_without_public_data(self, mock_invoke):
        """public_data 인자 없이 호출 가능 — 기존 시그니처 하위호환."""
        from ai.pipeline.describe import generate_description

        cls = _make_classification("h_compat")
        meta = _make_meta("h_compat")
        mock_invoke.return_value = self._valid_response("h_compat")

        result = generate_description(cls, cls.detailed_signals, meta)

        assert result.hospital_id == "h_compat"
        mock_invoke.assert_called_once()

    @patch("ai.pipeline.describe.invoke_model")
    def test_with_public_data(self, mock_invoke):
        """public_data 전달 시 정상 동작하고 Bedrock 1회 호출."""
        from ai.pipeline.describe import generate_description

        cls = _make_classification("h_pd")
        meta = _make_meta("h_pd")
        pd = _make_public_data(
            specialists_by_dept={"피부과": 1},
            nonpay_items=[NonPayItem(item_name="레이저치료", category="미용")],
        )
        mock_invoke.return_value = self._valid_response("h_pd")

        result = generate_description(cls, cls.detailed_signals, meta, public_data=pd)

        assert result.hospital_id == "h_pd"
        mock_invoke.assert_called_once()
        # 프롬프트에 심평원 정보가 주입됐는지 확인
        call_prompt = mock_invoke.call_args.kwargs.get("prompt") or mock_invoke.call_args[1].get("prompt") or mock_invoke.call_args[0][0]
        assert "심평원 신고 기준" in call_prompt
