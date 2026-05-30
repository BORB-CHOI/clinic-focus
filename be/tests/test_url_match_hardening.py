"""URL 오매칭 방어 테스트 — 카카오 이름 매칭 + 크롤 후 병원명 교차검증."""

from datetime import datetime

from be.adapters.kakao_adapter import _name_core, _name_match
from be.core.crawler import site_mentions_hospital
from shared.models import CrawlData, CrawledPage


# ── ① 카카오 이름 매칭 (_name_core / _name_match) ──────────────────────
def test_name_core_strips_suffix_and_parens():
    assert _name_core("헵시바치과의원") == "헵시바"
    assert _name_core("해아림한의원(목동점)") == "해아림목동점"  # 지점명 유지
    assert _name_core("연세365의원") == "연세365"


def test_name_match_positive():
    assert _name_match({"place_name": "헵시바치과"}, _name_core("헵시바치과의원"))
    assert _name_match({"place_name": "리더스피부과 청담점"}, _name_core("리더스피부과의원"))


def test_name_match_negative_different_hospital():
    # 다른 병원이면 핵심 토큰 불일치 → False (맹목 매칭 방지)
    assert not _name_match({"place_name": "압구정성형외과"}, _name_core("헵시바치과의원"))


def test_name_match_short_core_disabled():
    # 핵심 토큰 2자 미만(흔한 이름)은 신뢰 못 해 False → 지역(동/구) 매칭에 의존.
    assert not _name_match({"place_name": "본의원"}, _name_core("본의원"))  # core "본" len1 → False
    # 2자 이상 핵심 토큰은 정상 매칭 (예: "서울"내과)
    assert _name_match({"place_name": "서울내과"}, _name_core("서울내과의원"))


# ── ② 크롤 후 병원명 교차검증 (site_mentions_hospital) ──────────────────
def _cd(name_in_text: str | None) -> CrawlData:
    text = f"환자 여러분 환영합니다 {name_in_text or ''} 진료안내 양악수술" if name_in_text else "엉뚱한 식당 메뉴 김치찌개 된장찌개"
    return CrawlData(
        hospital_id="h1", website_url="http://x",
        pages=[CrawledPage(url="http://x", page_type="main", html_text=text,
                           fetched_at=datetime(2026, 5, 30), render_method="static")],
        images=[], public_data=None,
    )


def test_site_mentions_match():
    assert site_mentions_hospital("헵시바치과의원", _cd("헵시바치과")) is True


def test_site_mentions_mismatch_discards():
    # 본문에 병원명 핵심 토큰 없음 → 잘못된 URL 의심 (False = 폐기 대상)
    assert site_mentions_hospital("헵시바치과의원", _cd(None)) is False


def test_site_mentions_short_core_conservative():
    # 핵심 토큰 2자 미만이면 검증 불가 → True(보수적, 폐기 안 함)
    assert site_mentions_hospital("본의원", _cd(None)) is True


def test_site_mentions_empty_pages():
    cd = CrawlData(hospital_id="h", website_url="http://x", pages=[], images=[], public_data=None)
    assert site_mentions_hospital("헵시바치과의원", cd) is False  # 본문 없음 → 미언급
