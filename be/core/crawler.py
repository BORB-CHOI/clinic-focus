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

# 서브 페이지 분류 키워드
_PAGE_TYPE_KEYWORDS: dict[str, list[str]] = {
    "about": ["소개", "인사말", "about", "intro", "greeting", "원장"],
    "service": ["진료", "클리닉", "치료", "service", "clinic", "treatment", "센터", "center"],
    "doctors": ["의료진", "원장님", "doctor", "staff", "전문의", "대표원장"],
    "blog": ["블로그", "칼럼", "건강정보", "blog", "column", "news", "공지", "notice"],
}

# 무시할 링크 패턴
_IGNORE_PATTERNS = [
    "javascript:", "#", "mailto:", "tel:", "kakao", "naver.com",
    "facebook.com", "instagram.com", "youtube.com", "twitter.com",
    ".pdf", ".zip", ".hwp", ".doc",
]

# 요청 간격 (초)
REQUEST_DELAY = 1.0

# 최대 크롤링 페이지 수
MAX_PAGES = 10

# 최대 이미지 수집 수
MAX_IMAGES = 30

USER_AGENT = "ClinicFocusBot/1.0 (research; contact@clinicfocus.kr)"


async def crawl_one_hospital(
    hospital_id: str,
    website_url: str,
    http_client: httpx.AsyncClient,
) -> CrawlData:
    """병원 1개 사이트 크롤링. CrawlData 반환."""
    pages: list[CrawledPage] = []
    images: list[CrawledImage] = []
    visited_urls: set[str] = set()

    # 도메인 제한 (외부 사이트로 나가지 않도록)
    parsed_base = urlparse(website_url)
    base_domain = parsed_base.netloc

    # 1. 메인 페이지 fetch (raw HTML 포함)
    main_result = await _fetch_page_raw(http_client, website_url)
    if not main_result:
        return _empty_crawl_data(hospital_id, website_url)

    raw_html, text, soup = main_result
    main_page = CrawledPage(
        url=website_url,
        page_type="main",
        html_text=text,
        fetched_at=datetime.utcnow(),
    )
    pages.append(main_page)
    visited_urls.add(website_url)
    visited_urls.add(website_url.rstrip("/"))

    # 메인 페이지에서 이미지 수집
    main_images = _extract_images(soup, website_url)
    images.extend(main_images[:MAX_IMAGES])

    # 메인 페이지에서 서브 페이지 링크 탐색
    sub_links = _find_subpage_links(soup, website_url, base_domain)

    # 2. 서브 페이지 크롤링
    for link_url, page_type in sub_links:
        normalized = link_url.rstrip("/")
        if normalized in visited_urls or len(pages) >= MAX_PAGES:
            break
        visited_urls.add(normalized)
        visited_urls.add(link_url)

        await asyncio.sleep(REQUEST_DELAY)

        sub_result = await _fetch_page_raw(http_client, link_url)
        if not sub_result:
            continue

        sub_raw, sub_text, sub_soup = sub_result

        # 텍스트가 너무 짧으면 스킵 (JS 렌더링 필요 사이트)
        if len(sub_text) < 50:
            continue

        sub_page = CrawledPage(
            url=link_url,
            page_type=page_type,
            html_text=sub_text,
            fetched_at=datetime.utcnow(),
        )
        pages.append(sub_page)

        # 서브 페이지 이미지도 수집
        if len(images) < MAX_IMAGES:
            sub_images = _extract_images(sub_soup, link_url)
            remaining = MAX_IMAGES - len(images)
            images.extend(sub_images[:remaining])

    return CrawlData(
        hospital_id=hospital_id,
        website_url=website_url,
        pages=pages,
        images=images,
        public_data=PublicData(license_number="", specialists=[], registered_devices=[]),
    )


async def _fetch_page_raw(
    client: httpx.AsyncClient,
    url: str,
) -> tuple[str, str, BeautifulSoup] | None:
    """페이지 fetch → (raw_html, clean_text, soup) 반환."""
    try:
        resp = await client.get(
            url,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=15.0,
        )
        if resp.status_code != 200:
            return None

        # 인코딩 처리
        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type and "text/" not in content_type:
            return None

        raw_html = resp.text
        soup = BeautifulSoup(raw_html, "html.parser")

        # 텍스트 추출용 복사본 (원본 soup는 링크/이미지 파싱에 사용)
        text_soup = BeautifulSoup(raw_html, "html.parser")
        for tag in text_soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        text = text_soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()

        return raw_html, text, soup

    except (httpx.HTTPError, Exception):
        return None


def _find_subpage_links(
    soup: BeautifulSoup,
    base_url: str,
    base_domain: str,
) -> list[tuple[str, Literal["about", "service", "doctors", "blog", "other"]]]:
    """HTML에서 같은 도메인의 서브 페이지 링크 추출 + 페이지 타입 분류."""
    results: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()

        # 무시할 패턴 체크
        if any(pattern in href.lower() for pattern in _IGNORE_PATTERNS):
            continue

        # 절대 URL로 변환
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        # 같은 도메인만
        if parsed.netloc != base_domain:
            continue

        # 중복 제거
        normalized = full_url.rstrip("/")
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)

        # 페이지 타입 분류 (URL + 링크 텍스트 기반)
        link_text = a_tag.get_text(strip=True).lower()
        url_lower = full_url.lower()
        page_type = _classify_page_type(url_lower, link_text)

        results.append((full_url, page_type))

    # 우선순위: about > service > doctors > blog > other
    priority = {"about": 0, "service": 1, "doctors": 2, "blog": 3, "other": 4}
    results.sort(key=lambda x: priority.get(x[1], 4))

    return results[:MAX_PAGES - 1]  # 메인 제외하고 최대 9개


def _classify_page_type(
    url: str, link_text: str
) -> Literal["about", "service", "doctors", "blog", "other"]:
    """URL과 링크 텍스트로 페이지 타입 분류."""
    combined = f"{url} {link_text}"

    for page_type, keywords in _PAGE_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                return page_type

    return "other"


def _extract_images(soup: BeautifulSoup, page_url: str) -> list[CrawledImage]:
    """HTML에서 이미지 URL 추출."""
    images: list[CrawledImage] = []
    seen_urls: set[str] = set()

    for img_tag in soup.find_all("img", src=True):
        src = img_tag["src"].strip()

        # data URI 스킵
        if src.startswith("data:"):
            continue

        # 절대 URL로 변환
        full_url = urljoin(page_url, src)

        # 너무 작은 이미지 (아이콘 등) 필터링
        width = img_tag.get("width", "")
        height = img_tag.get("height", "")
        if width and width.isdigit() and int(width) < 50:
            continue
        if height and height.isdigit() and int(height) < 50:
            continue

        # 중복 제거
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        alt_text = img_tag.get("alt", "").strip() or None

        images.append(CrawledImage(
            url=full_url,
            page_url=page_url,
            alt_text=alt_text,
        ))

    return images


def _empty_crawl_data(hospital_id: str, website_url: str) -> CrawlData:
    """빈 크롤링 결과 반환."""
    return CrawlData(
        hospital_id=hospital_id,
        website_url=website_url,
        pages=[],
        images=[],
        public_data=PublicData(license_number="", specialists=[], registered_devices=[]),
    )
