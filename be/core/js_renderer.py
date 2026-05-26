"""SPA 병원 홈페이지 Playwright 렌더링 — BrowserManager 주입."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from be.core.browser_manager import BrowserManager

logger = logging.getLogger(__name__)


class JSRenderer:
    """SPA 병원 홈페이지를 Playwright로 렌더링하여 텍스트+soup 반환.

    - BrowserManager를 주입받아 브라우저 인스턴스를 재사용
    - networkidle 대기 후 HTML 추출
    - script/style/nav/footer/header/noscript 제거 후 clean text 반환
    """

    def __init__(self, browser_manager: BrowserManager) -> None:
        self._browser_manager = browser_manager

    async def render_and_extract(self, url: str) -> tuple[str, BeautifulSoup] | None:
        """URL을 Playwright로 렌더링하여 (clean_text, soup) 반환.

        렌더링 실패 시 None 반환.
        """
        raw_html = await self._browser_manager.render_page(url, wait_until="networkidle")
        if raw_html is None:
            logger.warning("JSRenderer: render_page returned None for %s", url)
            return None

        soup = BeautifulSoup(raw_html, "html.parser")

        # 텍스트 추출용 복사본 (crawler.py의 _fetch_page_raw와 동일 로직)
        text_soup = BeautifulSoup(raw_html, "html.parser")
        for tag in text_soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        text = text_soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()

        return text, soup
