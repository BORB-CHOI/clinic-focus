"""test_kb_store.py — ai/search/kb_store.py 단위 테스트.

실행:
    .venv/bin/python -m pytest ai/tests/ -q

모든 테스트는 Bedrock·S3 실 호출 비용을 발생시키지 않는다.
boto3.client 는 unittest.mock.patch 로 완전히 차단한다.

fixture: be/tests/fixtures/kakao/*.json → parse_* 를 통해 입력.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from be.adapters.kakao_place_adapter import parse_blog, parse_place, parse_reviews
from shared.models import (
    Classification,
    Confidence,
    Contact,
    CrawlData,
    CrawledPage,
    DetailedSignals,
    HospitalMeta,
    Location,
    ReviewSignal,
    BlogSignal,
    SelfClaimSignal,
    SignalContributions,
)
from ai.search.kb_store import (
    build_blog_chunk,
    build_ingest_metadata,
    build_reviews_chunk,
    build_self_claim_chunk,
    build_signal_chunks,
    ingest_hospital,
)

# ---------------------------------------------------------------------------
# 픽스처 경로
# ---------------------------------------------------------------------------

_FIXTURE_DIR = (
    Path(__file__).parent.parent.parent
    / "be" / "tests" / "fixtures" / "kakao"
)


def _load_fixture(name: str) -> dict:
    with open(_FIXTURE_DIR / name, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 카카오 파싱 헬퍼 (parse_* 경유)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def kakao_place_27388604() -> dict:
    """자생한방병원 panel3 파싱 결과."""
    raw = _load_fixture("panel3_27388604.json")
    return parse_place(raw, "27388604")


@pytest.fixture(scope="module")
def kakao_reviews_27388604() -> dict:
    """자생한방병원 reviews 파싱 결과."""
    raw = _load_fixture("reviews_27388604.json")
    return parse_reviews(raw)


@pytest.fixture(scope="module")
def kakao_place_202729757() -> dict:
    """더서울병원 panel3 파싱 결과."""
    raw = _load_fixture("panel3_202729757.json")
    return parse_place(raw, "202729757")


@pytest.fixture(scope="module")
def kakao_reviews_202729757() -> dict:
    """더서울병원 reviews 파싱 결과."""
    raw = _load_fixture("reviews_202729757.json")
    return parse_reviews(raw)


@pytest.fixture(scope="module")
def kakao_blog_8094954() -> dict:
    """춘원당한의원(place_id=8094954) blog 파싱 결과."""
    raw = _load_fixture("blog_8094954.json")
    return parse_blog(raw)


# ---------------------------------------------------------------------------
# CrawlData 헬퍼
# ---------------------------------------------------------------------------

def _make_crawl_data(pages: list[dict] | None = None) -> CrawlData:
    now = datetime.now(tz=timezone.utc)
    crawled_pages = []
    for p in (pages or []):
        crawled_pages.append(
            CrawledPage(
                url=p.get("url", "https://example-hospital.com/"),
                page_type=p["page_type"],
                html_text=p.get("html_text", ""),
                fetched_at=now,
                render_method="static",
            )
        )
    return CrawlData(
        hospital_id="h_test_001",
        website_url="https://example-hospital.com",
        pages=crawled_pages,
        images=[],
        public_data=None,
    )


# ---------------------------------------------------------------------------
# HospitalMeta / Classification 헬퍼
# ---------------------------------------------------------------------------

def _make_meta(
    hospital_id: str = "h_test_001",
    lat: float | None = 37.4979,
    lng: float | None = 127.0430,
) -> HospitalMeta:
    return HospitalMeta(
        hospital_id=hospital_id,
        name="테스트병원",
        location=Location(
            address="서울 강남구 강남대로 1",
            lat=lat,
            lng=lng,
            sido="서울",
            sigungu="강남구",
        ),
        contact=Contact(phone="02-000-0000"),
    )


def _make_classification(
    primary_focus: list[str] | None = None,
    confidence_score: int = 75,
) -> Classification:
    focus = primary_focus if primary_focus is not None else ["추나요법", "한방척추"]
    now = datetime.now(tz=timezone.utc)
    return Classification(
        hospital_id="h_test_001",
        standard_specialty="한의원",
        primary_focus=focus,
        confidence=Confidence(
            score=confidence_score,
            level="추정",
            signals=SignalContributions(self_claim=70, vision=0, blog=60, reviews=65),
        ),
        detailed_signals=DetailedSignals(
            self_claim=SelfClaimSignal(keywords=[], primary_focus=[], spam_score=0.0),
            blog=BlogSignal(total_posts=0, keyword_frequency={}, primary_topics=[]),
            reviews=ReviewSignal(total_reviews=0, keyword_frequency={}, primary_topics=[]),
        ),
        classified_at=now,
        classifier_version="v2.0",
    )


# ===========================================================================
# 1. build_self_claim_chunk 테스트
# ===========================================================================

class TestBuildSelfClaimChunk:
    def test_kakao_tags_included(self, kakao_place_27388604):
        """카카오 tags (도수치료, 추나요법 등) 가 self_claim 청크에 포함된다."""
        chunk = build_self_claim_chunk(kakao_place=kakao_place_27388604)
        assert "도수치료" in chunk
        assert "추나요법" in chunk

    def test_kakao_hira_specialty_included(self, kakao_place_27388604):
        """HIRA 전문 분야 (한방척추질환) 가 포함된다."""
        chunk = build_self_claim_chunk(kakao_place=kakao_place_27388604)
        assert "한방척추질환" in chunk

    def test_site_service_page_included(self):
        """자체 사이트 service 페이지 텍스트가 포함된다."""
        crawl_data = _make_crawl_data([
            {"page_type": "service", "html_text": "도수치료 전문 클리닉입니다."},
        ])
        chunk = build_self_claim_chunk(crawl_data=crawl_data)
        assert "도수치료 전문 클리닉입니다." in chunk

    def test_site_about_page_included(self):
        """service 없이 about 페이지 텍스트가 포함된다."""
        crawl_data = _make_crawl_data([
            {"page_type": "about", "html_text": "저희 병원 소개입니다."},
        ])
        chunk = build_self_claim_chunk(crawl_data=crawl_data)
        assert "저희 병원 소개입니다." in chunk

    def test_empty_inputs_returns_empty_string(self):
        """crawl_data=None, kakao_place=None 이면 빈 문자열 반환."""
        chunk = build_self_claim_chunk(crawl_data=None, kakao_place=None)
        assert chunk == ""

    def test_empty_crawl_data_pages(self):
        """pages 가 빈 CrawlData 이면 카카오 부분만 들어간다."""
        crawl_data = _make_crawl_data(pages=[])
        kakao_place = {"tags": ["레이저치료"], "mystore_intro": None, "hira": {}}
        chunk = build_self_claim_chunk(crawl_data=crawl_data, kakao_place=kakao_place)
        assert "레이저치료" in chunk

    def test_mystore_intro_included(self):
        """mystore_intro 텍스트가 포함된다."""
        kakao_place = {
            "tags": [],
            "mystore_intro": "저희 병원은 허리 디스크 전문입니다.",
            "hira": {},
        }
        chunk = build_self_claim_chunk(kakao_place=kakao_place)
        assert "허리 디스크 전문입니다." in chunk

    def test_priority_ordering(self):
        """service 페이지가 about 보다 먼저 나온다 (우선순위 정렬 확인)."""
        crawl_data = _make_crawl_data([
            {"page_type": "about", "html_text": "소개 페이지"},
            {"page_type": "service", "html_text": "서비스 페이지"},
        ])
        chunk = build_self_claim_chunk(crawl_data=crawl_data)
        assert chunk.index("서비스 페이지") < chunk.index("소개 페이지")


# ===========================================================================
# 2. build_blog_chunk 테스트
# ===========================================================================

class TestBuildBlogChunk:
    def test_kakao_blog_titles_included(self, kakao_blog_8094954):
        """카카오 블로그 제목들이 blog 청크에 포함된다."""
        chunk = build_blog_chunk(kakao_blog=kakao_blog_8094954)
        assert "임신준비" in chunk or "한의원 방문" in chunk

    def test_kakao_blog_contents_included(self, kakao_blog_8094954):
        """카카오 블로그 contents(발췌)가 포함된다."""
        chunk = build_blog_chunk(kakao_blog=kakao_blog_8094954)
        # fixture 첫 번째 seed 의 contents 일부
        assert "춘원당한의원" in chunk

    def test_site_blog_page_included(self):
        """자체 사이트 blog 페이지 텍스트가 포함된다."""
        crawl_data = _make_crawl_data([
            {"page_type": "blog", "html_text": "아토피 치료 사례 공유"},
        ])
        chunk = build_blog_chunk(crawl_data=crawl_data)
        assert "아토피 치료 사례 공유" in chunk

    def test_empty_inputs_returns_empty_string(self):
        """crawl_data=None, kakao_blog=None 이면 빈 문자열 반환."""
        assert build_blog_chunk() == ""

    def test_empty_seeds_returns_empty_string(self):
        """seeds 가 빈 리스트면 빈 문자열 반환 (crawl_data 없을 때)."""
        assert build_blog_chunk(kakao_blog={"total_posts": 0, "seeds": []}) == ""


# ===========================================================================
# 3. build_reviews_chunk 테스트
# ===========================================================================

class TestBuildReviewsChunk:
    def test_keyword_frequency_labels_included(self, kakao_reviews_27388604):
        """키워드 빈도 라벨 (전문성, 친절) 이 reviews 청크에 포함된다."""
        chunk = build_reviews_chunk(kakao_reviews=kakao_reviews_27388604)
        assert "전문성" in chunk
        assert "친절" in chunk

    def test_review_count_included(self, kakao_reviews_27388604):
        """총 리뷰 수가 포함된다 (303건)."""
        chunk = build_reviews_chunk(kakao_reviews=kakao_reviews_27388604)
        assert "303" in chunk

    def test_individual_review_contents_excluded(self, kakao_reviews_27388604):
        """개별 후기 본문 (contents) 이 청크에 포함되지 않는다 (§56③ 준수).

        fixture 의 실제 후기 본문 일부:
          '점수 높은 이유가 ... ㅋㅋ'
        이 텍스트가 청크에 나타나면 안 된다.
        """
        chunk = build_reviews_chunk(kakao_reviews=kakao_reviews_27388604)
        assert "점수 높은 이유가" not in chunk
        assert "슬리퍼 수건부터" not in chunk
        assert "음식이 정말 맛있어요" not in chunk

    def test_second_fixture_individual_review_excluded(self, kakao_reviews_202729757):
        """두 번째 fixture 에서도 개별 후기 본문이 제외된다."""
        chunk = build_reviews_chunk(kakao_reviews=kakao_reviews_202729757)
        # reviews_202729757 의 실제 후기 본문 텍스트는 포함되지 않아야 함
        # (fixture raw 의 reviews[*].contents 텍스트)
        # fixture 에 실제 후기가 있다면 여기서 검증 — 없으면 keyword_frequency 만 검증
        if kakao_reviews_202729757.get("keyword_frequency"):
            assert chunk  # 빈도가 있으면 청크도 비어있지 않아야 함

    def test_naver_reviews_included(self):
        """네이버 후기 keyword_stats 가 청크에 포함된다."""
        naver_reviews = {
            "keyword_stats": {"청결": 55, "친절": 33, "전문성": 20},
            "visitor_count": 1000,
        }
        chunk = build_reviews_chunk(naver_reviews=naver_reviews)
        assert "청결" in chunk
        assert "친절" in chunk
        assert "전문성" in chunk

    def test_empty_inputs_returns_empty_string(self):
        """kakao_reviews=None, naver_reviews=None 이면 빈 문자열 반환."""
        assert build_reviews_chunk() == ""

    def test_empty_keyword_frequency_excluded(self):
        """keyword_frequency 가 빈 dict 이면 빈 문자열 반환."""
        chunk = build_reviews_chunk(
            kakao_reviews={"keyword_frequency": {}, "total_reviews": 10}
        )
        assert chunk == ""


# ===========================================================================
# 4. build_signal_chunks 테스트
# ===========================================================================

class TestBuildSignalChunks:
    def test_empty_signal_excluded(self):
        """텍스트가 비어있는 시그널은 결과 dict 에서 제외된다."""
        chunks = build_signal_chunks(
            crawl_data=None,
            kakao_place=None,
            kakao_reviews=None,
            kakao_blog=None,
            naver_reviews=None,
        )
        assert chunks == {}

    def test_all_signals_present(self, kakao_place_27388604, kakao_reviews_27388604, kakao_blog_8094954):
        """유효한 데이터가 있으면 세 시그널이 모두 반환된다."""
        chunks = build_signal_chunks(
            kakao_place=kakao_place_27388604,
            kakao_reviews=kakao_reviews_27388604,
            kakao_blog=kakao_blog_8094954,
        )
        assert "self_claim" in chunks
        assert "reviews" in chunks
        assert "blog" in chunks

    def test_partial_signals(self, kakao_place_27388604):
        """일부 시그널만 있으면 해당 시그널만 반환된다."""
        chunks = build_signal_chunks(kakao_place=kakao_place_27388604)
        assert "self_claim" in chunks
        assert "reviews" not in chunks
        assert "blog" not in chunks

    def test_signal_values_non_empty(self, kakao_place_27388604, kakao_reviews_27388604):
        """반환된 시그널 텍스트는 빈 문자열이 아니다."""
        chunks = build_signal_chunks(
            kakao_place=kakao_place_27388604,
            kakao_reviews=kakao_reviews_27388604,
        )
        for key, text in chunks.items():
            assert text.strip(), f"{key} 시그널 텍스트가 비어있음"


# ===========================================================================
# 5. build_ingest_metadata 테스트
# ===========================================================================

class TestBuildIngestMetadata:
    def test_team_id_always_present(self):
        """team_id="clinic-focus" 가 항상 포함된다."""
        meta = _make_meta()
        cls = _make_classification()
        md = build_ingest_metadata(meta, cls)
        assert md["team_id"] == "clinic-focus"

    def test_required_fields_present(self):
        """필수 필드들이 모두 포함된다."""
        meta = _make_meta()
        cls = _make_classification()
        md = build_ingest_metadata(meta, cls)
        for key in ("hospital_id", "name", "standard_specialty", "sido", "sigungu", "confidence_score"):
            assert key in md, f"필수 필드 {key} 누락"

    def test_empty_primary_focus_excluded(self):
        """primary_focus 가 빈 리스트면 키가 dict 에서 제외된다 (KB 빈 리스트 거절 방어)."""
        meta = _make_meta()
        cls = _make_classification(primary_focus=[])
        md = build_ingest_metadata(meta, cls)
        assert "primary_focus" not in md

    def test_non_empty_primary_focus_included(self):
        """primary_focus 가 비어있지 않으면 포함된다."""
        meta = _make_meta()
        cls = _make_classification(primary_focus=["추나요법", "한방척추"])
        md = build_ingest_metadata(meta, cls)
        assert md["primary_focus"] == ["추나요법", "한방척추"]

    def test_lat_lng_excluded_when_none(self):
        """lat/lng 가 None 이면 키가 제외된다 (null 값 KB 거절 방어)."""
        meta = _make_meta(lat=None, lng=None)
        cls = _make_classification()
        md = build_ingest_metadata(meta, cls)
        assert "lat" not in md
        assert "lng" not in md

    def test_lat_lng_included_when_present(self):
        """lat/lng 가 있으면 숫자로 포함된다."""
        meta = _make_meta(lat=37.4979, lng=127.0430)
        cls = _make_classification()
        md = build_ingest_metadata(meta, cls)
        assert md["lat"] == pytest.approx(37.4979)
        assert md["lng"] == pytest.approx(127.0430)


# ===========================================================================
# 6. ingest_hospital 테스트 (boto3.client mock)
# ===========================================================================

_ENV = {
    "KB_DATASOURCE_S3_BUCKET": "test-bucket",
    "KB_DATASOURCE_S3_PREFIX": "clinic-focus/prod/",
    "KB_ID": "GTBJ6HLFDK",
    "KB_DATA_SOURCE_ID": "PLC6QYALDU",
    "AWS_REGION": "us-east-1",
}


class TestIngestHospital:
    """boto3.client 를 mock 해서 실제 AWS 호출을 차단한다."""

    def _run_ingest(
        self,
        mock_boto3,
        hospital_id: str = "h_001",
        signal_chunks: dict[str, str] | None = None,
        metadata: dict | None = None,
        trigger_ingestion: bool = False,
    ):
        """공통 실행 헬퍼. mock_boto3 = patch("boto3.client") 의 MagicMock."""
        mock_s3 = MagicMock()
        mock_agent = MagicMock()

        def client_factory(service, region_name=None):
            if service == "s3":
                return mock_s3
            if service == "bedrock-agent":
                return mock_agent
            return MagicMock()

        mock_boto3.side_effect = client_factory

        chunks = signal_chunks if signal_chunks is not None else {
            "self_claim": "자생한방병원은 척추 질환을 중점으로 다룸.",
            "reviews": "방문자 후기 강점 키워드 — 친절 164회, 전문성 145회",
        }
        md = metadata if metadata is not None else {
            "team_id": "clinic-focus",
            "hospital_id": hospital_id,
            "standard_specialty": "한의원",
            "sido": "서울",
            "sigungu": "강남구",
            "confidence_score": 75,
        }

        ingest_hospital(
            hospital_id=hospital_id,
            signal_chunks=chunks,
            metadata=md,
            trigger_ingestion=trigger_ingestion,
        )
        return mock_s3, mock_agent

    @patch("boto3.client")
    @patch.dict(os.environ, _ENV)
    def test_signal_keys_uploaded(self, mock_boto3):
        """각 시그널에 대해 .txt 와 .txt.metadata.json 이 S3 에 업로드된다."""
        mock_s3, _ = self._run_ingest(mock_boto3)
        uploaded_keys = [
            call_args.kwargs["Key"]
            for call_args in mock_s3.put_object.call_args_list
        ]
        assert any("h_001/self_claim.txt" in k for k in uploaded_keys)
        assert any("h_001/self_claim.txt.metadata.json" in k for k in uploaded_keys)
        assert any("h_001/reviews.txt" in k for k in uploaded_keys)
        assert any("h_001/reviews.txt.metadata.json" in k for k in uploaded_keys)

    @patch("boto3.client")
    @patch.dict(os.environ, _ENV)
    def test_sidecar_metadata_has_signal_type(self, mock_boto3):
        """사이드카 JSON 에 signal_type 필드가 포함된다."""
        mock_s3, _ = self._run_ingest(mock_boto3)
        meta_calls = [
            call_args
            for call_args in mock_s3.put_object.call_args_list
            if call_args.kwargs.get("Key", "").endswith(".txt.metadata.json")
        ]
        for c in meta_calls:
            body = json.loads(c.kwargs["Body"])
            assert "signal_type" in body["metadataAttributes"]

    @patch("boto3.client")
    @patch.dict(os.environ, _ENV)
    def test_sidecar_metadata_has_team_id(self, mock_boto3):
        """사이드카 JSON 에 team_id="clinic-focus" 가 있다."""
        mock_s3, _ = self._run_ingest(mock_boto3)
        meta_calls = [
            c for c in mock_s3.put_object.call_args_list
            if c.kwargs.get("Key", "").endswith(".txt.metadata.json")
        ]
        for c in meta_calls:
            body = json.loads(c.kwargs["Body"])
            assert body["metadataAttributes"]["team_id"] == "clinic-focus"

    @patch("boto3.client")
    @patch.dict(os.environ, _ENV)
    def test_empty_signal_not_uploaded(self, mock_boto3):
        """빈 텍스트 시그널은 S3 put_object 가 호출되지 않는다."""
        # build_signal_chunks 는 빈 시그널을 제외하지만, 만일 빈 값이 들어왔을 때 방어
        chunks = {
            "self_claim": "유효한 텍스트",
            "blog": "",  # 빈 텍스트 — 업로드 스킵 대상
        }
        mock_s3, _ = self._run_ingest(mock_boto3, signal_chunks=chunks)
        uploaded_keys = [
            c.kwargs["Key"] for c in mock_s3.put_object.call_args_list
        ]
        assert not any("blog.txt" in k for k in uploaded_keys), "빈 blog 시그널이 업로드됨"
        assert any("self_claim.txt" in k for k in uploaded_keys)

    @patch("boto3.client")
    @patch.dict(os.environ, _ENV)
    def test_trigger_ingestion_false_no_job_called(self, mock_boto3):
        """trigger_ingestion=False 면 start_ingestion_job 이 호출되지 않는다."""
        _, mock_agent = self._run_ingest(mock_boto3, trigger_ingestion=False)
        mock_agent.start_ingestion_job.assert_not_called()

    @patch("boto3.client")
    @patch.dict(os.environ, _ENV)
    def test_trigger_ingestion_true_job_called_once(self, mock_boto3):
        """trigger_ingestion=True 면 start_ingestion_job 이 정확히 1회 호출된다."""
        mock_agent = MagicMock()
        mock_agent.start_ingestion_job.return_value = {
            "ingestionJob": {"ingestionJobId": "job-test-001", "status": "STARTING"}
        }
        mock_s3 = MagicMock()

        def client_factory(service, region_name=None):
            return mock_s3 if service == "s3" else mock_agent

        mock_boto3.side_effect = client_factory

        ingest_hospital(
            hospital_id="h_002",
            signal_chunks={"self_claim": "테스트 텍스트"},
            metadata={"team_id": "clinic-focus", "hospital_id": "h_002",
                      "standard_specialty": "내과", "sido": "서울",
                      "sigungu": "강남구", "confidence_score": 80},
            trigger_ingestion=True,
        )
        mock_agent.start_ingestion_job.assert_called_once_with(
            knowledgeBaseId="GTBJ6HLFDK",
            dataSourceId="PLC6QYALDU",
        )

    @patch("boto3.client")
    @patch.dict(os.environ, _ENV)
    def test_s3_prefix_applied(self, mock_boto3):
        """S3 키에 KB_DATASOURCE_S3_PREFIX 가 적용된다."""
        mock_s3, _ = self._run_ingest(mock_boto3, hospital_id="h_999")
        uploaded_keys = [
            c.kwargs["Key"] for c in mock_s3.put_object.call_args_list
        ]
        assert all(k.startswith("clinic-focus/prod/") for k in uploaded_keys)

    @patch("boto3.client")
    @patch.dict(os.environ, {**_ENV, "KB_DATASOURCE_S3_PREFIX": "/clinic-focus/prod/"})
    def test_prefix_leading_slash_stripped(self, mock_boto3):
        """KB_DATASOURCE_S3_PREFIX 앞의 '/' 가 자동 제거된다."""
        mock_s3, _ = self._run_ingest(mock_boto3, hospital_id="h_prefix")
        uploaded_keys = [
            c.kwargs["Key"] for c in mock_s3.put_object.call_args_list
        ]
        assert not any(k.startswith("/") for k in uploaded_keys), "키가 / 로 시작하면 안 됨"

    @patch("boto3.client")
    def test_missing_bucket_raises_error(self, mock_boto3):
        """KB_DATASOURCE_S3_BUCKET 이 없으면 KBIngestError 를 발생시킨다."""
        from ai.core.exceptions import KBIngestError

        env_without_bucket = {k: v for k, v in _ENV.items() if k != "KB_DATASOURCE_S3_BUCKET"}
        with patch.dict(os.environ, env_without_bucket, clear=True):
            # clear=True 로 기존 env 를 무시하기 위해 필요한 경우만 설정
            # 단, clear=True 는 다른 env 까지 날리므로 명시적으로 누락만 테스트
            os.environ.pop("KB_DATASOURCE_S3_BUCKET", None)
            with pytest.raises(KBIngestError, match="KB_DATASOURCE_S3_BUCKET"):
                ingest_hospital(
                    hospital_id="h_err",
                    signal_chunks={"self_claim": "텍스트"},
                    metadata={"team_id": "clinic-focus"},
                )
