"""카카오 장소 페이지 Playwright 렌더링 → 홈페이지 URL 추출.

카카오 장소 페이지(place.map.kakao.com/{id})를 Playwright로 렌더링하고,
여러 후보 CSS 셀렉터를 순차 시도하여 홈페이지 링크를 추출한다.
"""

from __future__ import annotations

import logging

from be.core.browser_manager import BrowserManager

logger = logging.getLogger(__name__)


class KakaoPlaceRenderer:
    """카카오 장소 페이지에서 홈페이지 URL을 추출하는 렌더러.

    BrowserManager를 주입받아 단일 브라우저 인스턴스를 재사용하며,
    여러 후보 CSS 셀렉터를 순차적으로 시도하여 첫 번째 매칭된 홈페이지 URL을 반환한다.
    """

    # 카카오 장소 페이지에서 홈페이지 링크를 찾기 위한 후보 셀렉터 목록.
    # 카카오 페이지 DOM 구조가 변경될 수 있으므로 여러 후보를 순차 시도한다.
    HOMEPAGE_SELECTORS: list[str] = [
        "a.link_homepage",
        'a[data-id="homepage"]',
        ".info_detail .link_url",
        ".cont_essential .link_detail",
        ".detail_placeinfo a[href^='http']",
        "a.link_detail[href^='http']",
    ]

    TIMEOUT_MS: int = 15_000

    def __init__(self, browser_manager: BrowserManager) -> None:
        self._browser_manager = browser_manager

    async def extract_homepage_url(self, place_url: str) -> str | None:
        """카카오 장소 페이지에서 홈페이지 URL을 추출한다.

        Args:
            place_url: 카카오맵 장소 URL (예: "http://place.map.kakao.com/12345678")

        Returns:
            홈페이지 URL 문자열 또는 None (미발견/타임아웃/프로토콜 불일치 시)
        """
        async with self._browser_manager._semaphore:
            await self._browser_manager._ensure_browser()
            context = None
            try:
                context = await self._browser_manager._browser.new_context()  # type: ignore[union-attr]
                page = await context.new_page()
                await page.goto(
                    place_url,
                    wait_until="networkidle",
                    timeout=self.TIMEOUT_MS,
                )

                # 여러 후보 셀렉터를 순차 시도하여 첫 번째 매칭 반환
                for selector in self.HOMEPAGE_SELECTORS:
                    element = await page.query_selector(selector)
                    if element is not None:
                        href = await element.get_attribute("href")
                        if href:
                            validated = self._validate_protocol(href)
                            if validated is not None:
                                logger.debug(
                                    "Found homepage URL via selector '%s': %s",
                                    selector,
                                    validated,
                                )
                                return validated

                logger.debug("No homepage link found on %s", place_url)
                return None

            except Exception as exc:
                logger.warning(
                    "KakaoPlaceRenderer failed for %s: %s", place_url, exc
                )
                # 브라우저 크래시 감지 후 복구
                if (
                    self._browser_manager._browser
                    and not self._browser_manager._browser.is_connected()
                ):
                    logger.info("Browser disconnected, recovering...")
                    await self._browser_manager._restart_browser()
                return None
            finally:
                if context:
                    try:
                        await context.close()
                    except Exception:
                        pass
                self._browser_manager._page_count += 1
                if (
                    self._browser_manager._page_count
                    >= self._browser_manager.MAX_PAGES_BEFORE_RESTART
                ):
                    await self._browser_manager._restart_browser()

    @staticmethod
    def _validate_protocol(url: str) -> str | None:
        """URL이 http:// 또는 https://로 시작하는지 검증.

        Args:
            url: 검증할 URL 문자열

        Returns:
            유효한 URL이면 그대로 반환, 아니면 None
        """
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return None
