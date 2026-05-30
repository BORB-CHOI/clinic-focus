"""_filter_noise_pages 단위 테스트 — 페이지 단위 노이즈 제거(에러/중복/블로그 캡)."""

from datetime import datetime

from be.core.crawler import _MAX_BLOG_PAGES, _filter_noise_pages
from shared.models import CrawledPage


def _page(html_text: str, page_type: str = "service", url: str = "http://x/") -> CrawledPage:
    return CrawledPage(
        url=url,
        page_type=page_type,
        html_text=html_text,
        fetched_at=datetime(2026, 5, 30),
        render_method="static",
    )


def test_drops_short_error_page():
    """짧고 에러/준비중 마커가 있는 페이지는 통째 제외."""
    pages = [
        _page("저희 병원은 피부질환을 진료합니다. " * 5, page_type="main", url="http://x/"),
        _page("준비중입니다.", page_type="service", url="http://x/svc"),
        _page("페이지를 찾을 수 없습니다 404 Not Found", page_type="other", url="http://x/404"),
    ]
    out = _filter_noise_pages(pages)
    urls = {p.url for p in out}
    assert "http://x/svc" not in urls
    assert "http://x/404" not in urls
    assert "http://x/" in urls


def test_keeps_long_page_with_incidental_marker():
    """긴 정상 본문에 우연히 마커가 섞여 있어도 살린다(길이 가드)."""
    body = "아토피 클리닉 진료 안내. " * 40 + "로그인이 필요한 회원 게시판도 있습니다."
    out = _filter_noise_pages([_page(body, url="http://x/long")])
    assert len(out) == 1


def test_dedups_near_identical_pages():
    """공백만 다른 동일 본문 페이지는 1회만 유지(/ 와 /index)."""
    text = "여드름 흉터 레이저 치료 전문 클리닉입니다. " * 10
    pages = [
        _page(text, url="http://x/"),
        _page(text + "   ", page_type="about", url="http://x/index"),
        _page("전혀 다른 보톡스 필러 시술 안내 본문. " * 10, page_type="service", url="http://x/svc"),
    ]
    out = _filter_noise_pages(pages)
    assert len(out) == 2  # 중복 1개 제거


def test_caps_blog_pages_but_not_clinical():
    """blog 페이지는 _MAX_BLOG_PAGES 로 캡, 진료정보 page_type 은 캡 없음."""
    blog = [
        _page(f"블로그 포스트 {i} 본문 내용입니다 환자 후기 사례. " * 5,
              page_type="blog", url=f"http://x/blog/{i}")
        for i in range(_MAX_BLOG_PAGES + 5)
    ]
    clinical = [
        _page(f"진료과목 {i} 상세 안내 본문. " * 5, page_type="service", url=f"http://x/svc/{i}")
        for i in range(10)
    ]
    out = _filter_noise_pages(blog + clinical)
    n_blog = sum(1 for p in out if p.page_type == "blog")
    n_clinical = sum(1 for p in out if p.page_type == "service")
    assert n_blog == _MAX_BLOG_PAGES   # 블로그는 캡
    assert n_clinical == 10            # 진료정보는 전부 유지


def test_all_filtered_falls_back_to_original():
    """전부 걸러지는 극단 케이스엔 빈 리스트 대신 원본 유지."""
    pages = [_page("준비중입니다", page_type="main", url="http://x/")]
    out = _filter_noise_pages(pages)
    assert out == pages  # fallback


def test_empty_input():
    assert _filter_noise_pages([]) == []
