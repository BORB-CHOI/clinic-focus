"""URLValidator 단위 테스트 — 2xx 통과, 4xx/5xx 거부, 타임아웃 거부, 리다이렉트 추적, 차단 도메인 거부."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from be.core.url_validator import URLValidator


@pytest.fixture
def validator() -> URLValidator:
    return URLValidator()


# --- 2xx 통과 ---


@pytest.mark.asyncio
async def test_200_ok_returns_url(validator: URLValidator):
    """200 OK 응답 시 URL을 반환한다."""
    url = "https://example-hospital.com"

    mock_response = httpx.Response(
        status_code=200,
        request=httpx.Request("HEAD", url),
    )

    with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=mock_response):
        result = await validator.validate(url)

    assert result == url


# --- 리다이렉트 추적 ---


@pytest.mark.asyncio
async def test_redirect_to_valid_domain_returns_final_url(validator: URLValidator):
    """301 리다이렉트 후 유효한 도메인이면 최종 URL을 반환한다."""
    original_url = "https://old-hospital.com"
    final_url = "https://new-hospital.com/home"

    mock_response = httpx.Response(
        status_code=200,
        request=httpx.Request("HEAD", final_url),
    )
    # httpx follow_redirects=True 시 response.url이 최종 URL
    mock_response._url = httpx.URL(final_url)

    with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=mock_response):
        result = await validator.validate(original_url)

    assert result == final_url


@pytest.mark.asyncio
async def test_redirect_to_blocked_domain_returns_none(validator: URLValidator):
    """301 리다이렉트 후 차단 도메인이면 None을 반환한다."""
    original_url = "https://hospital-redirect.com"
    final_url = "https://map.naver.com/some-place"

    mock_response = httpx.Response(
        status_code=200,
        request=httpx.Request("HEAD", final_url),
    )
    mock_response._url = httpx.URL(final_url)

    with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=mock_response):
        result = await validator.validate(original_url)

    assert result is None


# --- 4xx/5xx 거부 ---


@pytest.mark.asyncio
async def test_404_returns_none(validator: URLValidator):
    """404 응답 시 None을 반환한다."""
    url = "https://example-hospital.com/not-found"

    mock_response = httpx.Response(
        status_code=404,
        request=httpx.Request("HEAD", url),
    )

    with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=mock_response):
        result = await validator.validate(url)

    assert result is None


@pytest.mark.asyncio
async def test_500_returns_none(validator: URLValidator):
    """500 응답 시 None을 반환한다."""
    url = "https://example-hospital.com"

    mock_response = httpx.Response(
        status_code=500,
        request=httpx.Request("HEAD", url),
    )

    with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=mock_response):
        result = await validator.validate(url)

    assert result is None


# --- 타임아웃 거부 ---


@pytest.mark.asyncio
async def test_timeout_returns_none(validator: URLValidator):
    """타임아웃 발생 시 None을 반환한다."""
    url = "https://slow-hospital.com"

    with patch(
        "httpx.AsyncClient.head",
        new_callable=AsyncMock,
        side_effect=httpx.TimeoutException("Connection timed out"),
    ):
        result = await validator.validate(url)

    assert result is None


# --- 차단 도메인 거부 ---


@pytest.mark.asyncio
async def test_blocked_domain_input_returns_none(validator: URLValidator):
    """입력 URL이 차단 도메인이면 HTTP 요청 없이 None을 반환한다."""
    blocked_urls = [
        "https://map.naver.com/v5/entry/place/12345",
        "https://map.daum.net/place/67890",
        "https://google.com/maps/place/hospital",
        "https://search.naver.com/search.naver?query=hospital",
        "https://news.naver.com/article/123",
    ]

    for url in blocked_urls:
        result = await validator.validate(url)
        assert result is None, f"Expected None for blocked URL: {url}"


@pytest.mark.asyncio
async def test_subdomain_of_blocked_domain_returns_none(validator: URLValidator):
    """차단 도메인의 서브도메인도 차단된다."""
    url = "https://www.google.com/search?q=hospital"
    result = await validator.validate(url)
    assert result is None


# --- HEAD 405 → GET 폴백 ---


@pytest.mark.asyncio
async def test_head_405_falls_back_to_get(validator: URLValidator):
    """HEAD 405 시 GET으로 폴백하여 200이면 URL을 반환한다."""
    url = "https://hospital-no-head.com"

    head_response = httpx.Response(
        status_code=405,
        request=httpx.Request("HEAD", url),
    )

    get_response = httpx.Response(
        status_code=200,
        request=httpx.Request("GET", url),
    )

    with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=head_response):
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=get_response):
            result = await validator.validate(url)

    assert result == url


@pytest.mark.asyncio
async def test_head_405_get_also_fails_returns_none(validator: URLValidator):
    """HEAD 405 후 GET도 실패하면 None을 반환한다."""
    url = "https://hospital-broken.com"

    head_response = httpx.Response(
        status_code=405,
        request=httpx.Request("HEAD", url),
    )

    get_response = httpx.Response(
        status_code=500,
        request=httpx.Request("GET", url),
    )

    with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=head_response):
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=get_response):
            result = await validator.validate(url)

    assert result is None


# --- _is_blocked_domain 직접 테스트 ---


def test_is_blocked_domain_exact_match(validator: URLValidator):
    """정확히 일치하는 차단 도메인을 감지한다."""
    assert validator._is_blocked_domain("https://map.naver.com/place/123") is True
    assert validator._is_blocked_domain("https://map.daum.net/place/456") is True
    assert validator._is_blocked_domain("https://google.com/maps") is True


def test_is_blocked_domain_subdomain_match(validator: URLValidator):
    """차단 도메인의 서브도메인을 감지한다."""
    assert validator._is_blocked_domain("https://www.google.com/search") is True
    assert validator._is_blocked_domain("https://sub.map.naver.com/x") is True


def test_is_blocked_domain_valid_url(validator: URLValidator):
    """차단되지 않은 도메인은 False를 반환한다."""
    assert validator._is_blocked_domain("https://hospital-clinic.com") is False
    assert validator._is_blocked_domain("https://www.hospital.co.kr") is False
    assert validator._is_blocked_domain("https://naver.com") is False  # naver.com 자체는 차단 아님
