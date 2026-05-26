"""URL 유효성 검증 — HEAD 요청, 리다이렉트 추적, 차단 도메인 필터링."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx


class URLValidator:
    """URL 접근 가능성 및 유효성 검증.

    - HEAD 요청으로 2xx/3xx 확인
    - HEAD 405 시 GET 폴백
    - 리다이렉트 추적 후 최종 URL 반환
    - 차단 도메인 필터링
    - 10초 타임아웃
    """

    BLOCKED_DOMAINS: list[str] = [
        "map.naver.com",
        "map.daum.net",
        "google.com",
        "search.naver.com",
        "news.naver.com",
    ]

    TIMEOUT_SECONDS: float = 10.0

    USER_AGENT: str = "ClinicFocusBot/1.0 (research; contact@clinicfocus.kr)"

    async def validate(self, url: str) -> str | None:
        """URL 유효성 검증. 유효하면 최종 URL 반환, 아니면 None.

        1. 입력 URL 도메인이 차단 목록에 있으면 None
        2. HEAD 요청 (follow_redirects=True, timeout=10s)
        3. HEAD 405 시 GET 폴백
        4. 2xx/3xx → 최종 URL 도메인 차단 확인 → 최종 URL 반환
        5. 4xx/5xx → None
        6. 타임아웃 → None
        """
        if self._is_blocked_domain(url):
            return None

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(self.TIMEOUT_SECONDS),
            ) as client:
                # HEAD 요청 시도
                response = await client.head(
                    url,
                    headers={"User-Agent": self.USER_AGENT},
                )

                # HEAD 405 → GET 폴백
                if response.status_code == 405:
                    response = await client.get(
                        url,
                        headers={"User-Agent": self.USER_AGENT},
                    )

                # 2xx/3xx 확인
                if response.status_code >= 400:
                    return None

                # 최종 URL 추출 (리다이렉트 후)
                final_url = str(response.url)

                # 최종 URL 도메인이 차단 목록에 있으면 None
                if self._is_blocked_domain(final_url):
                    return None

                return final_url

        except httpx.TimeoutException:
            return None
        except (httpx.HTTPError, Exception):
            return None

    def _is_blocked_domain(self, url: str) -> bool:
        """URL의 도메인이 차단 목록에 포함되는지 확인."""
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
            # 정확히 일치하거나 서브도메인으로 일치하는 경우 차단
            for blocked in self.BLOCKED_DOMAINS:
                if hostname == blocked or hostname.endswith(f".{blocked}"):
                    return True
            return False
        except Exception:
            return False
