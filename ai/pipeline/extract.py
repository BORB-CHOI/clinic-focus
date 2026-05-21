import json
import os

from ai.core import bedrock_client
from ai.core.exceptions import BedrockInvocationError, InsufficientDataError
from shared.models import (
    Classification,
    CrawlData,
    Doctor,
    Equipment,
    ExcludedService,
    ImageAnalysisResult,
    PriceItem,
    Service,
    ServicesAndDoctors,
)

_SPECIALTY_DEFAULT_SERVICES: dict[str, list[str]] = {
    "피부과": ["미용 시술", "일반 진료(아토피·여드름)", "피부암·종양", "모발·탈모"],
    "정형외과": ["척추", "어깨·견관절", "무릎·관절", "손·발(수부외과)", "스포츠 의학"],
    "이비인후과": ["알레르기·비염", "청각·이명", "코·수면호흡", "갑상선"],
    "안과": ["라식·라섹", "백내장", "망막", "일반 시력"],
}


def _build_prompt(crawl_data: CrawlData, classification: Classification) -> str:
    page_texts = "\n\n".join(
        f"[{p.page_type.upper()}] {p.html_text[:2000]}"
        for p in crawl_data.pages
        if p.html_text.strip()
    )
    public_data = crawl_data.public_data
    public_devices = ", ".join(public_data.registered_devices) if public_data else "없음"
    specialists = ", ".join(public_data.specialists) if public_data else "없음"
    primary_focus = ", ".join(classification.primary_focus)
    all_services = ", ".join(
        _SPECIALTY_DEFAULT_SERVICES.get(classification.standard_specialty, [])
    )

    return f"""다음은 한국 {classification.standard_specialty} 병원 웹사이트의 텍스트입니다.

=== 병원 웹사이트 텍스트 ===
{page_texts}

=== 심평원 공공 데이터 ===
등록 의료기기: {public_devices}
전문의 자격: {specialists}

=== AI 분류 결과 ===
주력 분야: {primary_focus}
진료과목: {classification.standard_specialty}

위 정보를 바탕으로 아래 JSON을 추출해줘. 확신하지 못하는 항목은 빈 리스트로 두고 절대 추측하지 마.

{{
  "services": [
    {{"name": "진료 항목명", "category": "분류", "source": "self_claim|vision|blog|reviews|public_data"}}
  ],
  "excluded_services": [
    {{"name": "{all_services} 중 이 병원이 다루지 않는 항목", "reason": "판단 근거"}}
  ],
  "equipment": [
    {{"name": "의료기기명", "source": "vision|public_data", "confidence": 0.0~1.0}}
  ],
  "prices": [
    {{"service_name": "시술명", "price_text": "가격 원문"}}
  ],
  "doctors": [
    {{"name": "의사명", "specialty": "전문과목", "qualifications": ["자격증 목록"], "sub_specialty": "세부 전공"}}
  ]
}}

JSON만 반환. 설명 없이."""


def extract_services_and_doctors(
    crawl_data: CrawlData,
    classification: Classification,
    vision_results: list[ImageAnalysisResult],
) -> ServicesAndDoctors:
    """크롤링 데이터에서 상세 페이지 영역 ②③ 구성 데이터를 추출."""
    all_texts = [p.html_text for p in crawl_data.pages if p.html_text.strip()]
    if not all_texts:
        raise InsufficientDataError(f"hospital_id={crawl_data.hospital_id}: 추출 가능한 텍스트 없음")

    prompt = _build_prompt(crawl_data, classification)

    try:
        response = bedrock_client.invoke_model(prompt)
        raw_text: str = response["content"][0]["text"].strip()
    except Exception as e:
        raise BedrockInvocationError(f"Bedrock 호출 실패: {e}") from e

    # JSON 블록 파싱
    if "```" in raw_text:
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        data = {}

    # Vision 결과에서 의료기기 병합
    vision_devices: list[Equipment] = [
        Equipment(name=d, source="vision", confidence=r.confidence)
        for r in vision_results
        for d in r.detected_devices
    ]

    # 심평원 공공 데이터 의료기기 병합
    public_devices: list[Equipment] = [
        Equipment(name=d, source="public_data", confidence=1.0)
        for d in (crawl_data.public_data.registered_devices if crawl_data.public_data else [])
    ]

    # 중복 제거 (같은 이름이면 confidence 높은 쪽 유지)
    device_map: dict[str, Equipment] = {}
    for eq in public_devices + vision_devices:
        if eq.name not in device_map or eq.confidence > device_map[eq.name].confidence:
            device_map[eq.name] = eq

    llm_equipment: list[Equipment] = [
        Equipment(**e) for e in data.get("equipment", [])
        if e.get("name") and e.get("name") not in device_map
    ]
    all_equipment = list(device_map.values()) + llm_equipment

    return ServicesAndDoctors(
        services=[Service(**s) for s in data.get("services", [])],
        excluded_services=[ExcludedService(**e) for e in data.get("excluded_services", [])],
        equipment=all_equipment,
        prices=[PriceItem(**p) for p in data.get("prices", [])],
        doctors=[Doctor(**d) for d in data.get("doctors", [])],
    )
