"""Playwright 브라우저 인스턴스 관리 — async context manager."""

from __future__ import annotations

import asyncio
import logging
from typing import Self

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

logger = logging.getLogger(__name__)


class BrowserManager:
    """Playwright Chromium headless 브라우저 생명주기 관리.

    - 30페이지마다 브라우저 재시작 (RAM 4GB·메모리 상주 차단)
    - 30초 페이지 타임아웃
    - 동시 탭 3개 제한 (asyncio.Semaphore)
    - 크래시 복구: 브라우저 비정상 종료 시 새 인스턴스 생성
    """

    MAX_PAGES_BEFORE_RESTART: int = 30
    PAGE_TIMEOUT_MS: int = 30_000
    MAX_CONCURRENT_TABS: int = 3

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page_count: int = 0
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_TABS)

    @property
    def page_count(self) -> int:
        """현재까지 처리한 페이지 수."""
        return self._page_count

    async def __aenter__(self) -> Self:
        self._playwright = await async_playwright().start()
        await self._launch_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        await self._close_browser()
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def render_page(self, url: str, wait_until: str = "networkidle") -> str | None:
        """URL을 Playwright로 렌더링하여 텍스트 콘텐츠 반환.

        타임아웃 또는 에러 시 None 반환.
        """
        async with self._semaphore:
            await self._ensure_browser()
            context: BrowserContext | None = None
            try:
                context = await self._browser.new_context()  # type: ignore[union-attr]
                page: Page = await context.new_page()
                await page.goto(url, wait_until=wait_until, timeout=self.PAGE_TIMEOUT_MS)
                content = await page.content()
                return content
            except Exception as exc:
                logger.warning("render_page failed for %s: %s", url, exc)
                # 브라우저 크래시 감지 후 복구
                if self._browser and not self._browser.is_connected():
                    logger.info("Browser disconnected, recovering...")
                    await self._restart_browser()
                return None
            finally:
                if context:
                    try:
                        await context.close()
                    except Exception:
                        pass
                self._page_count += 1
                if self._page_count >= self.MAX_PAGES_BEFORE_RESTART:
                    await self._restart_browser()

    async def screenshot_page(self, url: str, full_page: bool = True) -> bytes | None:
        """URL을 렌더링해 풀페이지 스크린샷 PNG bytes 반환.

        Vision 시연(10개 한정)용. 디스크 임시파일을 거치지 않고 bytes 로 직접 반환한다.
        타임아웃·에러·브라우저 크래시 시 None 반환.

        ⚠️ 메인 크롤 루프에 자동 연결하지 않는다 (비용·자격증명 이슈). 호출은 후속.
        """
        async with self._semaphore:
            await self._ensure_browser()
            context: BrowserContext | None = None
            try:
                context = await self._browser.new_context(  # type: ignore[union-attr]
                    viewport={"width": 1280, "height": 2000},
                )
                page: Page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=self.PAGE_TIMEOUT_MS)
                shot = await page.screenshot(full_page=full_page, type="png")
                return shot
            except Exception as exc:
                logger.warning("screenshot_page failed for %s: %s", url, exc)
                # 브라우저 크래시 감지 후 복구
                if self._browser and not self._browser.is_connected():
                    logger.info("Browser disconnected, recovering...")
                    await self._restart_browser()
                return None
            finally:
                if context:
                    try:
                        await context.close()
                    except Exception:
                        pass
                self._page_count += 1
                if self._page_count >= self.MAX_PAGES_BEFORE_RESTART:
                    await self._restart_browser()

    async def extract_element_attr(self, url: str, selector: str, attr: str) -> str | None:
        """URL을 렌더링한 뒤 특정 셀렉터의 속성값 추출.

        카카오 장소 페이지 등에서 홈페이지 링크 추출에 사용.
        """
        async with self._semaphore:
            await self._ensure_browser()
            context: BrowserContext | None = None
            try:
                context = await self._browser.new_context()  # type: ignore[union-attr]
                page: Page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=self.PAGE_TIMEOUT_MS)
                element = await page.query_selector(selector)
                if element is None:
                    return None
                value = await element.get_attribute(attr)
                return value
            except Exception as exc:
                logger.warning("extract_element_attr failed for %s: %s", url, exc)
                if self._browser and not self._browser.is_connected():
                    logger.info("Browser disconnected, recovering...")
                    await self._restart_browser()
                return None
            finally:
                if context:
                    try:
                        await context.close()
                    except Exception:
                        pass
                self._page_count += 1
                if self._page_count >= self.MAX_PAGES_BEFORE_RESTART:
                    await self._restart_browser()

    async def _ensure_browser(self) -> None:
        """브라우저가 살아있는지 확인, 없으면 새로 시작."""
        if self._browser is None or not self._browser.is_connected():
            await self._launch_browser()

    async def _restart_browser(self) -> None:
        """브라우저 재시작 — 메모리 누적 방지 및 크래시 복구."""
        logger.info("Restarting browser (page_count=%d)", self._page_count)
        await self._close_browser()
        await self._launch_browser()
        self._page_count = 0

    async def _launch_browser(self) -> None:
        """Chromium headless 브라우저 시작.

        RAM 4GB·작은 /dev/shm 환경 대응 args:
        - --no-sandbox: 컨테이너/제한 환경에서 sandbox 비활성 (EC2 단일 프로세스)
        - --disable-dev-shm-usage: 작은 /dev/shm 대신 /tmp 사용 (크래시 방지)
        - --disable-gpu: headless에서 불필요한 GPU 프로세스 차단
        - --single-process: 별도 렌더러 프로세스 미생성 (메모리 절감)
        """
        if self._playwright is None:
            raise RuntimeError("BrowserManager not entered as context manager")
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
            ],
        )

    async def _close_browser(self) -> None:
        """브라우저 안전 종료."""
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
