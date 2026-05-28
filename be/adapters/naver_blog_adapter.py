"""네이버 블로그 검색 어댑터 — 블로그 시그널(20%) 수집.

공식 검색 API `openapi.naver.com/v1/search/blog` 사용 (NaverMapAdapter 와 동일 키
`NAVER_MAP_CLIENT_ID/SECRET` — 변수명만 _MAP 이고 실제로는 검색 API 키).
공식 API 라 robots/약관 회색지대 아님. Playwright 불필요(httpx 단발).

네트워크(fetch)와 파싱(parse)을 분리 — parse_* 는 순수 함수라 저장된 raw 로
오프라인 테스트 가능.

의료법 §56③: 블로그 발췌 본문(description)은 DDB 저장·임베딩 입력으로만,
화면 노출은 키워드 빈도만. 작성자(bloggername·bloggerlink)는 parse 단계에서 제거.
"""

from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from shared.models import NaverBlog

logger = logging.getLogger(__name__)

BLOG_SEARCH_URL = "https://openapi.naver.com/v1/search/blog.json"

# 검색 API 응답의 title/description 은 <b>키워드</b> 강조 태그 + HTML 엔티티 포함.
_TAG_RE = re.compile(r"<[^>]+>")
_ENTITY = {"&lt;": "<", "&gt;": ">", "&amp;": "&", "&quot;": '"', "&#39;": "'"}


class NaverBlogAdapter:
    """v1/search/blog httpx 단발 호출 (공식 API)."""

    def __init__(self, timeout: float = 10.0) -> None:
        self._client = httpx.Client(timeout=timeout)
        self._client_id = os.environ.get("NAVER_MAP_CLIENT_ID", "")
        self._client_secret = os.environ.get("NAVER_MAP_CLIENT_SECRET", "")

    def __enter__(self) -> "NaverBlogAdapter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        return {
            "X-Naver-Client-Id": self._client_id,
            "X-Naver-Client-Secret": self._client_secret,
        }

    def fetch_blog(
        self,
        hospital_name: str,
        region: str = "",
        display: int = 30,
    ) -> dict[str, Any] | None:
        """`{병원명} {지역}` 쿼리로 블로그 검색. raw JSON 반환.

        키 미설정·HTTP 오류·비JSON 시 None (배치 graceful).
        """
        if not self._client_id or not self._client_secret:
            logger.warning("NAVER 검색 API 키 미설정 — 블로그 검색 스킵")
            return None
        query = f"{hospital_name} {region}".strip()
        try:
            resp = self._client.get(
                BLOG_SEARCH_URL,
                headers=self._headers(),
                params={"query": query, "display": min(display, 100), "sort": "sim"},
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.debug("네이버 블로그 검색 실패 (%s): %s", query, exc)
            return None

    def close(self) -> None:
        self._client.close()


# ---------------------------------------------------------------------------
# 순수 파서 (네트워크 없음)
# ---------------------------------------------------------------------------

def _strip_html(text: str) -> str:
    """검색 API 응답의 <b> 강조 태그·HTML 엔티티 제거."""
    if not text:
        return ""
    text = _TAG_RE.sub("", text)
    for ent, ch in _ENTITY.items():
        text = text.replace(ent, ch)
    return text.strip()


def parse_naver_blog(blog_json: dict[str, Any]) -> dict[str, Any]:
    """v1/search/blog raw → DDB `NAVER#BLOG` entity.

    작성자(bloggername·bloggerlink)는 옮기지 않는다 (PII).
    keyword_frequency 는 AI 트랙이 description 본문에서 추출 (parse 는 빈 dict).
    """
    items = blog_json.get("items") or []
    posts = [
        {
            "title": _strip_html(it.get("title") or ""),
            "link": it.get("link") or "",
            "description": _strip_html(it.get("description") or ""),
            "post_date": it.get("postdate"),
        }
        for it in items
    ]
    return {
        "total": blog_json.get("total"),
        "keyword_frequency": {},  # AI 트랙이 description 에서 채움
        "posts": posts,
    }


def to_naver_blog(parsed: dict[str, Any]) -> "NaverBlog":
    """parse_naver_blog() dict → NaverBlog 모델."""
    from shared.models import NaverBlog
    return NaverBlog.model_validate(parsed)
