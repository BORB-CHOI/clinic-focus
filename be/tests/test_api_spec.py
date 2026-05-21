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
         patch("be.api.history.DynamoAdapter") as MockDB4:

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
        """q도 lat/lng도 없으면 에러."""
        with patch("be.api.search.db"):
            resp = client.get("/api/search")
            assert resp.status_code == 200  # 에러지만 200으로 반환 (스펙 확인 필요)
            body = resp.json()
            assert "error" in body
            assert body["error"]["code"] == "INVALID_PARAMETER"

    def test_with_sigungu_returns_data_meta(self, client):
        """시군구 검색 → {"data": [...], "meta": {...}}."""
        with patch("be.api.search.db") as mock_db:
            mock_db.list_hospitals_by_sigungu.return_value = []
            resp = client.get("/api/search?q=피부과&sigungu=성북구")
            assert resp.status_code == 200
            body = resp.json()
            assert "data" in body
            assert "meta" in body
            assert "search_mode" in body["meta"]


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
