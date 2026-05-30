"""병원 1개 크롤링 — 순수 로직. AWS 의존 없음."""

from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter
from datetime import datetime
from typing import TYPE_CHECKING, Literal
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from shared.models import CrawlData, CrawledImage, CrawledPage, PublicData

if TYPE_CHECKING:
    from be.core.browser_manager import BrowserManager

logger = logging.getLogger(__name__)

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

# 이미지 노이즈 필터 — 파일명·alt 에 이 토큰이 있으면 비-진료 장식/추적 이미지로 보고 스킵.
# Vision 입력 품질을 위해 로고·아이콘·버튼·배너·SNS·1x1 추적 픽셀 등을 거른다.
_IMAGE_NOISE_PATTERN = re.compile(
    r"(logo|icon|btn|button|banner|bullet|sprite|bg|pixel|tracking|1x1|"
    r"spacer|blank|favicon|sns|kakao|naver|facebook|map_)",
    re.IGNORECASE,
)

# 추적 도메인 — 이 호스트가 src 에 들어간 이미지는 분석 가치 없음 (analytics·픽셀).
_IMAGE_TRACKING_DOMAINS = ("google-analytics", "facebook.com/tr")

USER_AGENT = "ClinicFocusBot/1.0 (research; contact@clinicfocus.kr)"

# HTML 잡음 블랙리스트 (이슈 #13) — 의료 사이트 공통 비-진료 텍스트.
# 정제 후 이 문구를 포함한 단락은 자칭/블로그 시그널에서 제외한다.
# ⚠️ 비급여 진료비·항목은 제외하지 않는다 — 시술명·가격(PriceItem) 의 원천이라 시그널.
_NOISE_BLACKLIST = (
    "개인정보취급방침", "개인정보처리방침", "환자권리장전", "이용약관",
    "Copyright", "COPYRIGHT", "All rights reserved",
    "modoo.at", "모두의 홈페이지", "페이지를 찾을 수 없", "404 Not Found",
    "사업자등록번호", "통신판매업신고",
)

# 페이지 간 반복 판정 임계 — 한 사이트의 이 비율 이상 페이지에서 똑같이 나오면
# 네비/푸터/공통 배너로 보고 제거. 메뉴/푸터는 보통 전 페이지에 나오므로 보수적으로(0.7)
# 잡아 고유 진료 단락의 과삭제를 막는다. 페이지가 3개 미만이면 반복 검출 자체를 끈다.
_REPEAT_RATIO_THRESHOLD = 0.7
_REPEAT_MIN_PAGES = 3

# 페이지를 **통째로** 버릴 노이즈 마커 (단락 블랙리스트 _NOISE_BLACKLIST 와 별개).
# 에러·준비중·로그인벽 페이지는 진료 정보가 없으므로 시그널에서 제외한다.
_PAGE_NOISE_MARKERS = (
    "페이지를 찾을 수 없", "404 not found", "준비중입니다", "준비 중입니다",
    "공사중", "서비스 점검", "접근 권한이 없", "로그인이 필요", "잘못된 접근",
    "페이지가 존재하지 않", "정보 부족",
)
# 자체 블로그(자칭 동류) RSS 아카이브 상한 — depth 가 블로그 글 수십~수백 개를 빨아들이면
# 자칭 본문이 과대해져 도배 효과가 난다. 진료정보(about/service/doctors)는 무제한, blog 만 캡.
_MAX_BLOG_PAGES = 8

# 단락 분리 기준 — 문장부호·줄바꿈 외에 메뉴성 짧은 토막은 길이로 거른다.
_MIN_PARAGRAPH_LEN = 10


def _split_paragraphs(text: str) -> list[str]:
    """텍스트를 단락 후보로 분리한다. 줄바꿈·마침표 기준 + 공백 정규화."""
    # 줄바꿈/마침표/물음표/느낌표 뒤에서 분리
    chunks = re.split(r"[\n。.!?]+", text)
    return [re.sub(r"\s+", " ", c).strip() for c in chunks if c.strip()]


