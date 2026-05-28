"""test_naver_adapters.py — 네이버 블로그·플레이스 어댑터 parse 단위 테스트.

실행: .venv/bin/python -m pytest be/tests/test_naver_adapters.py -q

parse_* 는 순수 함수라 네트워크(Playwright·httpx) 없이 테스트한다.
의료법 §56③: 후기/블로그 본문은 보존하되 작성자 PII 미보존 검증이 핵심.
"""

from __future__ import annotations

import json
from pathlib import Path

from be.adapters.naver_blog_adapter import parse_naver_blog, to_naver_blog
from be.adapters.naver_place_adapter import parse_place, to_naver_place

_FIXTURE = Path(__file__).parent / "fixtures" / "naver"


# ---------------------------------------------------------------------------
# 네이버 블로그 (v1/search/blog 공식 API)
# ---------------------------------------------------------------------------

_BLOG_RAW = {
    "total": 1234,
    "items": [
        {
            "title": "강남 <b>피부과</b> 여드름 후기",
            "link": "https://blog.naver.com/abc/123",
            "description": "<b>여드름</b> 압출 치료 받음 &amp; 친절했어요",
            "bloggername": "홍길동",
            "bloggerlink": "https://blog.naver.com/abc",
            "postdate": "20260501",
        },
        {
            "title": "점 제거 레이저 시술",
            "link": "https://blog.naver.com/xyz/9",
            "description": "레이저 시술 후기",
            "bloggername": "김블로거",
            "postdate": "20260420",
        },
    ],
}


class TestNaverBlogParse:
    def test_total_and_post_count(self):
        parsed = parse_naver_blog(_BLOG_RAW)
        assert parsed["total"] == 1234
        assert len(parsed["posts"]) == 2

    def test_html_tags_and_entities_stripped(self):
        parsed = parse_naver_blog(_BLOG_RAW)
        p0 = parsed["posts"][0]
        assert "<b>" not in p0["title"] and "<b>" not in p0["description"]
        assert "&amp;" not in p0["description"]
        assert p0["title"] == "강남 피부과 여드름 후기"

    def test_author_pii_not_preserved(self):
        parsed = parse_naver_blog(_BLOG_RAW)
        dumped = json.dumps(parsed, ensure_ascii=False)
        assert "홍길동" not in dumped
        assert "bloggername" not in dumped
        assert "bloggerlink" not in dumped

    def test_link_preserved_as_blog_seed(self):
        parsed = parse_naver_blog(_BLOG_RAW)
        assert parsed["posts"][0]["link"] == "https://blog.naver.com/abc/123"

    def test_keyword_frequency_empty_for_ai_extraction(self):
        # parse 는 빈 dict — AI 트랙이 description 에서 추출
        assert parse_naver_blog(_BLOG_RAW)["keyword_frequency"] == {}

    def test_model_validation(self):
        m = to_naver_blog(parse_naver_blog(_BLOG_RAW))
        assert m.total == 1234
        assert len(m.posts) == 2
        assert m.posts[0].link == "https://blog.naver.com/abc/123"

    def test_empty_items(self):
        parsed = parse_naver_blog({"total": 0, "items": []})
        assert parsed["posts"] == []


# ---------------------------------------------------------------------------
# 네이버 플레이스 (비공식 GraphQL visitorReviews)
# ---------------------------------------------------------------------------

def _load_place_fixture() -> dict:
    with open(_FIXTURE / "reviews_778531046.json", encoding="utf-8") as f:
        return json.load(f)


class TestNaverPlaceParse:
    def test_visitor_count_and_reviews(self):
        parsed = parse_place(_load_place_fixture(), "778531046")
        assert parsed["place_id"] == "778531046"
        assert isinstance(parsed["visitor_count"], int)
        assert len(parsed["reviews"]) >= 1

    def test_review_body_preserved(self):
        parsed = parse_place(_load_place_fixture(), "778531046")
        # 본문(body)은 임베딩 입력용으로 보존
        assert all("body" in r for r in parsed["reviews"])
        assert any(r["body"] for r in parsed["reviews"])

    def test_author_pii_not_preserved(self):
        parsed = parse_place(_load_place_fixture(), "778531046")
        dumped = json.dumps(parsed, ensure_ascii=False)
        for pii in ("author", "userIdno", "loginIdno", "nickname", "objectId", "imageUrl"):
            assert pii not in dumped, f"PII 누출: {pii}"

    def test_keyword_stats_empty_for_ai_extraction(self):
        # 네이버는 병원 카테고리 키워드 통계 미제공(실측 사실 8) → 빈 dict
        assert parse_place(_load_place_fixture(), "778531046")["keyword_stats"] == {}

    def test_model_validation_ignores_extra_reviews(self):
        # NaverPlace 모델엔 reviews 필드 없음 — extra="ignore" 로 무시되고 통과
        parsed = parse_place(_load_place_fixture(), "778531046")
        m = to_naver_place(parsed)
        assert isinstance(m.visitor_count, int)
        assert m.keyword_stats == {}

    def test_invalid_graphql_shape(self):
        # 비정상 응답(빈 dict) → 빈 reviews, 안전
        parsed = parse_place({}, "999")
        assert parsed["reviews"] == []
        assert parsed["place_id"] == "999"
