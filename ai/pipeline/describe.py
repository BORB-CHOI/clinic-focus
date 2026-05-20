"""
generate_description: 4 시그널 분류 결과를 받아 자연어 통합 상세 설명을 생성.

의료법 5규칙 강제:
1. 주체 명시 의무 — "이 병원이 자기 사이트에서 ~를 메인으로 표시함" 형태
2. citations 비어선 안 됨
3. 평가·추천 형용사 금지
4. 약점·주의사항 포함 의무
5. 출력은 구조화된 JSON (HospitalDescription 파싱)
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ai.core.bedrock_client import invoke_model
from ai.core.exceptions import BedrockInvocationError, DescriptionValidationError
from shared.models import (
    Classification,
    DetailedSignals,
    HospitalDescription,
    HospitalMeta,
)

# 최대 재시도 횟수 (검증 실패 시 포함해서 최초 1회 + 재시도 2회 = 총 3회 시도)
MAX_RETRIES = 2

# 프롬프트 템플릿 파일 경로
# describe.py 는 ai/pipeline/ 에 있고 프롬프트는 ai/prompts/ 에 있으므로
# parent 를 두 번 올라가 ai/ 를 기준으로 잡는다.
_PROMPT_TEMPLATE_PATH = Path(__file__).parent.parent / "prompts" / "hospital_description.md"


# ---------------------------------------------------------------------------
# 프롬프트 빌드 헬퍼
# ---------------------------------------------------------------------------

def _load_prompt_template() -> str:
    """프롬프트 템플릿 파일을 읽어 반환. 파일 없으면 RuntimeError."""
    if not _PROMPT_TEMPLATE_PATH.exists():
        raise RuntimeError(
            f"프롬프트 템플릿 파일을 찾을 수 없음: {_PROMPT_TEMPLATE_PATH}"
        )
    return _PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def _serialize_vision_summary(signals: DetailedSignals) -> str:
    """VisionSignal을 사람이 읽기 좋은 문자열로 직렬화."""
    if signals.vision is None:
        return "데이터 없음"

    v = signals.vision
    categories_text = ", ".join(
        f"{cat}: {ratio:.0%}"
        for cat, ratio in sorted(v.image_categories.items(), key=lambda x: -x[1])
    )
    devices_text = ", ".join(v.detected_devices) if v.detected_devices else "없음"
    return (
        f"분석 이미지 수: {v.total_images_analyzed}장 / "
        f"이미지 카테고리 분포: {categories_text} / "
        f"식별된 의료기기: {devices_text}"
    )


def _serialize_blog_summary(signals: DetailedSignals) -> str:
    """BlogSignal을 사람이 읽기 좋은 문자열로 직렬화."""
    b = signals.blog
    top_keywords = sorted(b.keyword_frequency.items(), key=lambda x: -x[1])[:10]
    keywords_text = ", ".join(f"{kw}({cnt}회)" for kw, cnt in top_keywords)
    topics_text = ", ".join(b.primary_topics) if b.primary_topics else "없음"
    return (
        f"총 포스팅: {b.total_posts}건 / "
        f"주요 토픽: {topics_text} / "
        f"상위 키워드: {keywords_text}"
    )


def _serialize_review_summary(signals: DetailedSignals) -> str:
    """ReviewSignal을 사람이 읽기 좋은 문자열로 직렬화."""
    r = signals.reviews
    top_keywords = sorted(r.keyword_frequency.items(), key=lambda x: -x[1])[:10]
    keywords_text = ", ".join(f"{kw}({cnt}회)" for kw, cnt in top_keywords)
    topics_text = ", ".join(r.primary_topics) if r.primary_topics else "없음"
    return (
        f"총 후기: {r.total_reviews}건 / "
        f"주요 토픽: {topics_text} / "
        f"상위 키워드: {keywords_text}"
    )


def _build_prompt(
    classification: Classification,
    detailed_signals: DetailedSignals,
    hospital_meta: HospitalMeta,
    extra_instruction: str = "",
) -> str:
    """템플릿에 컨텍스트를 채워 완성된 프롬프트를 반환."""
    template = _load_prompt_template()

    sc = detailed_signals.self_claim
    self_claim_keywords = ", ".join(sc.keywords) if sc.keywords else "없음"

    # registered_devices: 이 함수의 시그니처에 CrawlData가 없으므로
    # vision의 detected_devices를 출처로 사용하고, public_data는 호출자가 전달한
    # classification.detailed_signals 범위 내 데이터만 활용한다.
    if detailed_signals.vision and detailed_signals.vision.detected_devices:
        registered_devices_text = ", ".join(detailed_signals.vision.detected_devices)
    else:
        registered_devices_text = "확인된 항목 없음"

    specialists_text = "확인된 항목 없음"  # HospitalMeta에 전문의 필드 없음 — public_data는 상위에서 전달

    context = {
        "hospital_id": classification.hospital_id,
        "hospital_name": hospital_meta.name,
        "standard_specialty": classification.standard_specialty,
        "primary_focus": ", ".join(classification.primary_focus),
        "confidence_score": classification.confidence.score,
        "self_claim_keywords": self_claim_keywords,
        "self_claim_spam_score": f"{sc.spam_score:.2f}",
        "vision_summary": _serialize_vision_summary(detailed_signals),
        "blog_summary": _serialize_blog_summary(detailed_signals),
        "review_summary": _serialize_review_summary(detailed_signals),
        "registered_devices": registered_devices_text,
        "specialists": specialists_text,
    }

    # 템플릿에는 출력 JSON 스키마 예시가 그대로 들어 있어 리터럴 중괄호가 많다.
    # str.format() 은 그 중괄호를 placeholder 로 오인해 KeyError 를 낸다.
    # → 알려진 placeholder 키만 명시적으로 치환한다.
    prompt = template
    for key, value in context.items():
        prompt = prompt.replace("{" + key + "}", str(value))

    if extra_instruction:
        prompt += f"\n\n## 이전 시도 실패 원인 — 반드시 수정\n\n{extra_instruction}"

    return prompt


# ---------------------------------------------------------------------------
# 응답 파싱 및 검증
# ---------------------------------------------------------------------------

def _extract_json_from_response(raw_response: dict[str, Any]) -> str:
    """Bedrock 응답 dict에서 텍스트 콘텐츠를 추출."""
    try:
        content = raw_response["content"]
        if isinstance(content, list):
            # Anthropic Messages API 형식
            text_blocks = [block["text"] for block in content if block.get("type") == "text"]
            return "\n".join(text_blocks).strip()
        # 단순 문자열인 경우
        return str(content).strip()
    except (KeyError, TypeError, IndexError) as e:
        raise DescriptionValidationError(
            f"Bedrock 응답 구조 파싱 실패: {e} / 원본: {raw_response}"
        ) from e


def _parse_and_validate(
    raw_text: str,
    hospital_id: str,
    generated_at: datetime,
    generator_model: str,
) -> HospitalDescription:
    """
    JSON 파싱 + HospitalDescription 검증.

    규칙 2 (citations 비어선 안 됨) 추가 검사 포함.
    파싱 또는 검증 실패 시 DescriptionValidationError.
    """
    # JSON 파싱
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise DescriptionValidationError(
            f"응답이 유효한 JSON이 아님: {e}\n원본 텍스트 앞 500자: {raw_text[:500]}"
        ) from e

    # generated_at, generator_model은 코드에서 주입 (모델 출력 신뢰 금지)
    data["hospital_id"] = hospital_id
    data["generated_at"] = generated_at.isoformat()
    data["generator_model"] = generator_model

    # Pydantic 검증
    try:
        description = HospitalDescription.model_validate(data)
    except ValidationError as e:
        raise DescriptionValidationError(
            f"HospitalDescription Pydantic 검증 실패: {e}"
        ) from e

    # 규칙 2: 각 단락 citations 비어선 안 됨
    empty_citation_indices = [
        i for i, p in enumerate(description.paragraphs) if not p.citations
    ]
    if empty_citation_indices:
        raise DescriptionValidationError(
            f"citations가 비어있는 단락 인덱스: {empty_citation_indices}. "
            "모든 단락에 self_claim / vision / blog / reviews / public_data 중 "
            "하나 이상의 출처 태그가 필요합니다."
        )

    # 규칙 4: 약점·주의사항 단락 존재 확인
    # 마지막 단락 또는 전체 단락 중 주의사항 키워드 포함 여부 체크
    caution_keywords = [
        "없음", "확인되지 않음", "부족", "권장", "주의", "불가", "해당 없음",
        "데이터가 충분하지 않", "직접 확인", "방문 전", "헛걸음",
    ]
    has_caution = any(
        any(kw in p.text for kw in caution_keywords)
        for p in description.paragraphs
    )
    if not has_caution:
        raise DescriptionValidationError(
            "약점·주의사항 단락이 없음. 보유하지 않은 장비, 다루지 않는 분야, "
            "또는 방문 전 확인 사항을 포함한 단락이 반드시 있어야 합니다."
        )

    return description


# ---------------------------------------------------------------------------
# 메인 함수
# ---------------------------------------------------------------------------

def generate_description(
    classification: Classification,
    detailed_signals: DetailedSignals,
    hospital_meta: HospitalMeta,
) -> HospitalDescription:
    """
    분류 결과 + 4 시그널 + 병원 기본 정보를 받아 자연어 통합 상세 설명을 생성.

    Args:
        classification: classify_hospital()의 반환값.
        detailed_signals: 4 시그널 세부 데이터.
        hospital_meta: 병원명·주소 등 기본 정보.

    Returns:
        HospitalDescription: 의료법 5규칙을 통과한 구조화된 설명.

    Raises:
        BedrockInvocationError: Bedrock API 호출 실패.
        DescriptionValidationError: 최대 재시도 후에도 검증 통과 불가.
    """
    generator_model = os.getenv(
        "BEDROCK_LLM_MODEL_ID",
        "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    )
    generated_at = datetime.utcnow()

    last_error: DescriptionValidationError | None = None
    extra_instruction = ""

    for attempt in range(MAX_RETRIES + 1):
        prompt = _build_prompt(
            classification=classification,
            detailed_signals=detailed_signals,
            hospital_meta=hospital_meta,
            extra_instruction=extra_instruction,
        )

        # Bedrock 호출
        try:
            raw_response = invoke_model(prompt=prompt, model_id=generator_model)
        except Exception as e:
            raise BedrockInvocationError(
                f"Bedrock invoke_model 실패 (시도 {attempt + 1}): {e}"
            ) from e

        # JSON 추출
        try:
            raw_text = _extract_json_from_response(raw_response)
        except DescriptionValidationError:
            raise

        # 파싱 + 검증
        try:
            return _parse_and_validate(
                raw_text=raw_text,
                hospital_id=classification.hospital_id,
                generated_at=generated_at,
                generator_model=generator_model,
            )
        except DescriptionValidationError as e:
            last_error = e
            # 다음 재시도 시 실패 원인을 프롬프트에 추가
            extra_instruction = (
                f"이전 시도 {attempt + 1}회차에서 다음 검증 오류가 발생했습니다:\n"
                f"{e}\n\n"
                "위 오류를 반드시 수정하여 다시 출력하십시오. "
                "특히 citations가 비어있으면 안 되고, 약점·주의사항 단락이 필수입니다."
            )
            if attempt < MAX_RETRIES:
                continue

    # 모든 재시도 소진
    raise DescriptionValidationError(
        f"최대 재시도({MAX_RETRIES}회) 후에도 검증 통과 불가. "
        f"마지막 오류: {last_error}"
    )
