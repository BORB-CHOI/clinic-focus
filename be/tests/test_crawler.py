"""크롤러 단위 테스트 — HTTP 모킹으로 AWS 없이 실행."""

import pytest
import httpx

from be.core.crawler import crawl_one_hospital


MOCK_HTML_MAIN = """
<html>
<head><title>○○피부과</title></head>
<body>
    <nav>메뉴</nav>
    <h1>○○피부과</h1>
    <p>아토피·여드름·습진 전문 진료</p>
    <p>일반 피부질환 중심의 동네 피부과입니다.</p>
    <img src="/img/clinic.jpg" alt="진료실">
    <img src="/img/atopy.jpg" alt="아토피 치료">
    <a href="/about">소개</a>
    <a href="/service">진료안내</a>
    <footer>주소: 서울시 강남구</footer>
</body>
</html>
"""

MOCK_HTML_ABOUT = """
<html><body>
    <h1>원장 인사말</h1>
    <p>2010년 개원 이래 강남구 주민들의 피부 건강을 책임져 왔습니다.</p>
</body></html>
"""


def _mock_transport(request: httpx.Request) -> httpx.Response:
    """URL에 따라 다른 HTML 반환."""
    url = str(request.url)
    if "about" in url:
        return httpx.Response(200, text=MOCK_HTML_ABOUT)
    if "service" in url or "doctors" in url or "blog" in url:
        return httpx.Response(404)
    return httpx.Response(200, text=MOCK_HTML_MAIN)


@pytest.mark.asyncio
async def test_crawl_extracts_main_page():
    """메인 페이지 텍스트가 정상 추출되는지."""
    transport = httpx.MockTransport(_mock_transport)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await crawl_one_hospital("h_test", "http://test-clinic.kr", client)

    assert result.hospital_id == "h_test"
    assert len(result.pages) >= 1
    assert result.pages[0].page_type == "main"
    assert "아토피" in result.pages[0].html_text
    assert "여드름" in result.pages[0].html_text
    # nav, footer는 제거되어야 함
    assert "메뉴" not in result.pages[0].html_text


@pytest.mark.asyncio
async def test_crawl_handles_404():
    """서브 페이지 404여도 크래시 없이 메인만 반환."""
    transport = httpx.MockTransport(lambda req: httpx.Response(404))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await crawl_one_hospital("h_test", "http://test-clinic.kr", client)

    # 메인도 404면 pages가 비어있을 수 있음
    assert result.hospital_id == "h_test"
    assert len(result.pages) == 0


@pytest.mark.asyncio
async def test_crawl_respects_max_pages():
    """MAX_PAGES 이상 크롤링하지 않는지."""
    call_count = 0

    def counting_transport(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, text=MOCK_HTML_MAIN)

    transport = httpx.MockTransport(counting_transport)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await crawl_one_hospital("h_test", "http://test-clinic.kr", client)

    # MAX_PAGES(10) + 메인 1개 이하여야 함
    assert len(result.pages) <= 11
