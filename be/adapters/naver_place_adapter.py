"""네이버 플레이스 비공식 GraphQL 어댑터 — 방문자 후기 시그널(후기 25% 한 축).

네이버 플레이스 후기는 공식 API 가 없고 `pcmap-api.place.naver.com/graphql`
(getVisitorReviews) 비공식 엔드포인트만 존재한다. 이 엔드포인트는 ncpt 토큰을
요구해 httpx 단독 호출이 차단되므로, Playwright headless Chromium 으로 상세
페이지에 진입해 SDK 가 토큰을 자동 발급하게 한 뒤 page.evaluate 로 fetch 한다
(실측: 1건당 18~25초). 흐름·실측 근거는 task-queue.md "Phase B 후기 시그널 전략"
박스의 사실 1~9 + ai/scratch/naver-place-probe-2026-05-28/ 참조.

⚠️ 회색지대 — `pcmap.place.naver.com`·`pcmap-api.place.naver.com` 은 robots.txt
   자동화 금지 + 네이버 약관이 자동 수집을 금지한다. fetch_* 는 시연 표본 한정으로만
   돌린다 (1만 풀커버 미적용 — IP rate-limit 미실측). 실행 여부는 운영자 결정.

네트워크(fetch — Playwright)와 파싱(parse — 순수 함수)을 분리해, parse_* 는
저장된 raw JSON 으로 오프라인 단위 테스트가 가능하다 (Playwright 미설치 환경 포함).

의료법 §56③: 후기 본문(body) raw 는 DDB 저장·임베딩 입력으로만, 화면 노출은
키워드 빈도만. 작성자(author·userIdno·loginIdno·nickname)는 parse 단계에서 제거한다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from shared.models import NaverPlace

logger = logging.getLogger(__name__)

_QUERY_DIR = Path(__file__).parent / "naver_queries"
_GRAPHQL_URL = "https://pcmap-api.place.naver.com/graphql"
_DETAIL_URL = "https://pcmap.place.naver.com/hospital/{pid}/review/visitor"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# 병원,의원 카테고리 ID (실측 사실 8 — 사용자 캡처 cidList 그대로).
_CID_LIST = ["223175", "223176", "223192", "228995"]

# place_id 는 네이버 내부 정수 식별자. 경로/변수에 직접 박히므로 정수만 허용.
_PLACE_ID_RE = re.compile(r"^\d+$")


def _load_query(name: str) -> str:
    """GraphQL 쿼리 파일 로드 (# 주석 줄 제거)."""
    text = (_QUERY_DIR / name).read_text(encoding="utf-8")
    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))


class NaverPlaceAdapter:
    """Playwright headless Chromium 으로 ncpt 토큰 자동 발급 → graphql 후기 수집.

    Playwright 는 무거운 선택적 의존성이라 import 를 fetch 시점까지 지연한다
    (parse_* 만 쓰는 테스트·환경에서는 Playwright 불필요).
    """

    def __init__(self, *, timeout_ms: int = 40000, settle_ms: int = 6000) -> None:
        self._timeout_ms = timeout_ms
        self._settle_ms = settle_ms  # 상세 진입 후 SDK 토큰 발급 대기

    async def fetch_reviews(self, place_id: str, size: int = 10) -> dict[str, Any] | None:
        """place_id 의 방문자 후기 raw(graphql 응답)를 반환. 실패 시 None.

        Playwright 미설치·차단·타임아웃·비정상 place_id 시 None (배치 graceful).
        """
        if not _PLACE_ID_RE.match(place_id):
            logger.warning("거부된 place_id (정수 아님): %r", place_id)
            return None
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("playwright 미설치 — 네이버 플레이스 후기 수집 스킵")
            return None

        payload = [
            {
                "operationName": "getVisitorReviews",
                "variables": {
                    "input": {
                        "businessId": place_id,
                        "bookingBusinessId": None,
                        "businessType": "hospital",
                        "cidList": _CID_LIST,
                        "includeContent": True,
                        "size": size,
                    }
                },
                "query": _load_query("visitor_reviews.graphql"),
            },
        ]

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
                )
                try:
                    ctx = await browser.new_context(
                        user_agent=_UA, viewport={"width": 1280, "height": 900}, locale="ko-KR"
                    )
                    page = await ctx.new_page()
                    # 상세 진입 → ncpt SDK 가 토큰 자동 발급 + 세션 쿠키 굳히기
                    await page.goto(
                        _DETAIL_URL.format(pid=place_id),
                        wait_until="domcontentloaded",
                        timeout=self._timeout_ms,
                    )
                    await page.wait_for_timeout(self._settle_ms)
                    result = await page.evaluate(
                        """async ([url, body]) => {
                            const r = await fetch(url, {
                                method: "POST",
                                headers: {"Content-Type": "application/json"},
                                credentials: "include",
                                body: JSON.stringify(body),
                            });
                            return {status: r.status, text: await r.text()};
                        }""",
                        [_GRAPHQL_URL, payload],
                    )
                finally:
                    await browser.close()
        except (asyncio.TimeoutError, OSError, ValueError) as exc:
            # 차단·타임아웃·네트워크·비JSON — 배치 graceful 스킵
            logger.debug("네이버 플레이스 후기 수집 실패 (%s): %s", place_id, exc)
            return None
        except Exception as exc:
            # 예상 밖 오류는 원인 추적 위해 warning (Playwright 내부 오류 등)
            logger.warning(
                "네이버 플레이스 예상 밖 오류 (%s): %s: %s",
                place_id, type(exc).__name__, exc,
            )
            return None

        if result.get("status") != 200:
            logger.debug("네이버 graphql 비정상 응답 (%s): HTTP %s", place_id, result.get("status"))
            return None
        try:
            return json.loads(result["text"])
        except (ValueError, KeyError):
            return None


