"""API 스펙 준수 테스트 — API-FE-BE.md 기준.

DynamoDB 없이 mock으로 테스트.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from shared.models import (
    Classification,
    Confidence,
    Contact,
    DetailedSignals,
    HospitalMeta,
    Location,
    OperatingHours,
    SelfClaimSignal,
    BlogSignal,
    ReviewSignal,
    SignalContributions,
)


@pytest.fixture
def client():
    """DynamoDB mock으로 FastAPI 테스트 클라이언트 생성."""
    with patch("be.api.hospital.DynamoAdapter") as MockDB, \
         patch("be.api.search.DynamoAdapter") as MockDB2, \
         patch("be.api.feedback.DynamoAdapter") as MockDB3, \
         patch("be.api.history.DynamoAdapter") as MockDB4, \
         patch("be.api.specialties.DynamoAdapter") as MockDB5:

        from be.handlers.api import app
        return TestClient(app)


@pytest.fixture
def sample_hospital_meta():
    return HospitalMeta(
        hospital_id="test_001",
        name="테스트의원",
        location=Location(
            address="서울특별시 성북구 종암로 1",
            lat=37.6,
            lng=127.0,
            sido="서울",
            sigungu="성북구",
        ),
        contact=Contact(
            phone="02-1234-5678",
            website_url="http://test-clinic.com",
        ),
    )


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestHospitalDetailEndpoint:
    """GET /api/hospitals/{id} 스펙 테스트."""

    def test_not_found_returns_404(self, client):
        """존재하지 않는 병원 → 404."""
        with patch("be.api.hospital.db") as mock_db:
            mock_db.load_hospital_meta.return_value = None
            resp = client.get("/api/hospitals/nonexistent")
            assert resp.status_code == 404

    def test_found_returns_data_wrapper(self, client, sample_hospital_meta):
        """존재하는 병원 → {"data": {...}} 형태."""
        with patch("be.api.hospital.db") as mock_db:
            mock_db.load_hospital_meta.return_value = sample_hospital_meta
            mock_db.load_classification.return_value = None
            mock_db.load_description.return_value = None
            mock_db.load_services_and_doctors.return_value = None
            mock_db.load_related_hospitals.return_value = []
            mock_db.load_recent_changes.return_value = []
            mock_db.get_feedback_for_hospital.return_value = []

            resp = client.get("/api/hospitals/test_001")
            assert resp.status_code == 200

            body = resp.json()
            assert "data" in body
            data = body["data"]

            # 스펙 필수 필드 확인
            assert data["hospital_id"] == "test_001"
            assert data["name"] == "테스트의원"
            assert data["location"]["sido"] == "서울"
            assert data["location"]["sigungu"] == "성북구"
            assert "ai_description" in data
            assert "services" in data
            assert "excluded_services" in data
            assert "equipment" in data
            assert "doctors" in data
            assert "feedback_stats" in data
            assert "recent_changes" in data
            assert "related_hospitals" in data
            assert "metadata" in data


class TestSearchEndpoint:
    """GET /api/search 스펙 테스트."""

    def test_no_params_returns_error(self, client):
        """q·lat/lng·sigungu 다 없으면 400 INVALID_PARAMETER (API-FE-BE.md 라인 44·356)."""
        with patch("be.api.search.db"):
            resp = client.get("/api/search")
            assert resp.status_code == 400
            body = resp.json()
            assert "error" in body
            assert body["error"]["code"] == "INVALID_PARAMETER"

    def test_with_sigungu_returns_data_meta(self, client):
        """시군구 단독(카테고리) 검색 → DDB GSI 직접 조회 → {"data": [...], "meta": {...}}."""
        with patch("be.api.search.db") as mock_db:
            mock_db.list_hospitals_by_sigungu_light.return_value = []
            resp = client.get("/api/search?sigungu=성북구")
            assert resp.status_code == 200
            body = resp.json()
            assert "data" in body
            assert "meta" in body
            assert body["meta"]["search_mode"] == "category"

    def test_search_meta_has_total_and_has_more(self, client):
        """meta.total 은 전체 수, has_more = offset+limit < total."""
        with patch("be.api.search.db") as mock_db:
            # 경량 목록 25건 반환, limit=10, offset=0 → has_more=True, total=25
            mock_db.list_hospitals_by_sigungu_light.return_value = [
                {"hospital_id": f"h_{i:03d}", "name": f"병원{i}", "confidence_score": 80.0}
                for i in range(25)
            ]
            mock_db.load_hospital_meta.return_value = None  # 카드 None → data 빈 배열
            resp = client.get("/api/search?sigungu=강남구&limit=10&offset=0")
            assert resp.status_code == 200
            meta = resp.json()["meta"]
            assert meta["total"] == 25
            assert meta["has_more"] is True
            assert meta["limit"] == 10
            assert meta["offset"] == 0

    def test_search_last_page_has_more_false(self, client):
        """마지막 페이지 → has_more=False."""
        with patch("be.api.search.db") as mock_db:
            mock_db.list_hospitals_by_sigungu_light.return_value = [
                {"hospital_id": f"h_{i:03d}", "name": f"병원{i}", "confidence_score": 80.0}
                for i in range(5)
            ]
            mock_db.load_hospital_meta.return_value = None
            resp = client.get("/api/search?sigungu=강남구&limit=10&offset=0")
            assert resp.status_code == 200
            meta = resp.json()["meta"]
            assert meta["total"] == 5
            assert meta["has_more"] is False

    def test_search_limit_max_is_100(self, client):
        """limit 최대는 100(이전 50에서 상향). 101 이면 FastAPI 422."""
        with patch("be.api.search.db") as mock_db:
            mock_db.list_hospitals_by_sigungu_light.return_value = []
            resp = client.get("/api/search?sigungu=강남구&limit=101")
            # FastAPI le=100 validator 위반 → 422
            assert resp.status_code == 422

    def test_nl_search_fetch_cap_is_100(self, client):
        """자연어 검색은 FETCH_CAP=100 으로 retrieve_hospital 호출."""
        from shared.models import SearchQuery, SearchResult

        with patch("be.api.search.db") as mock_db, \
             patch("ai.retrieve_hospital") as mock_retrieve:
            mock_retrieve.return_value = []
            resp = client.get("/api/search?q=피부과&limit=10")
            assert resp.status_code == 200
            # retrieve_hospital 이 호출됐을 때 SearchQuery.limit == FETCH_CAP(100)
            call_args = mock_retrieve.call_args[0][0]
            assert call_args.limit == 100

    def test_nl_search_meta_has_total_independent_of_limit(self, client):
        """NL 결과 5건, limit=3 → total=5, has_more=True, data 3건."""
        from shared.models import SearchResult

        sample_meta = HospitalMeta(
            hospital_id="h_001",
            name="테스트의원",
            location=Location(address="서울", lat=37.5, lng=127.0, sido="서울", sigungu="강남구"),
            contact=Contact(website_url=None),
        )

        with patch("be.api.search.db") as mock_db, \
             patch("ai.retrieve_hospital") as mock_retrieve:
            mock_retrieve.return_value = [
                SearchResult(
                    hospital_id=f"h_{i:03d}",
                    similarity_score=0.9 - i * 0.1,
                    matched_focus=[],
                    query_interpretation=None,
                )
                for i in range(5)
            ]
            mock_db.load_hospital_meta.return_value = sample_meta
            mock_db.load_classification.return_value = None
            mock_db.load_description.return_value = None

            resp = client.get("/api/search?q=피부과&limit=3&offset=0")
            assert resp.status_code == 200
            body = resp.json()
            assert body["meta"]["total"] == 5
            assert body["meta"]["has_more"] is True
            assert len(body["data"]) == 3

    def test_category_with_specialty_uses_specialty_light(self, client):
        """specialty 있는 카테고리 검색 → list_hospitals_by_sigungu_specialty_light 호출."""
        with patch("be.api.search.db") as mock_db:
            mock_db.list_hospitals_by_sigungu_specialty_light.return_value = []
            resp = client.get("/api/search?sigungu=강남구&specialty=피부과")
            assert resp.status_code == 200
            mock_db.list_hospitals_by_sigungu_specialty_light.assert_called_once_with(
                "강남구", "피부과"
            )

    def test_natural_query_uses_retrieve_hospital(self, client):
        """자연어(q) 검색 → AI retrieve_hospital(KB Retrieve) 경유."""
        from shared.models import SearchResult

        with patch("be.api.search.db") as mock_db, \
             patch("ai.retrieve_hospital") as mock_retrieve:
            mock_retrieve.return_value = [
                SearchResult(hospital_id="h_001", similarity_score=0.9,
                             matched_focus=["여드름"], query_interpretation=None),
            ]
            # 카드 join 용 META/분류 — 간단화 위해 META 만 있고 분류 전인 케이스
            mock_db.load_hospital_meta.return_value = None  # 카드 None → 결과 0개여도 경로 검증
            resp = client.get("/api/search?q=여드름 잘 보는 피부과")
            assert resp.status_code == 200
            body = resp.json()
            assert body["meta"]["search_mode"] == "natural"
            mock_retrieve.assert_called_once()


class TestFeedbackEndpoint:
    """POST /api/feedback 스펙 테스트."""

    def test_submit_feedback_returns_201(self, client):
        """정상 피드백 → 201 + {"data": {"feedback_id": ...}}."""
        with patch("be.api.feedback.db") as mock_db:
            mock_db.check_duplicate_feedback.return_value = False
            mock_db.save_feedback.return_value = None

            resp = client.post("/api/feedback", json={
                "hospital_id": "test_001",
                "device_id": "d_test_device",
                "primary_focus": "일반 진료",
                "verdict": "agree",
            })
            assert resp.status_code == 201
            body = resp.json()
            assert "data" in body
            assert "feedback_id" in body["data"]
            assert "received_at" in body["data"]

    def test_duplicate_feedback_returns_error(self, client):
        """중복 피드백 → {"error": {"code": "DUPLICATE_FEEDBACK"}}."""
        with patch("be.api.feedback.db") as mock_db:
            mock_db.check_duplicate_feedback.return_value = True

            resp = client.post("/api/feedback", json={
                "hospital_id": "test_001",
                "device_id": "d_test_device",
                "primary_focus": "일반 진료",
                "verdict": "agree",
            })
            body = resp.json()
            assert "error" in body
            assert body["error"]["code"] == "DUPLICATE_FEEDBACK"


class TestSpecialtiesEndpoint:
    """GET /api/specialties 신규 엔드포인트 스펙 테스트."""

    def test_no_sigungu_returns_422(self, client):
        """sigungu 파라미터 없으면 FastAPI 422 (필수 파라미터)."""
        resp = client.get("/api/specialties")
        assert resp.status_code == 422

    def test_returns_data_meta_envelope(self, client):
        """정상 요청 → {"data": [...], "meta": {...}} 봉투."""
        with patch("be.api.specialties.db") as mock_db:
            mock_db.list_specialty_counts.return_value = (
                [{"specialty": "피부과", "count": 120}, {"specialty": "치과", "count": 85}],
                205,
            )
            resp = client.get("/api/specialties?sigungu=강남구")
            assert resp.status_code == 200
            body = resp.json()
            assert "data" in body
            assert "meta" in body

    def test_data_sorted_by_count_desc(self, client):
        """data 는 count 내림차순 정렬."""
        with patch("be.api.specialties.db") as mock_db:
            mock_db.list_specialty_counts.return_value = (
                [
                    {"specialty": "피부과", "count": 120},
                    {"specialty": "치과", "count": 85},
                    {"specialty": "한의원", "count": 40},
                ],
                245,
            )
            resp = client.get("/api/specialties?sigungu=강남구")
            data = resp.json()["data"]
            counts = [item["count"] for item in data]
            assert counts == sorted(counts, reverse=True)

    def test_meta_fields(self, client):
        """meta 에 sigungu·total_hospitals·total_specialties 포함."""
        with patch("be.api.specialties.db") as mock_db:
            mock_db.list_specialty_counts.return_value = (
                [{"specialty": "피부과", "count": 10}],
                10,
            )
            resp = client.get("/api/specialties?sigungu=강남구")
            meta = resp.json()["meta"]
            assert meta["sigungu"] == "강남구"
            assert "total_hospitals" in meta
            assert "total_specialties" in meta
            assert meta["total_specialties"] == 1

    def test_empty_sigungu_returns_400(self, client):
        """빈 sigungu 값 → 400."""
        with patch("be.api.specialties.db"):
            resp = client.get("/api/specialties?sigungu=")
            assert resp.status_code == 400
            assert resp.json()["error"]["code"] == "INVALID_PARAMETER"


class TestSearchSortOrder:
    """보조정렬 규칙 단위 테스트 (_sort_nl_results)."""

    def _make_card(self, hospital_id: str, name: str, confidence: int, similarity: float) -> dict:
        return {
            "hospital_id": hospital_id,
            "name": name,
            "confidence": {"score": confidence},
            "distance_km": None,
        }

    def test_relevance_preserves_retrieve_order(self):
        from be.api.search import _sort_nl_results

        # relevance 는 retrieve_hospital 이 '주력 강도'(빈도+primary_focus+코사인)로 이미
        # 정렬해 돌려준 순서를 보존해야 한다 — 여기서 similarity(코사인) 로 재정렬하면 주력
        # 랭킹을 덮어쓴다. 따라서 입력 순서 그대로 반환(코사인이 더 높은 c 가 뒤여도 유지).
        cards = [
            self._make_card("c", "C의원", 90, 0.9),  # 코사인 최고지만 입력상 1번 아님 → 보존
            self._make_card("a", "A의원", 80, 0.5),
            self._make_card("b", "B의원", 95, 0.6),
        ]
        score_map = {"a": 0.5, "b": 0.6, "c": 0.9}
        sorted_cards = _sort_nl_results(cards, "relevance", score_map=score_map)
        ids = [c["hospital_id"] for c in sorted_cards]
        assert ids == ["c", "a", "b"]  # 입력 순서 그대로 (재정렬 안 함)

    def test_confidence_sort(self):
        from be.api.search import _sort_nl_results

        cards = [
            self._make_card("a", "A의원", 70, 0.9),
            self._make_card("b", "B의원", 90, 0.5),
            self._make_card("c", "C의원", 90, 0.8),
        ]
        score_map = {"a": 0.9, "b": 0.5, "c": 0.8}
        sorted_cards = _sort_nl_results(cards, "confidence", score_map=score_map)
        ids = [c["hospital_id"] for c in sorted_cards]
        # confidence 90 동점: 유사도 0.8>0.5 이므로 c → b, 그 다음 a(70)
        assert ids == ["c", "b", "a"]

    def test_distance_sort(self):
        from be.api.search import _sort_nl_results

        cards = [
            {**self._make_card("a", "A의원", 80, 0.5), "distance_km": 2.0},
            {**self._make_card("b", "B의원", 90, 0.5), "distance_km": 1.0},
            {**self._make_card("c", "C의원", 70, 0.5), "distance_km": 1.0},
        ]
        sorted_cards = _sort_nl_results(cards, "distance")
        ids = [c["hospital_id"] for c in sorted_cards]
        # 거리 1.0 동점: confidence 90>70 이므로 b → c, 그 다음 a(2.0)
        assert ids == ["b", "c", "a"]
