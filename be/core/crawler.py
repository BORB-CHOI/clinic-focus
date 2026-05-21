"""병원 1개 크롤링 — 순수 로직. AWS 의존 없음."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Literal
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from shared.models import CrawlData, CrawledImage, CrawledPage, PublicData

# 크롤링 대상 서브 페이지 패턴
_SUBPAGE_PATTERNS: dict[str, list[str]] = {
    "about": ["소개", "인사말", "about", "intro"],
    "service": ["진료", "클리닉", "치료", "service", "clinic", "treatment"],
    "doctors": ["의료진", "원장", "doctor", "staff"],
    "blog": ["블로그", "칼럼", "건강정보", "blog", "column", "news"],
}

# 요청 간격 (초) — 예의상 딜레이
REQUEST_DELAY = 1.0

# 최대 크롤링 페이지 수
MAX_PAGES = 10


async def crawl_one_hospital(
    hospital_id: str,
    website_url: str,
    http_client: httpx.AsyncClient,
) -> CrawlData:
    """병원 1개 사이트 크롤링. CrawlData 반환."""
    pages: list[CrawledPage] = []
    images: list[CrawledImage] = []
    visited_urls: set[str] = set()

    # 1. 메인 페이지
    main_page = await _fetch_page(http_client, website_url, "main")
    if main_page:
        pages.append(main_page)
        visited_urls.add(website_url)

        # 메인 페이지에서 이미지 수집
        main_images = _extract_images(main_page.html_text, website_url)
        images.extend(main_images)

        # 메인 페이지에서 서브 페이지 링크 탐색
        sub_links = _find_subpage_links(main_page.html_text, website_url)

        # 2. 서브 페이지 크롤링
        for link_url, page_type in sub_links:
            if link_url in visited_urls or len(pages) >= MAX_PAGES:
                break
            visited_urls.add(link_url)

            await asyncio.sleep(REQUEST_DELAY)
            sub_page = await _fetch_page(http_client, link_url, page_type)
            if sub_page:
                pages.append(sub_page)
                sub_images = _extract_images(sub_page.html_text, link_url)
                images.extend(sub_images)

    return CrawlData(
        hospital_id=hospital_id,
        website_url=website_url,
        pages=pages,
        images=images,
        public_data=PublicData(license_number="", specialists=[], registered_devices=[]),
    )


async def _fetch_page(
    client: httpx.AsyncClient,
    url: str,
    page_type: Literal["main", "about", "service", "doctors", "blog", "other"],
) -> CrawledPage | None:
    """단일 페이지 fetch + 텍스트 추출."""
    try:
        resp = await client.get(
            url,
            headers={"User-Agent": "ClinicFocusBot/1.0 (research; contact@clinicfocus.kr)"},
            follow_redirects=True,
            timeout=15.0,
        )
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # 불필요한 태그 제거
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        # 연속 공백 정리
        text = re.sub(r"\s+", " ", text).strip()

        return CrawledPage(
            url=url,
            page_type=page_type,
            html_text=text,
            fetched_at=datetime.utcnow(),
        )
    except (httpx.HTTPError, Exception):
        return None


def _find_subpage_links(
    html_text: str, base_url: str
) -> list[tuple[str, Literal["about", "service", "doctors", "blog", "other"]]]:
    """메인 페이지 HTML에서 서브 페이지 링크 추출."""
    # 실제로는 원본 HTML이 필요하지만, 여기서는 간소화
    # 실제 구현에서는 raw HTML을 별도로 받아서 처리
    results: list[tuple[str, str]] = []

    # 패턴 매칭으로 서브 페이지 URL 추정
    parsed = urlparse(base_url)
    base_domain = f"{parsed.scheme}://{parsed.netloc}"

    for page_type, keywords in _SUBPAGE_PATTERNS.items():
        for kw in keywords:
            candidate = f"{base_domain}/{kw}"
            results.append((candidate, page_type))

    return results[:8]  # 최대 8개 서브 페이지


def _extract_images(page_text: str, page_url: str) -> list[CrawledImage]:
    """페이지에서 이미지 URL 추출. (실제 구현에서는 raw HTML 파싱)"""
    # 간소화: 실제로는 BeautifulSoup으로 img 태그 파싱
    # 여기서는 빈 리스트 반환, 실제 구현 시 raw HTML 기반으로 교체
    return []
