"""JS 렌더링 크롤러 통합 테스트.

테스트 케이스:
1. 정적 성공 (text ≥ 100자) → Playwright 미사용, render_method="static"
2. 정적 실패 (text < 100자) + JS 성공 → render_method="playwright"
3. 정적 실패 + JS 실패 → 페이지 스킵 (빈 결과)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from be.core.browser_manager import BrowserManager
from be.core.crawler import crawl_one_hospital
from be.core.js_renderer import JSRenderer


# --- Fixtures: HTML 콘텐츠 ---

# 충분한 텍스트가 있는 정적 HTML (≥ 100자)
STATIC_RICH_HTML = """
<html>
<head><title>서울피부과</title></head>
<body>
    <h1>서울피부과 의원</h1>
    <p>아토피, 여드름, 습진, 건선, 두드러기 등 각종 피부질환을 전문적으로 진료합니다.
    20년 경력의 피부과 전문의가 정확한 진단과 맞춤 치료를 제공합니다.</p>
    <p>레이저 치료, 보톡스, 필러 등 미용 시술도 가능합니다.</p>
    <a href="/about">소개</a>
    <a href="/service">진료안내</a>
</body>
</html>
"""

# 텍스트가 부족한 정적 HTML (< 100자) — SPA 사이트 시뮬레이션
STATIC_SPARSE_HTML = """
<html>
<head><title>SPA병원</title></head>
<body>
    <div id="app"></div>
    <script src="/bundle.js"></script>
</body>
</html>
"""

# JS 렌더링 후 충분한 텍스트가 있는 HTML
JS_RENDERED_HTML = """
<html>
<head><title>SPA병원</title></head>
<body>
    <div id="app">
        <h1>SPA병원 소개</h1>
        <p>최신 의료 장비와 숙련된 의료진이 환자분들의 건강을 책임집니다.
        내과, 외과, 정형외과, 재활의학과 등 다양한 진료과를 운영하고 있습니다.</p>
        <p>진료 시간: 평일 09:00-18:00, 토요일 09:00-13:00</p>
    </div>
    <a href="/about">병원소개</a>
    <a href="/doctors">의료진</a>
</body>
</html>
"""

# 서브페이지 HTML (충분한 텍스트)
SUB_PAGE_HTML = """
<html>
<body>
    <h1>의료진 소개</h1>
    <p>김원장 - 내과 전문의, 서울대학교 의과대학 졸업, 20년 경력의 내과 전문의입니다.
    당뇨, 고혈압, 갑상선 질환 등을 전문적으로 진료합니다.</p>
