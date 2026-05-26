"""KakaoPlaceRenderer 단위 테스트 — 로컬 HTML fixture로 추출 로직 검증."""

from __future__ import annotations

import pathlib
import urllib.parse

import pytest

from be.adapters.kakao_place_renderer import KakaoPlaceRenderer
from be.core.browser_manager import BrowserManager

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


def _fixture_url(filename: str) -> str:
    """로컬 HTML fixture 파일을 file:// URL로 변환."""
    path = FIXTURES_DIR / filename
    return path.as_uri()


# ---------------------------------------------------------------------------
# 3.1 & 3.2: 셀렉터 기반 홈페이지 링크 추출
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_homepage_link_homepage_selector():
    """a.link_homepage 셀렉터로 홈페이지 URL을 추출한다."""
    async with BrowserManager() as bm:
        renderer = KakaoPlaceRenderer(bm)
        url = _fixture_url("kakao_place_with_homepage.html")
        result = await renderer.extract_homepage_url(url)
        assert result == "https://www.cmcseoul.or.kr"


@pytest.mark.asyncio
async def test_extract_homepage_data_id_selector():
    """a[data-id="homepage"] 셀렉터로 홈페이지 URL을 추출한다."""
    async with BrowserManager() as bm:
        renderer = KakaoPlaceRenderer(bm)
        url = _fixture_url("kakao_place_data_id_selector.html")
        result = await renderer.extract_homepage_url(url)
        assert result == "https://gs.severance.healthcare"


@pytest.mark.asyncio
async def test_extract_homepage_fallback_selector():
    """detail_placeinfo 내 a[href^='http'] 폴백 셀렉터로 URL을 추출한다."""
    async with BrowserManager() as bm:
        renderer = KakaoPlaceRenderer(bm)
        url = _fixture_url("kakao_place_fallback_selector.html")
        result = await renderer.extract_homepage_url(url)
        assert result == "http://www.samsunghospital.com"


@pytest.mark.asyncio
async def test_extract_homepage_http_protocol():
    """http:// 프로토콜 URL도 정상적으로 추출한다."""
    async with BrowserManager() as bm:
        renderer = KakaoPlaceRenderer(bm)
        url = _fixture_url("kakao_place_http_url.html")
        result = await renderer.extract_homepage_url(url)
        assert result == "http://www.yonsei-clinic.co.kr"


# ---------------------------------------------------------------------------
# 3.2: 홈페이지 링크 없는 경우
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_none_when_no_homepage():
    """홈페이지 링크가 없는 페이지에서 None을 반환한다."""
    async with BrowserManager() as bm:
        renderer = KakaoPlaceRenderer(bm)
        url = _fixture_url("kakao_place_no_homepage.html")
        result = await renderer.extract_homepage_url(url)
        assert result is None


# ---------------------------------------------------------------------------
# 3.3: URL 프로토콜 검증 로직
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_protocol_returns_none():
    """http/https가 아닌 URL(javascript: 등)은 필터링하여 None을 반환한다."""
    async with BrowserManager() as bm:
        renderer = KakaoPlaceRenderer(bm)
        url = _fixture_url("kakao_place_invalid_protocol.html")
        result = await renderer.extract_homepage_url(url)
        assert result is None


class TestValidateProtocol:
    """_validate_protocol 정적 메서드 단위 테스트."""

    def test_https_url_passes(self):
        assert (
            KakaoPlaceRenderer._validate_protocol("https://example.com")
            == "https://example.com"
        )

    def test_http_url_passes(self):
        assert (
            KakaoPlaceRenderer._validate_protocol("http://example.com")
            == "http://example.com"
        )

    def test_javascript_url_rejected(self):
        assert KakaoPlaceRenderer._validate_protocol("javascript:void(0)") is None

    def test_ftp_url_rejected(self):
        assert KakaoPlaceRenderer._validate_protocol("ftp://files.example.com") is None

    def test_relative_url_rejected(self):
        assert KakaoPlaceRenderer._validate_protocol("/path/to/page") is None

    def test_empty_string_rejected(self):
        assert KakaoPlaceRenderer._validate_protocol("") is None

    def test_tel_url_rejected(self):
        assert KakaoPlaceRenderer._validate_protocol("tel:02-555-1234") is None

    def test_mailto_url_rejected(self):
        assert (
            KakaoPlaceRenderer._validate_protocol("mailto:info@hospital.com") is None
        )


# ---------------------------------------------------------------------------
# 3.1: BrowserManager 주입 확인
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reuses_browser_manager_instance():
    """KakaoPlaceRenderer는 주입된 BrowserManager 인스턴스를 재사용한다."""
    async with BrowserManager() as bm:
        renderer = KakaoPlaceRenderer(bm)
        assert renderer._browser_manager is bm

        # 두 번 호출해도 같은 BrowserManager 사용
        url = _fixture_url("kakao_place_with_homepage.html")
        await renderer.extract_homepage_url(url)
        await renderer.extract_homepage_url(url)

        # page_count가 증가했으므로 같은 인스턴스 사용 확인
        assert bm.page_count == 2
