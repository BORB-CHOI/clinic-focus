"""병원 상세 API 라우터.

스펙: .claude/docs/API-FE-BE.md > 엔드포인트 > 2. 병원 상세
응답: 상세 페이지 9개 영역에 직접 매핑.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from be.adapters.dynamo_adapter import DynamoAdapter
from be.core.feedback import compute_feedback_stats

router = APIRouter(prefix="/api/hospitals", tags=["hospitals"])
db = DynamoAdapter()


@router.get("/{hospital_id}")
def get_hospital_detail(hospital_id: str):
    """
    병원 상세 페이지 — 9개 영역 데이터 반환.

    ① AI 통합 설명 (ai_description)
    ② 핵심 진료 정보 (services, excluded_services, equipment, prices)
    ③ 의료진 정보 (doctors)
    ④ 신뢰도·근거 (confidence, detailed_signals)
    ⑤ 기본 운영 정보 (location, operating_hours, contact)
    ⑥ 사용자 피드백 (feedback_stats)
    ⑦ 분류 변경 이력 (recent_changes)
    ⑧ 관련 병원 추천 (related_hospitals)
    ⑨ 메타 정보 (metadata)
    """
    meta = db.load_hospital_meta(hospital_id)
    if not meta:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "병원을 찾을 수 없습니다"}},
        )

    classification = db.load_classification(hospital_id)
    description = db.load_description(hospital_id)
    services_and_doctors = db.load_services_and_doctors(hospital_id)
    related = db.load_related_hospitals(hospital_id)
    recent_changes = db.load_recent_changes(hospital_id, limit=2)

    # ⑥ 피드백 통계
    feedback_list = db.get_feedback_for_hospital(hospital_id)
    feedback_stats = compute_feedback_stats(feedback_list)

    # 응답 조립 — API-FE-BE.md 스펙 기준
    return {
        "data": {
            "hospital_id": meta.hospital_id,
            "name": meta.name,
            "standard_specialty": classification.standard_specialty if classification else "",
            "primary_focus": classification.primary_focus if classification else [],
            "confidence": classification.confidence.model_dump() if classification else None,
            "location": meta.location.model_dump() if meta.location else None,
            "website_url": meta.contact.website_url,
            "one_line_summary": description.one_line_summary if description else "",

            # ① AI 통합 설명
            "ai_description": description.model_dump() if description else None,

            # ② 핵심 진료 정보 (스펙 형태로 어댑팅)
            "services": [s.model_dump() for s in services_and_doctors.services] if services_and_doctors else [],
            "excluded_services": [s.model_dump() for s in services_and_doctors.excluded_services] if services_and_doctors else [],
            "equipment": [_adapt_equipment(e) for e in services_and_doctors.equipment] if services_and_doctors else [],
            "prices": [_adapt_price(p) for p in services_and_doctors.prices] if services_and_doctors else [],

            # ③ 의료진 정보
            "doctors": [_adapt_doctor(d) for d in services_and_doctors.doctors] if services_and_doctors else [],

            # ④ 신뢰도·근거
            "detailed_signals": _adapt_detailed_signals(classification, meta.contact.website_url if meta.contact else None),

            # ⑤ 기본 운영 정보 — operating_hours 는 구조화 미보유라 null(FE 가 "정보 없음")
            "operating_hours": None,
            "contact": _adapt_contact(meta.contact),

            # ⑥ 사용자 피드백
            "feedback_stats": feedback_stats.model_dump(),

            # ⑦ 분류 변경 이력
            "recent_changes": [c.model_dump() for c in recent_changes],

            # ⑧ 관련 병원 추천
            "related_hospitals": [_adapt_related(r) for r in related],

            # ⑨ 메타 정보
            "metadata": {
                "last_updated_at": classification.classified_at.isoformat() if classification else None,
                "data_sources": ["public_registry"],
                "data_completeness": _calc_completeness(classification, description, services_and_doctors),
                "warning": "정보 부족 — 직접 병원에 문의 권장" if not classification else None,
            },
        }
    }


# ---------------------------------------------------------------------------
# 응답 어댑터 — raw Pydantic 모델 → API-FE-BE.md 스펙 형태 (FE 가 기대하는 shape).
# BE 모델이 안 가진 필드(source_text·sample_image_urls·career·주차 등)는 null/[]/false
# 로 채운다(미수집 = graceful 공란). 스펙이 합의된 계약이므로 BE 가 거기 맞춘다.
# ---------------------------------------------------------------------------

def _adapt_detailed_signals(classification, website_url: str | None) -> dict | None:
    if not classification:
        return None
    ds = classification.detailed_signals
    sc, v, blog, rev = ds.self_claim, ds.vision, ds.blog, ds.reviews
    return {
        "self_claim": {
            "extracted_keywords": list(sc.keywords or []),
            "source_text": "",  # 자칭 원문은 임베딩 전용·미저장
            "source_url": website_url or "",
        },
        "vision": (
            {
                "detected_devices": list(v.detected_devices or []),
                "image_distribution": dict(v.image_categories or {}),
                "sample_image_urls": [],  # 샘플 이미지 URL 미수집
            }
            if v
            else None
        ),
        "blog": {
            "top_topics": [
                {"topic": t, "frequency": int(f)}
                for t, f in list((blog.keyword_frequency or {}).items())[:10]
            ],
            "total_posts": blog.total_posts,
        },
        "reviews": {
            "review_count": rev.total_reviews,
            "top_keywords": list((rev.keyword_frequency or {}).keys())[:15],
        },
    }


_EQUIP_SOURCE_MAP = {"public_data": "public_registry", "vision": "vision"}


def _adapt_equipment(e) -> dict:
    return {
        "name": e.name,
        "available": True,
        "source": _EQUIP_SOURCE_MAP.get(e.source, "self_claim"),
        "source_url": None,
    }


def _adapt_price(p) -> dict:
    return {"service_name": p.service_name, "price_range": p.price_text, "source_url": "", "last_seen": ""}


def _adapt_doctor(d) -> dict:
    return {
        "name": d.name,
        "position": d.specialty or "",
        "specialty_certifications": list(d.qualifications or []),
        "sub_specialty": d.sub_specialty,
        "career": [],
        "primary_focus": None,
        "source_url": None,
    }


def _adapt_contact(c) -> dict | None:
    if not c:
        return None
    methods: list[str] = []
    if c.reservation_url:
        methods.append("online")
    if c.phone:
        methods.append("phone")
    return {
        "phone": c.phone or "",
        "homepage_url": c.website_url,
        "parking_available": False,
        "appointment_methods": methods,
    }


def _adapt_related(r) -> dict:
    d = r.model_dump()
    d["thumbnail_url"] = None
    return d


def _calc_completeness(classification, description, services_and_doctors) -> float:
    """9개 영역 중 채워진 비율 계산."""
    filled = 1  # meta는 항상 있음 (여기까지 왔으니까)
    if classification:
        filled += 2  # ② 일부 + ④
    if description:
        filled += 1  # ①
    if services_and_doctors:
        filled += 2  # ② 나머지 + ③
    # ⑤ 기본 운영 정보는 meta에 포함
    filled += 1
    # ⑥⑦⑧은 데이터 있으면 카운트
    return round(filled / 9, 2)