</body>
</html>
"""


def _make_static_rich_transport(request: httpx.Request) -> httpx.Response:
    """정적 크롤링으로 충분한 텍스트를 반환하는 transport."""
    url = str(request.url)
    if "about" in url or "service" in url:
        return httpx.Response(200, text=SUB_PAGE_HTML)
    return httpx.Response(200, text=STATIC_RICH_HTML)


def _make_static_sparse_transport(request: httpx.Request) -> httpx.Response:
    """정적 크롤링으로 텍스트가 부족한 transport (SPA 사이트)."""
    return httpx.Response(200, text=STATIC_SPARSE_HTML)


# --- Test 1: 정적 성공 케이스 ---


@pytest.mark.asyncio
async def test_static_success_no_playwright():
    """정적 크롤링으로 충분한 텍스트 → Playwright 미사용, render_method='static'."""
    mock_browser_manager = AsyncMock(spec=BrowserManager)

    transport = httpx.MockTransport(_make_static_rich_transport)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await crawl_one_hospital(
            "h_static",
            "http://test-clinic.kr",
            client,
            browser_manager=mock_browser_manager,
        )

    # 메인 페이지가 정상 크롤링됨
    assert len(result.pages) >= 1
    assert result.pages[0].page_type == "main"
    assert result.pages[0].render_method == "static"

    # Playwright render_page가 호출되지 않아야 함
    mock_browser_manager.render_page.assert_not_called()


# --- Test 2: JS 폴백 성공 케이스 ---


@pytest.mark.asyncio
async def test_js_fallback_success():
    """정적 < 100자 + JS 렌더링 성공 → render_method='playwright'."""
    mock_browser_manager = AsyncMock(spec=BrowserManager)
    # render_page가 JS 렌더링된 HTML 반환
    mock_browser_manager.render_page = AsyncMock(return_value=JS_RENDERED_HTML)

    transport = httpx.MockTransport(_make_static_sparse_transport)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await crawl_one_hospital(
            "h_js",
            "http://spa-clinic.kr",
            client,
            browser_manager=mock_browser_manager,
        )

    # 메인 페이지가 JS 렌더링으로 성공
    assert len(result.pages) >= 1
    assert result.pages[0].page_type == "main"
    assert result.pages[0].render_method == "playwright"
    assert "SPA병원" in result.pages[0].html_text

    # Playwright render_page가 호출됨
    mock_browser_manager.render_page.assert_called()


# --- Test 3: JS 렌더링 실패 케이스 ---


@pytest.mark.asyncio
async def test_js_fallback_failure_skips_page():
    """정적 < 100자 + JS 렌더링 실패 → 페이지 스킵 (빈 결과)."""
    mock_browser_manager = AsyncMock(spec=BrowserManager)
    # render_page가 None 반환 (렌더링 실패)
    mock_browser_manager.render_page = AsyncMock(return_value=None)

    transport = httpx.MockTransport(_make_static_sparse_transport)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await crawl_one_hospital(
            "h_fail",
            "http://broken-clinic.kr",
            client,
            browser_manager=mock_browser_manager,
        )

    # 메인 페이지도 실패 → 빈 결과
    assert len(result.pages) == 0
    assert result.hospital_id == "h_fail"


# --- Test 4: browser_manager=None 시 기존 동작 유지 ---


@pytest.mark.asyncio
async def test_backward_compatible_without_browser_manager():
    """browser_manager=None이면 기존 정적 크롤링만 수행."""
    transport = httpx.MockTransport(_make_static_rich_transport)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await crawl_one_hospital(
            "h_compat",
            "http://test-clinic.kr",
            client,
            # browser_manager 미제공 (기본값 None)
        )

    assert len(result.pages) >= 1
    assert result.pages[0].render_method == "static"


# --- Test 5: 메인 JS 필요 시 서브페이지도 Playwright 사용 ---


@pytest.mark.asyncio
async def test_subpages_use_playwright_when_main_needs_js():
    """메인 페이지가 JS 필요 시 서브페이지도 Playwright로 크롤링."""
    call_urls: list[str] = []

    async def mock_render_page(url: str, wait_until: str = "networkidle") -> str | None:
        call_urls.append(url)
        if "about" in url or "doctors" in url:
            return SUB_PAGE_HTML
        return JS_RENDERED_HTML

    mock_browser_manager = AsyncMock(spec=BrowserManager)
    mock_browser_manager.render_page = AsyncMock(side_effect=mock_render_page)

    transport = httpx.MockTransport(_make_static_sparse_transport)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await crawl_one_hospital(
            "h_subjs",
            "http://spa-clinic.kr",
            client,
            browser_manager=mock_browser_manager,
        )

    # 메인 페이지는 playwright
    assert result.pages[0].render_method == "playwright"

    # 서브페이지가 있으면 playwright로 시도됨
    # (JS_RENDERED_HTML에 /about, /doctors 링크가 있으므로)
    if len(result.pages) > 1:
        # 서브페이지도 playwright로 렌더링 시도됨
        assert any(url != "http://spa-clinic.kr" for url in call_urls)


# --- Test 6: JSRenderer 단위 테스트 ---


@pytest.mark.asyncio
async def test_js_renderer_render_and_extract():
    """JSRenderer.render_and_extract가 clean text와 soup를 반환."""
    mock_browser_manager = AsyncMock(spec=BrowserManager)
    mock_browser_manager.render_page = AsyncMock(return_value=JS_RENDERED_HTML)

    renderer = JSRenderer(mock_browser_manager)
    result = await renderer.render_and_extract("http://test.kr")

    assert result is not None
    text, soup = result
    assert "SPA병원" in text
    assert len(text) >= 100
    # script 태그 내용은 제거되어야 함
    assert "<script" not in text


@pytest.mark.asyncio
async def test_js_renderer_returns_none_on_failure():
    """JSRenderer.render_and_extract가 렌더링 실패 시 None 반환."""
    mock_browser_manager = AsyncMock(spec=BrowserManager)
    mock_browser_manager.render_page = AsyncMock(return_value=None)

    renderer = JSRenderer(mock_browser_manager)
    result = await renderer.render_and_extract("http://broken.kr")

    assert result is None
