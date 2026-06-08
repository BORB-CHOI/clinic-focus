"""병원 상세 API 라우터.

스펙: .claude/docs/API-FE-BE.md > 엔드포인트 > 2. 병원 상세
응답: 상세 페이지 9개 영역에 직접 매핑.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from be.adapters.dynamo_adapter import DynamoAdapter
from be.adapters.s3_adapter import S3Adapter
from be.core.feedback import compute_feedback_stats
from shared.etc_category import display_specialty

router = APIRouter(prefix="/api/hospitals", tags=["hospitals"])
db = DynamoAdapter()
s3 = S3Adapter()


@router.get("/{hospital_id}/thumbnail")
def get_hospital_thumbnail(hospital_id: str):
    """병원 대표 이미지(홈페이지 스크린샷) 스트리밍.

    S3 크롤 버킷이 public-access 차단이라 외부 직접노출이 안 돼 BE 가 중계한다.
    카카오/네이버 대표사진은 외부 CDN URL 을 thumbnail_url 에 직접 넣으므로 이 경로를
    안 탄다 — 이 엔드포인트는 우리가 찍어 S3 에 올린 스크린샷 전용. 없으면 404
    (FE HospitalThumbnail 이 onError 로 회색 플레이스홀더 폴백).
    """
    data = s3.load_thumbnail(hospital_id)
    if not data:
        raise HTTPException(status_code=404, detail="thumbnail not found")
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


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

    # 심평원 공공 데이터 (③ 의료진 보강·비급여 신규 영역)
    public_doctors = db.load_public_doctors(hospital_id)
    public_nonpay = db.load_public_nonpay(hospital_id)

    # ⑥ 피드백 통계
    feedback_list = db.get_feedback_for_hospital(hospital_id)
    feedback_stats = compute_feedback_stats(feedback_list)

    # 응답 조립 — API-FE-BE.md 스펙 기준
    return {
        "data": {
            "hospital_id": meta.hospital_id,
            "name": meta.name,
            "standard_specialty": classification.standard_specialty if classification else "",
            "etc_subcategory": (
                display_specialty(classification.standard_specialty, classification.primary_focus)
                if classification else ""
            ),
            "primary_focus": classification.primary_focus if classification else [],
            "confidence": classification.confidence.model_dump() if classification else None,
            # 헤드라이너 히어로 + 카드 좌측 썸네일 동일 출처. None 이면 그라데이션 플레이스홀더.
            "thumbnail_url": meta.thumbnail_url,
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

            # ③ 의료진 정보 + 심평원 신고 기준 전문의 수
            "doctors": [_adapt_doctor(d) for d in services_and_doctors.doctors] if services_and_doctors else [],
            # 심평원 신고 기준 과목별 전문의 수 {"피부과": 2, ...}. 출처: 심평원 공식 신고(public_data).
            # "이 병원이 잘 본다" 아닌 "심평원 신고 기준 N명" 형식으로 FE 렌더 필요(의료법 주체 명시).
            "specialists_by_dept": public_doctors.get("specialists_by_dept", {}),
            # 총 의사 수(getDtlInfo2.7). None 이면 미확인.
            "total_doctors": public_doctors.get("total_doctors"),

            # (신규) 심평원 신고 비급여 항목 — 의료법 제45조의2 공식 신고 사실 그대로 노출.
            # "병원이 신고한 비급여 항목"(주체 명시). 분류 신호 편입 금지, 표시·필터 전용.
            "nonpay_items": [item.model_dump() for item in public_nonpay],

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
    # self_claim 은 아래에서 classification.primary_focus 로 대체 노출하므로 ds.self_claim 미사용.
    v, blog, rev = ds.vision, ds.blog, ds.reviews
    return {
        "self_claim": {
            # 정제된 주력(primary_focus)을 자칭 컨셉으로 노출. raw sc.keywords 는 자기 사이트의
            # 블로그/FAQ 문맥어(예: 탈모약 부작용 FAQ의 '당뇨·기형아·분만')까지 섞여 오인 소지 →
            # 빈도·교차검증 거친 primary_focus 로 대체(분류 노이즈가 상세 화면에 그대로 노출되는 것 방지).
            "extracted_keywords": list(classification.primary_focus or []),
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
    # 관련 병원 카드 — 이름·대표 이미지를 META 에서 조인(≤5건). find_related_hospitals 는
    # name="" 로 두고 "BE 가 조인"하기로 한 계약이라, 여기서 이름을 안 채우면 FE 가 빈 이름
    # 대신 hospital_id(raw) 를 노출한다(관측된 'ID 가 왜 여기' 버그).
    rel_meta = db.load_hospital_meta(r.hospital_id)
    if rel_meta:
        if not (d.get("name") or "").strip():
            d["name"] = rel_meta.name
        d["thumbnail_url"] = rel_meta.thumbnail_url
    else:
        d["thumbnail_url"] = None
    # primary_focus literal 따옴표 정규화(적재 데이터 오염 방지).
    if isinstance(d.get("primary_focus"), list):
        d["primary_focus"] = [
            str(f).strip().strip('"').strip("'").strip()
            for f in d["primary_focus"] if str(f).strip()
        ]
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
