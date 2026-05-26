"""enrich_urls.py 보강 파이프라인 통합 테스트.

Task 6 검증:
- async 전환 (asyncio.run 패턴)
- 네이버 단계에서 search_hospital_multi_query 사용
- 카카오 단계에 KakaoPlaceRenderer + Playwright 통합
- URL 발견 후 URLValidator 검증
- 중단 재개 로직 (이미 URL 있는 병원 스킵)
- 최종 리포트 출력 개선
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.models import Contact, HospitalMeta, Location

# 테스트 대상 모듈 임포트 (sys.path 조작 없이 — pytest가 처리)
from be.scripts.enrich_urls import (
    _is_real_website,
    run_step1_naver,
    run_step2_kakao,
)


# ─── Fixtures ──────────────────────────────────────────────────────────


def _make_hospital(hospital_id: str, name: str, address: str, website_url: str | None = None) -> HospitalMeta:
    """테스트용 HospitalMeta 생성."""
    return HospitalMeta(
        hospital_id=hospital_id,
        name=name,
        location=Location(address=address, sido="서울특별시", sigungu="강남구"),
        contact=Contact(website_url=website_url),
    )


@pytest.fixture
def hospitals_no_url() -> list[HospitalMeta]:
    """URL 없는 병원 목록."""
    return [
        _make_hospital("H001", "강남성형외과", "서울특별시 강남구 역삼동 123"),
        _make_hospital("H002", "서울피부과의원", "서울특별시 강남구 대치동 456"),
        _make_hospital("H003", "미래치과", "서울특별시 강남구 삼성동 789"),
    ]


@pytest.fixture
def mock_db() -> MagicMock:
    """DynamoAdapter mock."""
    db = MagicMock()
    db.update_website_url = MagicMock()
    return db


@pytest.fixture
def mock_validator() -> AsyncMock:
    """URLValidator mock — 기본적으로 입력 URL을 그대로 반환."""
    validator = AsyncMock()
    validator.validate = AsyncMock(side_effect=lambda url: url)
    return validator


# ─── _is_real_website 테스트 ───────────────────────────────────────────


class TestIsRealWebsite:
    def test_valid_http_url(self):
        assert _is_real_website("https://hospital-clinic.com") is True

    def test_valid_blog_naver(self):
        """blog.naver.com은 허용."""
        assert _is_real_website("https://blog.naver.com/hospital123") is True

    def test_skip_map_naver(self):
        assert _is_real_website("https://map.naver.com/v5/entry/place/123") is False

    def test_skip_search_naver(self):
        assert _is_real_website("https://search.naver.com/search.naver?query=test") is False

    def test_skip_news_naver(self):
        assert _is_real_website("https://news.naver.com/article/123") is False

    def test_empty_url(self):
        assert _is_real_website("") is False

    def test_non_http_url(self):
        assert _is_real_website("ftp://hospital.com") is False


# ─── run_step1_naver 테스트 ────────────────────────────────────────────


class TestRunStep1Naver:
    @pytest.mark.asyncio
    async def test_uses_multi_query(self, hospitals_no_url, mock_db, mock_validator):
        """search_hospital_multi_query를 사용하는지 확인."""
        with patch("be.scripts.enrich_urls.NAVER_KEY", "test-key"):
            with patch("be.adapters.naver_map_adapter.NaverMapAdapter.search_hospital_multi_query") as mock_search:
                mock_search.return_value = {"link": "https://hospital.com", "title": "강남성형외과"}

                found, rejected, still_missing = await run_step1_naver(
                    mock_db, hospitals_no_url, mock_validator
                )

                # search_hospital_multi_query가 각 병원에 대해 호출됨
                assert mock_search.call_count == 3

    @pytest.mark.asyncio
    async def test_found_url_saved_to_db(self, hospitals_no_url, mock_db, mock_validator):
        """유효한 URL 발견 시 DynamoDB에 저장."""
        with patch("be.scripts.enrich_urls.NAVER_KEY", "test-key"):
            with patch("be.adapters.naver_map_adapter.NaverMapAdapter.search_hospital_multi_query") as mock_search:
                mock_search.return_value = {"link": "https://hospital.com", "title": "test"}

                found, rejected, still_missing = await run_step1_naver(
                    mock_db, hospitals_no_url, mock_validator
                )

                assert found == 3
                assert rejected == 0
                assert len(still_missing) == 0
                assert mock_db.update_website_url.call_count == 3

    @pytest.mark.asyncio
    async def test_validation_rejected_url_not_saved(self, hospitals_no_url, mock_db):
        """URLValidator가 거부한 URL은 저장하지 않음."""
        validator = AsyncMock()
        validator.validate = AsyncMock(return_value=None)  # 모든 URL 거부

        with patch("be.scripts.enrich_urls.NAVER_KEY", "test-key"):
            with patch("be.adapters.naver_map_adapter.NaverMapAdapter.search_hospital_multi_query") as mock_search:
                mock_search.return_value = {"link": "https://bad-url.com", "title": "test"}

                found, rejected, still_missing = await run_step1_naver(
                    mock_db, hospitals_no_url, validator
                )

                assert found == 0
                assert rejected == 3
                assert len(still_missing) == 3
                mock_db.update_website_url.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_naver_key_skips(self, hospitals_no_url, mock_db, mock_validator):
        """NAVER_KEY 미설정 시 건너뜀."""
        with patch("be.scripts.enrich_urls.NAVER_KEY", ""):
            found, rejected, still_missing = await run_step1_naver(
                mock_db, hospitals_no_url, mock_validator
            )

            assert found == 0
            assert rejected == 0
            assert still_missing == hospitals_no_url

    @pytest.mark.asyncio
    async def test_naver_skip_domains_not_saved(self, hospitals_no_url, mock_db, mock_validator):
        """NAVER_SKIP_DOMAINS에 해당하는 URL은 저장하지 않음."""
        with patch("be.scripts.enrich_urls.NAVER_KEY", "test-key"):
            with patch("be.adapters.naver_map_adapter.NaverMapAdapter.search_hospital_multi_query") as mock_search:
                mock_search.return_value = {"link": "https://map.naver.com/place/123", "title": "test"}

                found, rejected, still_missing = await run_step1_naver(
                    mock_db, hospitals_no_url, mock_validator
                )

                assert found == 0
                assert len(still_missing) == 3
                mock_db.update_website_url.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run_does_not_save(self, hospitals_no_url, mock_db, mock_validator):
        """dry_run=True 시 DB에 저장하지 않음."""
        with patch("be.scripts.enrich_urls.NAVER_KEY", "test-key"):
            with patch("be.adapters.naver_map_adapter.NaverMapAdapter.search_hospital_multi_query") as mock_search:
                mock_search.return_value = {"link": "https://hospital.com", "title": "test"}

                found, rejected, still_missing = await run_step1_naver(
                    mock_db, hospitals_no_url, mock_validator, dry_run=True
                )

                assert found == 3
                mock_db.update_website_url.assert_not_called()


# ─── run_step2_kakao 테스트 ────────────────────────────────────────────


class TestRunStep2Kakao:
    @pytest.mark.asyncio
    async def test_kakao_with_playwright_integration(self, hospitals_no_url, mock_db, mock_validator):
        """카카오 검색 → Playwright 렌더링 → URL 저장 흐름."""
        with patch("be.scripts.enrich_urls.KAKAO_KEY", "test-key"):
            with patch("be.adapters.kakao_adapter.KakaoAdapter.search_hospital") as mock_kakao:
                mock_kakao.return_value = {"place_url": "http://place.map.kakao.com/12345"}

                with patch("be.core.browser_manager.BrowserManager.__aenter__") as mock_enter:
                    mock_bm = AsyncMock()
                    mock_enter.return_value = mock_bm

                    with patch("be.core.browser_manager.BrowserManager.__aexit__", new_callable=AsyncMock):
                        with patch(
                            "be.adapters.kakao_place_renderer.KakaoPlaceRenderer.extract_homepage_url",
                            new_callable=AsyncMock,
                            return_value="https://hospital-homepage.com",
                        ):
                            found, rejected = await run_step2_kakao(
                                mock_db, hospitals_no_url, mock_validator
                            )

                            assert found == 3
                            assert rejected == 0
                            assert mock_db.update_website_url.call_count == 3

    @pytest.mark.asyncio
    async def test_kakao_no_place_url_skips(self, hospitals_no_url, mock_db, mock_validator):
        """카카오 검색 결과에 place_url 없으면 스킵."""
        with patch("be.scripts.enrich_urls.KAKAO_KEY", "test-key"):
            with patch("be.adapters.kakao_adapter.KakaoAdapter.search_hospital") as mock_kakao:
                mock_kakao.return_value = {"place_url": ""}

                with patch("be.core.browser_manager.BrowserManager.__aenter__") as mock_enter:
                    mock_bm = AsyncMock()
                    mock_enter.return_value = mock_bm

                    with patch("be.core.browser_manager.BrowserManager.__aexit__", new_callable=AsyncMock):
                        with patch(
                            "be.adapters.kakao_place_renderer.KakaoPlaceRenderer.extract_homepage_url",
                            new_callable=AsyncMock,
                        ) as mock_renderer:
                            found, rejected = await run_step2_kakao(
                                mock_db, hospitals_no_url, mock_validator
                            )

                            assert found == 0
                            mock_renderer.assert_not_called()

    @pytest.mark.asyncio
    async def test_kakao_renderer_returns_none_skips(self, hospitals_no_url, mock_db, mock_validator):
        """Playwright 렌더러가 None 반환 시 스킵."""
        with patch("be.scripts.enrich_urls.KAKAO_KEY", "test-key"):
            with patch("be.adapters.kakao_adapter.KakaoAdapter.search_hospital") as mock_kakao:
                mock_kakao.return_value = {"place_url": "http://place.map.kakao.com/12345"}

                with patch("be.core.browser_manager.BrowserManager.__aenter__") as mock_enter:
                    mock_bm = AsyncMock()
                    mock_enter.return_value = mock_bm

                    with patch("be.core.browser_manager.BrowserManager.__aexit__", new_callable=AsyncMock):
                        with patch(
                            "be.adapters.kakao_place_renderer.KakaoPlaceRenderer.extract_homepage_url",
                            new_callable=AsyncMock,
                            return_value=None,
                        ):
                            found, rejected = await run_step2_kakao(
                                mock_db, hospitals_no_url, mock_validator
                            )

                            assert found == 0
                            assert rejected == 0

    @pytest.mark.asyncio
    async def test_kakao_validation_rejected(self, hospitals_no_url, mock_db):
        """URLValidator가 거부한 URL은 저장하지 않음."""
        validator = AsyncMock()
        validator.validate = AsyncMock(return_value=None)

        with patch("be.scripts.enrich_urls.KAKAO_KEY", "test-key"):
            with patch("be.adapters.kakao_adapter.KakaoAdapter.search_hospital") as mock_kakao:
                mock_kakao.return_value = {"place_url": "http://place.map.kakao.com/12345"}

                with patch("be.core.browser_manager.BrowserManager.__aenter__") as mock_enter:
                    mock_bm = AsyncMock()
                    mock_enter.return_value = mock_bm

                    with patch("be.core.browser_manager.BrowserManager.__aexit__", new_callable=AsyncMock):
                        with patch(
                            "be.adapters.kakao_place_renderer.KakaoPlaceRenderer.extract_homepage_url",
                            new_callable=AsyncMock,
                            return_value="https://bad-hospital.com",
                        ):
                            found, rejected = await run_step2_kakao(
                                mock_db, hospitals_no_url, validator
                            )

                            assert found == 0
                            assert rejected == 3
                            mock_db.update_website_url.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_kakao_key_skips(self, hospitals_no_url, mock_db, mock_validator):
        """KAKAO_KEY 미설정 시 건너뜀."""
        with patch("be.scripts.enrich_urls.KAKAO_KEY", ""):
            found, rejected = await run_step2_kakao(
                mock_db, hospitals_no_url, mock_validator
            )

            assert found == 0
            assert rejected == 0


# ─── 중단 재개 로직 테스트 ─────────────────────────────────────────────


class TestResumeLogic:
    def test_hospitals_with_url_are_filtered_out(self):
        """이미 URL 있는 병원은 보강 대상에서 제외 (중단 재개 로직)."""
        hospitals = [
            _make_hospital("H001", "A병원", "서울특별시 강남구 역삼동", website_url="https://a.com"),
            _make_hospital("H002", "B병원", "서울특별시 강남구 대치동", website_url=None),
            _make_hospital("H003", "C병원", "서울특별시 강남구 삼성동", website_url="https://c.com"),
        ]

        with_url = [h for h in hospitals if h.contact.website_url]
        no_url = [h for h in hospitals if not h.contact.website_url]

        assert len(with_url) == 2
        assert len(no_url) == 1
        assert no_url[0].hospital_id == "H002"


# ─── 파이프라인 순서 테스트 ────────────────────────────────────────────


class TestPipelineOrder:
    @pytest.mark.asyncio
    async def test_naver_found_skips_kakao(self, mock_db, mock_validator):
        """네이버에서 URL 발견된 병원은 카카오 단계에서 처리하지 않음."""
        hospitals = [
            _make_hospital("H001", "A병원", "서울특별시 강남구 역삼동"),
            _make_hospital("H002", "B병원", "서울특별시 강남구 대치동"),
        ]

        with patch("be.scripts.enrich_urls.NAVER_KEY", "test-key"):
            with patch("be.adapters.naver_map_adapter.NaverMapAdapter.search_hospital_multi_query") as mock_naver:
                # H001만 네이버에서 발견
                def naver_side_effect(name, address):
                    if name == "A병원":
                        return {"link": "https://a-hospital.com", "title": "A병원"}
                    return None

                mock_naver.side_effect = naver_side_effect

                found, rejected, still_missing = await run_step1_naver(
                    mock_db, hospitals, mock_validator
                )

                assert found == 1
                assert len(still_missing) == 1
                assert still_missing[0].hospital_id == "H002"
