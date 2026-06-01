"""BrowserManager 단위 테스트 — 생명주기, 200페이지 재시작, 타임아웃 처리."""

from __future__ import annotations

import asyncio

import pytest

from be.core.browser_manager import BrowserManager


@pytest.mark.asyncio
async def test_lifecycle_enter_exit():
    """async context manager로 진입/종료 시 브라우저가 시작/종료된다."""
    async with BrowserManager() as bm:
        # 브라우저가 시작되어 있어야 함
        assert bm._browser is not None
        assert bm._playwright is not None

    # 종료 후 정리
    assert bm._browser is None
    assert bm._playwright is None


@pytest.mark.asyncio
async def test_page_count_increments():
    """render_page 호출 시 page_count가 증가한다."""
    async with BrowserManager() as bm:
        # 존재하지 않는 URL이라 None 반환되지만 카운터는 증가해야 함
        result = await bm.render_page("data:text/html,<h1>hello</h1>")
        assert bm.page_count == 1


@pytest.mark.asyncio
async def test_restart_after_max_pages():
    """MAX_PAGES_BEFORE_RESTART 도달 시 브라우저가 재시작되고 카운터가 리셋된다."""
    async with BrowserManager() as bm:
        # 카운터를 MAX-1로 설정하여 다음 호출에서 재시작 트리거
        bm._page_count = BrowserManager.MAX_PAGES_BEFORE_RESTART - 1
        old_browser = bm._browser

        # data URI로 간단한 페이지 렌더링
        await bm.render_page("data:text/html,<h1>trigger restart</h1>")

        # 재시작 후 카운터 리셋 확인
        assert bm.page_count == 0
        # 새 브라우저 인스턴스여야 함
        assert bm._browser is not old_browser


@pytest.mark.asyncio
async def test_timeout_returns_none():
    """타임아웃 발생 시 None을 반환하고 크래시하지 않는다."""
    async with BrowserManager() as bm:
        # 매우 짧은 타임아웃 설정
        bm.PAGE_TIMEOUT_MS = 1  # 1ms — 거의 모든 외부 URL이 타임아웃

        result = await bm.render_page("https://httpbin.org/delay/10")
        assert result is None


@pytest.mark.asyncio
async def test_crash_recovery():
    """브라우저 크래시 시 새 인스턴스를 생성하고 계속 동작한다."""
    async with BrowserManager() as bm:
        # 브라우저를 강제 종료하여 크래시 시뮬레이션
        await bm._browser.close()

        # 다음 호출에서 복구되어야 함
        result = await bm.render_page("data:text/html,<h1>recovered</h1>")
        # 복구 후 브라우저가 다시 연결되어 있어야 함
        assert bm._browser is not None
        assert bm._browser.is_connected()


@pytest.mark.asyncio
async def test_semaphore_limits_concurrency():
    """동시 탭이 MAX_CONCURRENT_TABS(3)으로 제한된다."""
    async with BrowserManager() as bm:
        # Semaphore 값 확인
        assert bm._semaphore._value == BrowserManager.MAX_CONCURRENT_TABS

        # 3개 동시 요청 시작 (data URI로 빠르게 완료)
        tasks = [
            asyncio.create_task(bm.render_page("data:text/html,<h1>page</h1>"))
            for _ in range(5)
        ]
        results = await asyncio.gather(*tasks)
        # 모두 완료되어야 함 (순차적으로 3개씩)
        assert len(results) == 5


@pytest.mark.asyncio
async def test_extract_element_attr():
    """extract_element_attr로 특정 요소의 속성값을 추출할 수 있다."""
    html = '<html><body><a id="link" href="https://example.com">Home</a></body></html>'
    data_url = f"data:text/html,{html}"

    async with BrowserManager() as bm:
        result = await bm.extract_element_attr(data_url, "a#link", "href")
        assert result == "https://example.com"


@pytest.mark.asyncio
async def test_extract_element_attr_missing_element():
    """존재하지 않는 셀렉터에 대해 None을 반환한다."""
    html = "<html><body><p>No links here</p></body></html>"
    data_url = f"data:text/html,{html}"

    async with BrowserManager() as bm:
        result = await bm.extract_element_attr(data_url, "a#nonexistent", "href")
        assert result is None