# ---------------------------------------------------------------------------
# 순수 파서 (네트워크 없음) — 저장된 raw 로 단위 테스트
# ---------------------------------------------------------------------------

def _extract_visitor_reviews(graphql_json: Any) -> dict[str, Any]:
    """graphql 응답(list[entry])에서 visitorReviews 블록을 찾아 반환."""
    if isinstance(graphql_json, list):
        for entry in graphql_json:
            data = (entry or {}).get("data") or {}
            if data.get("visitorReviews"):
                return data["visitorReviews"]
    elif isinstance(graphql_json, dict):
        data = graphql_json.get("data") or {}
        if data.get("visitorReviews"):
            return data["visitorReviews"]
    return {}


def parse_place(graphql_json: Any, place_id: str) -> dict[str, Any]:
    """visitorReviews raw → DDB `NAVER#PLACE#REVIEWS` entity (NaverPlace 형태).

    후기 본문(body)은 보존(임베딩 입력)하되 작성자 PII(author·userIdno·loginIdno·
    nickname)는 옮기지 않는다. keyword_stats 는 네이버가 병원 카테고리 통계를 주지
    않으므로(실측 사실 8) 빈 dict — AI 트랙이 후기 본문에서 직접 추출한다.
    """
    vr = _extract_visitor_reviews(graphql_json)
    items = vr.get("items") or []
    review_bodies = [
        {"body": (it.get("body") or "").strip(), "visit_count": it.get("visitCount")}
        for it in items
        if (it.get("body") or "").strip()
    ]
    return {
        "place_id": place_id,
        "visitor_count": vr.get("total"),
        "keyword_stats": {},          # AI 트랙이 후기 본문에서 추출
        "blog_seeds": [],             # photoViewer ugc 경로는 별도 (미수집)
        # 후기 본문 raw — 임베딩 입력용. NaverPlace 모델엔 없지만 DDB 저장엔 보존.
        "reviews": review_bodies,
    }


def to_naver_place(parsed: dict[str, Any]) -> "NaverPlace":
    """parse_place() dict → NaverPlace 모델 (모델에 없는 reviews 키는 extra=ignore)."""
    from shared.models import NaverPlace
    return NaverPlace.model_validate(parsed)


def fetch_reviews_sync(place_id: str, size: int = 10) -> dict[str, Any] | None:
    """fetch_reviews 동기 래퍼 — **배치 스크립트 전용**.

    ⚠️ 이미 실행 중인 event loop 안(FastAPI async 핸들러 등)에서 호출하면
    asyncio.run() 이 RuntimeError 를 던진다. FastAPI 경로에서는 async fetch_reviews
    를 직접 await 할 것. 검색(retrieve_hospital)·크롤은 경로가 분리돼 있어 실제로
    이 함수는 crawl_external_all 배치에서만 호출된다.
    """
    return asyncio.run(NaverPlaceAdapter().fetch_reviews(place_id, size))
