"""kakao_place_adapter 순수 파서 단위 테스트 — 네트워크 없이 fixture 로 실행.

fixture 는 실측 raw(ai/scratch/kakao-place-probe-2026-05-28/samples)에서
파서가 읽는 필드만 추린 것. 4건 표본 중 두 케이스를 커버:
  - 자생(27388604): mystore 미등록 → 대표 이미지 photos[] 폴백, homepages 다중(SNS 섞임)
  - 더서울(202729757): mystore 등록 → 공식 main_photo_url + mystore_intro
"""

import json
from pathlib import Path

import pytest

from be.adapters.kakao_place_adapter import (
    STRENGTH_LABELS,
    KakaoPlaceAdapter,
    extract_homepage,
    parse_blog,
    parse_place,
    parse_reviews,
)

FIXTURES = Path(__file__).parent / "fixtures" / "kakao"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def panel3_jaseng() -> dict:
    return _load("panel3_27388604.json")


@pytest.fixture
def panel3_theseoul() -> dict:
    return _load("panel3_202729757.json")


# --- extract_homepage --------------------------------------------------------

def test_extract_homepage_skips_social_picks_own_domain(panel3_jaseng):
    # homepages = [jaseng.co.kr, facebook, blog.naver, cafe.naver, jaseng.org]
    # → SNS·블로그·카페 건너뛰고 첫 자체 도메인
    assert extract_homepage(panel3_jaseng) == "http://www.jaseng.co.kr"


def test_extract_homepage_empty_returns_none():
    assert extract_homepage({"summary": {"homepages": []}}) is None
    assert extract_homepage({}) is None


def test_extract_homepage_all_social_falls_back_to_first():
    panel3 = {"summary": {"homepages": ["https://blog.naver.com/x", "https://facebook.com/y"]}}
    # 자체 도메인이 없으면 첫 항목 폴백
    assert extract_homepage(panel3) == "https://blog.naver.com/x"


# --- parse_place -------------------------------------------------------------

def test_parse_place_extracts_self_claim_tags(panel3_jaseng):
    place = parse_place(panel3_jaseng, "27388604")
    assert place["place_id"] == "27388604"
    assert place["name"] == "자생한방병원"
    # 자칭 키워드 시드 (분류기 primary_focus 입력)
    assert "도수치료" in place["tags"]
    assert "추나요법" in place["tags"]
    assert len(place["tags"]) == 18
    assert place["category"]["depth3"] == "한방병원"


def test_parse_place_hira_public_data(panel3_jaseng):
    place = parse_place(panel3_jaseng, "27388604")
    assert place["hira"]["medical_center_type"] == "한방병원"
    assert place["hira"]["doctor_count"]["total"] == 72


def test_parse_place_representative_image_prefers_mystore(panel3_theseoul):
    # mystore 등록 병원 → 사업자 공식 main_photo_url 우선 (PII 없음)
    place = parse_place(panel3_theseoul, "202729757")
    assert place["representative_image_url"].startswith("http://t1.kakaocdn.net/mystore/")
    assert place["mystore_intro"].startswith("더서울병원은")


def test_parse_place_representative_image_falls_back_to_photos(panel3_jaseng):
    # mystore 미등록 → photos[] URL 폴백 (owner 메타 없이 URL 만)
    place = parse_place(panel3_jaseng, "27388604")
    assert place["representative_image_url"].startswith("http://t1.daumcdn.net/")
    assert place["mystore_intro"] is None


# --- parse_reviews -----------------------------------------------------------

def test_parse_reviews_strength_to_keyword_frequency(panel3_jaseng):
    reviews = parse_reviews(_load("reviews_27388604.json"))
    # strength_counts id → 라벨 빈도 (화면 노출 가능)
    assert reviews["keyword_frequency"] == {"친절": 164, "전문성": 145, "주차": 50, "가격": 32}
    assert reviews["total_reviews"] == 303
    assert reviews["average_score"] == 4.6


def test_parse_reviews_strips_owner_pii():
    reviews = parse_reviews(_load("reviews_27388604.json"))
    for item in reviews["reviews"]:
        # 본문 raw 는 유지 (DDB 저장·임베딩 입력)
        assert "contents" in item
        # owner PII(meta) 는 정제 결과에 없어야 함
        assert "meta" not in item
        assert "owner" not in item
        assert set(item.keys()) <= {
            "review_id", "contents", "star_rating",
            "strength_labels", "photo_count", "registered_at",
        }


def test_parse_reviews_keeps_star_rating():
    reviews = parse_reviews(_load("reviews_27388604.json"))
    # 카카오는 병원 카테고리도 star_rating 노출 (네이버는 null)
    assert reviews["reviews"][0]["star_rating"] is not None


# --- parse_blog --------------------------------------------------------------

def test_parse_blog_seeds_and_pii_removal():
    blog = parse_blog(_load("blog_8094954.json"))
    assert blog["total_posts"] == 60
    assert blog["seeds"], "블로그 시드가 비어선 안 됨"
    for seed in blog["seeds"]:
        # origin_url = BlogSignal 시드
        assert seed["origin_url"].startswith("https://blog.naver.com/")
        # author PII 제거
        assert "author" not in seed
        assert set(seed.keys()) <= {
            "review_id", "title", "contents", "origin_url",
            "photo_count", "registered_at",
        }


def test_strength_labels_fixed_four():
    # 사실 18: 카테고리 무관 고정 4종
    assert STRENGTH_LABELS == {13: "가격", 10: "전문성", 2: "친절", 4: "주차"}


# --- fetch_* place_id 검증 (SSRF/경로조작 방어) --------------------------------

@pytest.mark.parametrize("bad_id", ["27388604/extra", "27388604?x=1", "../admin", "abc", ""])
def test_fetch_rejects_non_integer_place_id(bad_id):
    # 정수 아닌 place_id 는 네트워크 호출 없이 None (URL 경로 조작 차단)
    adapter = KakaoPlaceAdapter()
    try:
        assert adapter.fetch_panel3(bad_id) is None
        assert adapter.fetch_reviews(bad_id) is None
        assert adapter.fetch_blog(bad_id) is None
    finally:
        adapter.close()
