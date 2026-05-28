"""Google Places API (New) 어댑터 — 후기 시그널 수집.

공식 Places API (New) 사용:
  - Text Search: POST https://places.googleapis.com/v1/places:searchText
  - Place Details: GET  https://places.googleapis.com/v1/places/{place_id}

무료 tier 의 Place Details `reviews` 필드는 최대 5건. 카카오·네이버와 달리
공식 API 라 robots/약관 회색지대가 아니다 (API 키 + 쿼터 내 합법 사용).

네트워크(fetch_*)와 파싱(parse_*)을 분리했다 — parse_* 는 순수 함수라
저장된 raw JSON 으로 오프라인 테스트 가능 (be/tests/test_google_places_adapter.py).

의료법 §56③: 후기 본문 raw 는 DDB 저장·임베딩 입력으로만, 화면 노출은 키워드 빈도만.
개인정보: 리뷰 작성자(authorAttribution.displayName·photoUri) 는 parse 단계에서 제거.
키워드 빈도는 구글이 제공하지 않으므로(카카오 strength 와 달리) AI 트랙이 후기 본문에서
의료 키워드를 직접 추출해 GoogleReviews.keyword_frequency 를 채운다 (parse 는 빈 dict).
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from shared.models import GoogleReviews

logger = logging.getLogger(__name__)

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"

# Place Details 응답에서 받을 필드만 명시 (FieldMask 필수 — 미지정 시 400, 과금 폭증 방지).
_DETAILS_FIELD_MASK = (
    "id,displayName,formattedAddress,rating,userRatingCount,reviews"
)
# Text Search 는 후보 1개의 id·이름만 (매칭 확인용).
_SEARCH_FIELD_MASK = "places.id,places.displayName,places.formattedAddress"


class GooglePlacesAdapter:
    """Places API (New) Text Search + Details httpx 호출."""

    def __init__(self, api_key: str | None = None, timeout: float = 15.0) -> None:
        self._api_key = api_key or os.environ.get("GOOGLE_PLACES_API_KEY", "")
        self._client = httpx.Client(timeout=timeout)

    def __enter__(self) -> "GooglePlacesAdapter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _headers(self, field_mask: str) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": field_mask,
        }

    def search_place_id(self, name: str, address: str = "") -> str | None:
        """병원명(+주소)으로 Text Search → 첫 후보의 place_id 반환.

        매칭 실패(후보 0개)·키 미설정·HTTP 오류 시 None (배치 graceful).
        """
        if not self._api_key:
            logger.warning("GOOGLE_PLACES_API_KEY 미설정 — 구글 검색 스킵")
            return None
        query = f"{name} {address}".strip()
        try:
            resp = self._client.post(
                SEARCH_URL,
                headers=self._headers(_SEARCH_FIELD_MASK),
                json={"textQuery": query, "languageCode": "ko"},
            )
            resp.raise_for_status()
            places = resp.json().get("places") or []
        except (httpx.HTTPError, ValueError) as exc:
            logger.debug("구글 Text Search 실패 (%s): %s", query, exc)
            return None
        if not places:
            return None
        return places[0].get("id")

    def fetch_details(self, place_id: str) -> dict[str, Any] | None:
        """place_id → Place Details (reviews 포함) raw JSON.

        키 미설정·HTTP 오류·비JSON 시 None.
        """
        if not self._api_key:
            logger.warning("GOOGLE_PLACES_API_KEY 미설정 — 구글 상세 스킵")
            return None
        if not place_id:
            return None
        try:
            resp = self._client.get(
                DETAILS_URL.format(place_id=place_id),
                headers=self._headers(_DETAILS_FIELD_MASK),
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.debug("구글 Place Details 실패 (%s): %s", place_id, exc)
            return None

    def close(self) -> None:
        self._client.close()


# ---------------------------------------------------------------------------
# 순수 파서 (네트워크 없음)
# ---------------------------------------------------------------------------

def _review_text(review: dict[str, Any]) -> str:
    """리뷰 text 필드 추출. Places (New) 는 {text: {text, languageCode}} 구조."""
    text = review.get("text")
    if isinstance(text, dict):
        return (text.get("text") or "").strip()
    if isinstance(text, str):
        return text.strip()
    # originalText 폴백
    orig = review.get("originalText")
    if isinstance(orig, dict):
        return (orig.get("text") or "").strip()
    return ""


def parse_google_reviews(details: dict[str, Any]) -> dict[str, Any]:
    """Place Details raw → DDB GOOGLE#PLACE / GOOGLE#REVIEWS entity.

    작성자(authorAttribution)·절대 작성 시각·리뷰 사진 URL 은 옮기지 않는다 (PII).
    keyword_frequency 는 구글이 제공하지 않으므로 빈 dict — AI 트랙이 후기 본문에서
    의료 키워드를 직접 추출해 채운다.
    """
    display_name = details.get("displayName")
    if isinstance(display_name, dict):
        name = display_name.get("text")
    else:
        name = display_name

    reviews_raw = details.get("reviews") or []
    reviews = [
        {
            "rating": r.get("rating"),
            "text": _review_text(r),
            "relative_time": r.get("relativePublishTimeDescription"),
        }
        for r in reviews_raw
    ]

    return {
        "place_id": details.get("id"),
        "name": name,
        "rating": details.get("rating"),
        "user_ratings_total": details.get("userRatingCount"),
        "keyword_frequency": {},  # AI 트랙이 후기 본문에서 채움
        "reviews": reviews,
    }


def to_google_reviews(parsed: dict[str, Any]) -> "GoogleReviews":
    """parse_google_reviews() dict → GoogleReviews 모델."""
    from shared.models import GoogleReviews
    return GoogleReviews.model_validate(parsed)