def _denoise_pages(pages: list[CrawledPage]) -> list[CrawledPage]:
    """페이지 간 반복 단락(네비·푸터)·잡음 블랙리스트를 제거한다 (이슈 #13).

    1) 모든 페이지의 단락을 모아, N개 이상 페이지에서 반복되는 단락 = 공통 잡음으로 판정.
    2) 잡음 블랙리스트 문구를 포함한 단락 제거.
    3) 정제 후 100자 미만이면 html_text 끝에 "[정보 부족]" 마크.

    원본 page 객체는 건드리지 않고 html_text 만 교체한 새 리스트를 반환.
    """
    if not pages:
        return pages

    # 페이지별 단락 집합
    page_paragraphs: list[list[str]] = [_split_paragraphs(p.html_text or "") for p in pages]

    # 단락별 등장 페이지 수 카운트
    para_doc_count: Counter = Counter()
    for paras in page_paragraphs:
        for para in set(paras):  # 한 페이지 내 중복은 1회로
            para_doc_count[para] += 1

    n_pages = len(pages)
    # 페이지가 적으면(<3) 반복 검출은 우연한 중복을 과삭제하므로 끈다.
    # 충분하면 "전체의 70% 이상 페이지에 등장"한 단락만 네비/푸터로 본다.
    repeat_threshold = (
        max(2, int(round(n_pages * _REPEAT_RATIO_THRESHOLD)))
        if n_pages >= _REPEAT_MIN_PAGES
        else n_pages + 1  # 도달 불가 = 반복 검출 비활성
    )

    def _is_noise(para: str) -> bool:
        if len(para) < _MIN_PARAGRAPH_LEN:
            return True
        if para_doc_count[para] >= repeat_threshold:
            return True  # 여러 페이지 반복 = 네비/푸터
        return any(bad in para for bad in _NOISE_BLACKLIST)

    def _blacklist_only(paras: list[str]) -> list[str]:
        """반복 검출 없이 블랙리스트·길이 필터만 적용 (반복 검출 과삭제 fallback)."""
        return [
            p for p in paras
            if len(p) >= _MIN_PARAGRAPH_LEN and not any(bad in p for bad in _NOISE_BLACKLIST)
        ]

    cleaned: list[CrawledPage] = []
    for page, paras in zip(pages, page_paragraphs):
        kept = [p for p in paras if not _is_noise(p)]
        # 반복 검출이 단락을 전부 날렸는데 원본엔 내용이 있었다면(사이트가 페이지 간
        # 거의 동일한 극단 케이스) 반복 검출은 신뢰할 수 없으므로 블랙리스트만 적용.
        if not kept and paras:
            kept = _blacklist_only(paras)
        text = " ".join(kept)
        if len(text) < 100:
            text = f"{text} [정보 부족]".strip()
        cleaned.append(page.model_copy(update={"html_text": text}))
    return cleaned


def _filter_noise_pages(pages: list[CrawledPage]) -> list[CrawledPage]:
    """페이지를 **통째로** 거르는 단계 (`_denoise_pages` 이후 실행).

    `_denoise_pages` 가 단락 단위로 네비/푸터/블랙리스트를 지운다면, 여기선 페이지 단위로:
      1) 에러·준비중·로그인벽 페이지(_PAGE_NOISE_MARKERS) 제외 — 진료 정보 없음.
      2) 본문이 거의 동일한 중복 페이지 제거 — `/` 와 `/index` 같은 같은 화면.
      3) 자체 블로그(page_type=blog) 페이지 수 상한(_MAX_BLOG_PAGES) — RSS 아카이브 도배 방지.
         진료정보(main/about/service/doctors)는 캡 없이 전부 유지.

    크롤 시점(crawl_one_hospital)과 기존 데이터 재처리(reprocess_crawl) 둘 다 이 함수를 쓴다.
    """
    kept: list[CrawledPage] = []
    seen: set[str] = set()
    blog_count = 0
    for p in pages:
        text = (p.html_text or "").strip()
        low = text.lower()

        # 1) 에러/준비중/로그인벽 — 짧은데 노이즈 마커가 있으면 통째 제외.
        #    (긴 본문에 우연히 마커가 섞인 정상 페이지는 살린다 — 길이 가드 300자)
        if len(text) < 300 and any(m in low for m in _PAGE_NOISE_MARKERS):
            continue

        # 2) 거의 동일한 중복 페이지 — 공백 제거 본문 해시로 1회만.
        norm = re.sub(r"\s+", "", text)
        if norm:
            key = f"{len(norm)}:{hash(norm)}"
            if key in seen:
                continue
            seen.add(key)

        # 3) 블로그 RSS 아카이브 상한 (진료정보 page_type 은 캡 없음).
        if p.page_type == "blog":
            if blog_count >= _MAX_BLOG_PAGES:
                continue
            blog_count += 1

        kept.append(p)

    # 전부 걸러졌다면(극단) 원본 유지 — 빈 CrawlData 보다 낫다.
    return kept or pages


