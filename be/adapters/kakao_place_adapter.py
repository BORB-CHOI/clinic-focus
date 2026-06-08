"""카카오맵 비공식 place-api 어댑터 — 상세·후기·블로그 시그널 수집.

공식 `dapi.kakao.com` 검색(`KakaoAdapter`)이 돌려주는 place_id 를 받아
`place-api.map.kakao.com` 의 3 엔드포인트에서 상세·후기·블로그 raw 를 가져와
DDB 적재용 구조(KAKAO#PLACE / KAKAO#REVIEWS / KAKAO#BLOG)로 정제한다.

⚠️  회색지대 — `place-api.map.kakao.com` 은 robots.txt 자동화 금지 대상이고
   카카오 약관도 비정상 접근을 금지한다. fetch_* 는 **시연 표본(약 500개) 한정**으로만
   돌린다 (1만 풀커버 미적용 — rate-limit 미실측). 실측 근거·정책은
   `docs/plans/task-queue.md` "Phase B 후기 시그널 전략" 박스 사실 13~24 참조.

네트워크(fetch_*)와 파싱(parse_*)을 분리했다 — parse_* 는 순수 함수라
저장된 raw JSON 으로 오프라인 테스트 가능 (`be/tests/test_kakao_place_adapter.py`).

의료법 §56③: 후기·블로그 본문 raw 는 DDB 저장·임베딩 입력으로만 쓰고
화면 노출은 키워드 빈도(strength_counts)만. 본문 노출 금지.
개인정보: 후기 작성자 owner(map_user_id·nickname·profile_image_url)·블로그 author 는
정제 단계에서 제거한다 (네이버와 달리 카카오는 서버 마스킹이 없어 raw 노출됨).
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

import httpx

if TYPE_CHECKING:
    from shared.models import KakaoBlog, KakaoPlace, KakaoReviews

logger = logging.getLogger(__name__)

PANEL3_URL = "https://place-api.map.kakao.com/places/panel3/{pid}"
REVIEWS_URL = "https://place-api.map.kakao.com/places/tab/reviews/kakaomap/{pid}"
BLOG_URL = "https://place-api.map.kakao.com/places/tab/reviews/blog/{pid}"

# place_id 는 카카오 내부 정수 식별자. URL 경로에 직접 박히므로 정수만 허용
# (경로 조작·SSRF 방어). 호출자가 비정상 값을 주면 fetch_* 가 None 으로 스킵.
_PLACE_ID_RE = re.compile(r"^\d+$")

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# score_set.strength_counts 의 id → 라벨. 카테고리 무관 고정 4종 (사실 18).
STRENGTH_LABELS: dict[int, str] = {13: "가격", 10: "전문성", 2: "친절", 4: "주차"}

# summary.homepages 에 섞여 오는 SNS·블로그·카페 호스트 — 병원 자체 홈페이지가 아님.
_NON_HOMEPAGE_HOSTS = (
    "blog.naver.com",
    "cafe.naver.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "youtu.be",
    "pf.kakao.com",
    "twitter.com",
    "x.com",
    "band.us",
)


class KakaoPlaceAdapter:
    """place-api.map.kakao.com 3 엔드포인트 httpx 단발 호출 (ncpt 불필요)."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._client = httpx.Client(timeout=timeout)

    def __enter__(self) -> "KakaoPlaceAdapter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @staticmethod
    def _headers(place_id: str) -> dict[str, str]:
        # Referer/Origin/pf 누락 시 406. 검색과 달리 place-api 는 헤더 셋만 맞으면 통과.
        return {
            "User-Agent": _UA,
            "Referer": f"https://place.map.kakao.com/{place_id}",
            "Origin": "https://place.map.kakao.com",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "pf": "web",
        }

    def fetch_panel3(self, place_id: str) -> dict[str, Any] | None:
        return self._get(PANEL3_URL, place_id)

    def fetch_reviews(
        self,
        place_id: str,
        *,
        order: str = "RECOMMENDED",
        only_photo_review: bool = False,
    ) -> dict[str, Any] | None:
        params = {
            "order": order,
            "only_photo_review": "true" if only_photo_review else "false",
        }
        return self._get(REVIEWS_URL, place_id, params=params)

    def fetch_blog(self, place_id: str, page: int = 1) -> dict[str, Any] | None:
        return self._get(BLOG_URL, place_id, params={"page": page})

    def _get(
        self,
        url_template: str,
        place_id: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if not _PLACE_ID_RE.match(place_id):
            logger.warning("거부된 place_id (정수 아님): %r", place_id)
            return None
        url = url_template.format(pid=place_id)
        try:
            resp = self._client.get(url, headers=self._headers(place_id), params=params)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            # 회색지대 API — 차단·타임아웃·비JSON 응답 시 조용히 스킵 (배치 크롤 graceful)
            logger.debug("카카오 place-api 호출 실패 (%s): %s", place_id, exc)
            return None

    def close(self) -> None:
        self._client.close()


# ---------------------------------------------------------------------------
# 순수 파서 (네트워크 없음) — 저장된 raw 로 단위 테스트
# ---------------------------------------------------------------------------

def extract_homepage(panel3: dict[str, Any]) -> str | None:
    """summary.homepages 에서 병원 자체 홈페이지 1개 선별.

    SNS·블로그·카페 호스트는 건너뛰고 첫 자체 도메인 URL 을 고른다.
    자체 도메인이 하나도 없으면 첫 항목으로 폴백.
    (옛 Playwright 렌더러가 하던 홈페이지 추출을 httpx panel3 응답 파싱으로 대체.)
    """
    homepages = ((panel3.get("summary") or {}).get("homepages")) or []
    urls = [h for h in homepages if isinstance(h, str) and h.startswith(("http://", "https://"))]
    if not urls:
        return None
    for url in urls:
        host = urlsplit(url).netloc.lower()
        host = host[4:] if host.startswith("www.") else host
        if not any(host == bad or host.endswith("." + bad) or host == bad.replace("www.", "")
                   for bad in _NON_HOMEPAGE_HOSTS):
            return url
    return urls[0]


def _representative_image(panel3: dict[str, Any]) -> str | None:
    """FE 대표 이미지 URL 1개. 사업자 공식 사진 우선, 없으면 사진 배열 폴백.

    `my_store_notice.main_photo_url` = 사업자 본인 설정(PII 없음) → 최우선.
    폴백 `photos.photos[].url` 은 후기 사진이라 owner 메타는 버리고 URL 만 사용.
    """
    notice = panel3.get("my_store_notice")
    main = notice.get("main_photo_url") if isinstance(notice, dict) else None
    if isinstance(main, str) and main.startswith(("http://", "https://")):
        return main
    photos_block = panel3.get("photos")
    photos = photos_block.get("photos") if isinstance(photos_block, dict) else None
    for p in photos or []:
        url = p.get("url") if isinstance(p, dict) else None
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            return url
    return None


def _flatten_address(address: Any) -> str | None:
    """summary.address(dict 또는 str) → 표시용 문자열 1개.

    카카오는 address 를 {disp·road·jibun·...} dict 로 준다. disp(표시 주소) 우선,
    없으면 road → jibun 폴백. 이미 문자열이면 그대로.
    """
    if isinstance(address, str):
        return address or None
    if isinstance(address, dict):
        for key in ("disp", "road", "jibun"):
            val = address.get(key)
            if isinstance(val, str) and val.strip():
                return val
    return None


def _flatten_phones(phone_numbers: Any) -> list[str]:
    """summary.phone_numbers([{tel: ...}] 또는 [str]) → 전화번호 문자열 리스트."""
    result: list[str] = []
    for item in phone_numbers or []:
        if isinstance(item, str) and item.strip():
            result.append(item)
        elif isinstance(item, dict):
            tel = item.get("tel")
            if isinstance(tel, str) and tel.strip():
                result.append(tel)
    return result


def parse_place(panel3: dict[str, Any], place_id: str) -> dict[str, Any]:
    """panel3 raw → DDB `KAKAO#PLACE` entity.

    자칭 시그널: place_add_info.tags + my_store_notice.mystore_intro.
    공공 데이터: medical.hira (보조 — HIRA 직접 호출이 우선, 사실 21).
    FE 대표 이미지: representative_image_url.
    """
    summary = panel3.get("summary") or {}
    category = summary.get("category") or {}
    add_info = panel3.get("place_add_info") or {}
    medical = panel3.get("medical") or {}
    hira = medical.get("hira") or {}
    photos = panel3.get("photos") or {}
    notice = panel3.get("my_store_notice") or {}
    km_review = panel3.get("kakaomap_review") or {}
    score_set = km_review.get("score_set") or {}

    return {
        "place_id": place_id,
        "name": summary.get("name"),
        "address": _flatten_address(summary.get("address")),
        "phone_numbers": _flatten_phones(summary.get("phone_numbers")),
        "homepage_url": extract_homepage(panel3),
        "homepages_raw": (summary.get("homepages") or []),
        "category": {
            "full": category.get("name"),
            "depth1": category.get("name1"),
            "depth2": category.get("name2"),
            "depth3": category.get("name3"),
        },
        # 자칭 키워드 시드 (분류기 primary_focus 입력 — 사실 20)
        "tags": add_info.get("tags") or [],
        "facilities": add_info.get("facilities") or {},
        "mystore_intro": notice.get("mystore_intro"),
        # 공공 데이터 보조본
        "hira": {
            "medical_center_type": hira.get("medical_center_type"),
            "specialized_field": hira.get("specialized_field"),
            "doctor_count": hira.get("doctor_count") or {},
            "established_at": hira.get("established_at"),
        } if hira else {},
        # FE 대표 이미지 (Vision 입력 아님)
        "representative_image_url": _representative_image(panel3),
        "photo_counts": photos.get("counts") or {},
        # 후기 요약 (panel3 내장분 — 더서울 케이스는 null 가능)
        "review_count": score_set.get("review_count"),
        "average_score": score_set.get("average_score"),
    }


def _mask_review_item(item: dict[str, Any]) -> dict[str, Any]:
    """후기 1건 정제 — 본문 raw 유지, owner PII 제거.

    화이트리스트 방식: 아래 6개 안전 필드만 새 dict 로 옮긴다. raw item 의
    `meta.owner`(map_user_id·nickname·profile_image_url)·`photos`(사진별 owner 메타)
    는 옮기지 않으므로 자동 제외 — raw 구조가 바뀌어도 새 필드는 새지 않는다.
    """
    strength_ids = item.get("strength_ids") or []
    return {
        "review_id": item.get("review_id"),
        "contents": item.get("contents") or "",
        "star_rating": item.get("star_rating"),
        "strength_labels": [STRENGTH_LABELS.get(sid, str(sid)) for sid in strength_ids],
        "photo_count": item.get("photo_count") or 0,
        "registered_at": item.get("registered_at"),
    }


def parse_reviews(reviews_json: dict[str, Any]) -> dict[str, Any]:
    """reviews raw → DDB `KAKAO#REVIEWS` entity.

    strength_counts 를 라벨 빈도로 환산 (화면 노출 가능한 키워드 빈도).
    본문 raw 는 DDB 저장·임베딩 입력으로만 (의료법 §56③ — 화면 노출 금지).
    owner PII 제거.
    """
    score_set = reviews_json.get("score_set") or {}
    counts = score_set.get("strength_counts") or []
    keyword_frequency = {
        STRENGTH_LABELS.get(c["id"], str(c["id"])): c["count"]
        for c in counts
        if "id" in c and "count" in c
    }
    items = reviews_json.get("reviews") or []
    return {
        "total_reviews": score_set.get("review_count"),
        "average_score": score_set.get("average_score"),
        "keyword_frequency": keyword_frequency,
        "reviews": [_mask_review_item(it) for it in items],
        "has_next": reviews_json.get("has_next", False),
    }


def parse_blog(blog_json: dict[str, Any]) -> dict[str, Any]:
    """blog raw → DDB `KAKAO#BLOG` entity.

    origin_url = BlogSignal 시드 (100% blog.naver.com — 사실 19).
    발췌 본문은 키워드 추출 입력으로만. author PII 제거.
    """
    items = blog_json.get("reviews") or []
    seeds = [
        {
            "review_id": it.get("review_id"),
            "title": it.get("title") or "",
            "contents": it.get("contents") or "",
            "origin_url": it.get("origin_url"),
            "photo_count": it.get("photo_count") or 0,
            "registered_at": it.get("registered_at"),
        }
        for it in items
    ]
    return {
        "total_posts": blog_json.get("review_count"),
        "seeds": seeds,
    }


# ---------------------------------------------------------------------------
# 모델 승격 — parse_* dict 를 shared Pydantic 모델로 변환
#
# parse_* 는 DDB 적재(dict 필요)·오프라인 테스트 호환을 위해 dict 를 유지한다.
# to_kakao_* 는 경계(핸들러·AI 소비 시점)에서 타입 검증을 거는 승격 경로.
# kb_store/classify 는 dict·모델 둘 다 받으므로 어느 쪽을 넘겨도 동작한다.
# ---------------------------------------------------------------------------

def to_kakao_place(parsed: dict[str, Any]) -> "KakaoPlace":
    """parse_place() dict → KakaoPlace 모델."""
    from shared.models import KakaoPlace
    return KakaoPlace.model_validate(parsed)


def to_kakao_reviews(parsed: dict[str, Any]) -> "KakaoReviews":
    """parse_reviews() dict → KakaoReviews 모델."""
    from shared.models import KakaoReviews
    return KakaoReviews.model_validate(parsed)


def to_kakao_blog(parsed: dict[str, Any]) -> "KakaoBlog":
    """parse_blog() dict → KakaoBlog 모델."""
    from shared.models import KakaoBlog
    return KakaoBlog.model_validate(parsed)
