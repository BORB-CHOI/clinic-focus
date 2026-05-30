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

    MAX_PAGES_BEFORE_RESTART: int = 8   # 4GB EC2 single-process 크롬 크래시 누적 방지 (구 30→8)
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

    async def screenshot_page_scroll(
        self, url: str, *, max_tiles: int = 8, capture_popup: bool = True
    ) -> list[bytes]:
        """페이지를 위→아래 **뷰포트 타일 여러 장**으로 전부 캡처 (Vision 시연용).

        - full_page 한 장은 너무 길어 Sonnet 이 다운스케일→텍스트 깨짐. 그래서 1280×1600
          뷰포트 단위로 스크롤하며 여러 장(가독성 유지).
        - **팝업 처리**: 내용이 유용(시술 안내)할 수 있어 **닫기 전 1장 먼저 캡처** → 이후
          Escape·닫기버튼·오버레이 JS 제거로 본문을 가리지 않게 한 뒤 스크롤 타일.
        - lazy-load 대비 타일마다 짧게 대기 + scrollHeight 재측정.

        Returns: PNG bytes 리스트(앞=팝업 포함 첫 화면, 이후=본문 타일). 실패 시 가능한 만큼.
        """
        async with self._semaphore:
            await self._ensure_browser()
            context: BrowserContext | None = None
            shots: list[bytes] = []
            vh = 1600
            try:
                context = await self._browser.new_context(  # type: ignore[union-attr]
                    viewport={"width": 1280, "height": vh},
                )
                page: Page = await context.new_page()
                # networkidle 은 광고·트래킹으로 계속 통신하는 사이트에서 30초 풀타임아웃을
                # 먹어 병원당 ~2분으로 느려진다 → "load" + 짧은 타임아웃. 타임아웃이 나도
                # 부분 렌더라도 캡처를 진행한다(throw 로 전체 캡처를 버리지 않게).
                try:
                    await page.goto(url, wait_until="load", timeout=15_000)
                except Exception as exc:  # noqa: BLE001
                    logger.info("goto 부분 로드/타임아웃(%s) — 현재 상태로 캡처 진행: %s", url, exc)
                await page.wait_for_timeout(1500)  # 팝업·지연 렌더 대기

                # 1) 팝업 포함 첫 화면 1장 (팝업 안내문 내용 보존)
                if capture_popup:
                    s = await page.screenshot(type="png")
                    if s:
                        shots.append(s)

                # 2) 팝업/오버레이 닫기 — 본문을 가리지 않게
                try:
                    await page.keyboard.press("Escape")
                    await page.evaluate(
                        """() => {
                            const kill = el => { try { el.style.display='none'; } catch(e){} };
                            document.querySelectorAll(
                              '[class*=popup i],[class*=modal i],[class*=layer i],[id*=popup i],[id*=modal i],[class*=dimm i],[class*=overlay i]'
                            ).forEach(kill);
                            document.querySelectorAll('body *').forEach(el => {
                              const cs = getComputedStyle(el);
                              if ((cs.position==='fixed'||cs.position==='absolute')
                                  && parseInt(cs.zIndex||0) >= 100 && el.offsetHeight > 200) kill(el);
                            });
                        }"""
                    )
                    for sel in ("text=오늘 하루", "text=닫기", ".close", "[aria-label*=close i]", ".btn-close"):
                        try:
                            await page.click(sel, timeout=400)
                        except Exception:  # noqa: BLE001
                            pass
                except Exception:  # noqa: BLE001
                    pass
                await page.wait_for_timeout(300)

                # 3) 위→아래 뷰포트 타일 (스크롤하며 전부)
                y = 0
                n = 0
                total = await page.evaluate("() => document.body.scrollHeight")
                while y < total and n < max_tiles:
                    await page.evaluate(f"window.scrollTo(0, {y})")
                    await page.wait_for_timeout(250)  # lazy-load
                    s = await page.screenshot(type="png")
                    if s:
                        shots.append(s)
                        n += 1
                    y += vh
                    total = await page.evaluate("() => document.body.scrollHeight")
                return shots
            except Exception as exc:  # noqa: BLE001
                logger.warning("screenshot_page_scroll failed for %s: %s", url, exc)
                if self._browser and not self._browser.is_connected():
                    await self._restart_browser()
                return shots
            finally:
                if context:
                    try:
                        await context.close()
                    except Exception:  # noqa: BLE001
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

        ⚠️ --single-process 는 **제거**했다. 그 플래그가 "Target page/context/browser
        has been closed" 크래시의 주범(헤드리스 크롬 단일프로세스 불안정)이었고, 스왑
        4GB 확보로 멀티프로세스 메모리 여유도 생겼다. 멀티프로세스가 훨씬 안정적.
        """
        if self._playwright is None:
            raise RuntimeError("BrowserManager not entered as context manager")
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
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