async def crawl_one_hospital(
    hospital_id: str,
    website_url: str,
    http_client: httpx.AsyncClient,
    browser_manager: "BrowserManager | None" = None,
) -> CrawlData:
    """병원 1개 사이트 크롤링. CrawlData 반환.

    browser_manager가 제공되면 정적 크롤링 실패(< 100자) 시 Playwright 폴백 사용.
    """
    from be.core.js_renderer import JSRenderer

    pages: list[CrawledPage] = []
    images: list[CrawledImage] = []
    visited_urls: set[str] = set()

    # JS 렌더러 초기화 (browser_manager가 있을 때만)
    js_renderer: JSRenderer | None = None
    if browser_manager is not None:
        js_renderer = JSRenderer(browser_manager)

    # 메인 페이지가 JS 렌더링을 필요로 했는지 추적
    use_playwright = False

    # 도메인 제한 (외부 사이트로 나가지 않도록)
    parsed_base = urlparse(website_url)
    base_domain = parsed_base.netloc

    # 1. 메인 페이지 fetch (정적 먼저 시도)
    main_result = await _fetch_page_raw(http_client, website_url)
    render_method: Literal["static", "playwright"] = "static"

    if main_result:
        raw_html, text, soup = main_result
    else:
        text = ""
        soup = None
        raw_html = ""

    # 정적 결과가 없거나 텍스트 < 100자 → JS 폴백 시도
    if len(text) < 100 and js_renderer is not None:
        logger.info("Static text too short (%d chars) for %s, trying JS render", len(text), website_url)
        js_result = await js_renderer.render_and_extract(website_url)
        if js_result is not None:
            js_text, js_soup = js_result
            if len(js_text) >= 100:
                text = js_text
                soup = js_soup
                render_method = "playwright"
                use_playwright = True
                logger.info("JS render succeeded for %s (%d chars)", website_url, len(js_text))
            else:
                logger.warning("JS render also short (%d chars) for %s, skipping", len(js_text), website_url)
        else:
            logger.warning("JS render failed for %s, skipping", website_url)

    # 메인 페이지 결과 판정:
    # - browser_manager가 있을 때: 100자 미만이면 빈 결과 (render_failed)
    # - browser_manager가 없을 때: soup만 있으면 기존 동작 유지 (하위 호환)
    if soup is None:
        return _empty_crawl_data(hospital_id, website_url)
    if len(text) < 100 and browser_manager is not None:
        return _empty_crawl_data(hospital_id, website_url)

    main_page = CrawledPage(
        url=website_url,
        page_type="main",
        html_text=text,
        fetched_at=datetime.utcnow(),
        render_method=render_method,
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

        sub_render_method: Literal["static", "playwright"] = "static"
        sub_text: str = ""
        sub_soup: BeautifulSoup | None = None

        if use_playwright and js_renderer is not None:
            # 메인 페이지가 JS 필요했으면 서브페이지도 Playwright 사용
            js_sub_result = await js_renderer.render_and_extract(link_url)
            if js_sub_result is not None:
                sub_text, sub_soup = js_sub_result
                sub_render_method = "playwright"
            # Playwright 실패 시 정적 폴백
            if not sub_text:
                sub_result = await _fetch_page_raw(http_client, link_url)
                if sub_result:
                    _, sub_text, sub_soup = sub_result
                    sub_render_method = "static"
        else:
            # 정적 크롤링
            sub_result = await _fetch_page_raw(http_client, link_url)
            if sub_result:
                _, sub_text, sub_soup = sub_result
                sub_render_method = "static"

        # 텍스트가 너무 짧으면 스킵
        if len(sub_text) < 50:
            continue

        sub_page = CrawledPage(
            url=link_url,
            page_type=page_type,
            html_text=sub_text,
            fetched_at=datetime.utcnow(),
            render_method=sub_render_method,
        )
        pages.append(sub_page)

        # 서브 페이지 이미지도 수집
        if len(images) < MAX_IMAGES and sub_soup is not None:
            sub_images = _extract_images(sub_soup, link_url)
            remaining = MAX_IMAGES - len(images)
            images.extend(sub_images[:remaining])

    return CrawlData(
        hospital_id=hospital_id,
        website_url=website_url,
        pages=_filter_noise_pages(_denoise_pages(pages)),  # 단락 정제(#13) → 페이지 단위 노이즈 제거
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

        alt_text = img_tag.get("alt", "").strip() or None

        # 노이즈 필터 — 파일명·alt 에 장식/추적 토큰이 있으면 스킵
        if _IMAGE_NOISE_PATTERN.search(src) or _IMAGE_NOISE_PATTERN.search(alt_text or ""):
            continue
        # 추적 도메인 이미지 스킵
        if any(dom in full_url.lower() for dom in _IMAGE_TRACKING_DOMAINS):
            continue

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
