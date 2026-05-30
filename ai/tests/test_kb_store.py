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
    _enrich_with_synonyms,
    build_blog_chunk,
    build_ingest_metadata,
    build_reviews_chunk,
    build_self_claim_chunk,
    build_signal_chunks,
    ingest_hospital,
    retrieve_hospital,
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


class TestSynonymEnrichment:
    """문서-측 동의어 주입(_enrich_with_synonyms) — '사마귀≠심상성 우췌' 양방향 매칭."""

    def test_reverse_injection_academic_to_common(self):
        """본문에 학명만 있어도 일반어가 부착된다 (사용자가 '사마귀'로 검색 가능)."""
        out = _enrich_with_synonyms("저희 의원은 심상성 우췌 냉동요법을 시행합니다.")
        assert "사마귀" in out
        assert "[관련 의학 용어]" in out

    def test_forward_injection_common_to_academic(self):
        """본문에 일반어가 있으면 학명·영문이 부착된다."""
        out = _enrich_with_synonyms("사마귀 치료를 전문으로 합니다.")
        assert "심상성 우췌" in out
        assert "verruca" in out

    def test_short_key_no_false_trigger(self):
        """len<2 키(점·목·침·냉)는 부분문자열 오매칭을 일으키지 않는다."""
        out = _enrich_with_synonyms("이 시점에 주목해 주세요. 목요일 일정 안내입니다.")
        assert "[관련 의학 용어]" not in out

    def test_no_match_returns_unchanged(self):
        """의료 키워드가 없으면 원문 그대로 반환한다."""
        text = "주차 가능하며 친절하게 안내해 드립니다."
        assert _enrich_with_synonyms(text) == text

    def test_empty_returns_empty(self):
        assert _enrich_with_synonyms("") == ""

    def test_no_duplicate_terms_added(self):
        """이미 본문에 있는 표현은 중복 부착하지 않는다 (정확 일치 기준)."""
        out = _enrich_with_synonyms("사마귀 심상성 우췌 둘 다 언급")
        added = out.split("[관련 의학 용어]")[-1] if "[관련 의학 용어]" in out else ""
        added_terms = [t.strip() for t in added.split(",")]
        # 본문에 이미 있는 정확한 표현은 추가 목록에 없어야 (substring 인 "심상성 사마귀" 등은 허용)
        assert "사마귀" not in added_terms
        assert "심상성 우췌" not in added_terms

    def test_build_signal_chunks_enriches_self_claim(self):
        """build_signal_chunks 의 self_claim 청크가 동의어 주입을 거친다."""
        from datetime import datetime, timezone
        from shared.models import CrawlData, CrawledPage

        crawl = CrawlData(
            hospital_id="h1",
            website_url="https://x.kr",
            pages=[CrawledPage(
                url="https://x.kr",
                page_type="main",
                html_text="심상성 우췌 냉동요법 클리닉입니다.",
                fetched_at=datetime.now(tz=timezone.utc),
            )],
            images=[],
        )
        chunks = build_signal_chunks(crawl_data=crawl)
        assert "self_claim" in chunks
        assert "사마귀" in chunks["self_claim"]  # 문서-측 주입으로 일반어 추가됨


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


# ===========================================================================
# 7. retrieve_hospital 테스트 (bedrock-agent-runtime mock)
# ===========================================================================

_RETRIEVE_ENV = {
    "KB_ID": "GTBJ6HLFDK",
    "AWS_REGION": "us-east-1",
}

# KB Retrieve API 가 반환하는 raw result 샘플 팩토리
def _make_kb_result(
    hospital_id: str,
    score: float,
    name: str = "테스트병원",
    specialty: str = "피부과",
    primary_focus: list[str] | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> dict:
    """KB Retrieve retrievalResults 항목 mock 데이터를 생성한다."""
    md: dict = {
        "team_id": "clinic-focus",
        "hospital_id": hospital_id,
        "name": name,
        "standard_specialty": specialty,
        "sido": "서울",
        "sigungu": "강남구",
        "confidence_score": 80,
    }
    if primary_focus is not None:
        md["primary_focus"] = primary_focus
    if lat is not None:
        md["lat"] = lat
    if lng is not None:
        md["lng"] = lng
    return {
        "score": score,
        "metadata": md,
        "content": {"text": "샘플 본문 텍스트"},
    }


class TestRetrieveHospital:
    """retrieve_hospital 단위 테스트. boto3.client 를 mock 해 실 AWS 호출을 차단한다."""

    def _make_query(self, **kwargs) -> "SearchQuery":
        from shared.models import SearchQuery
        defaults = {"query_text": "여드름 잘 보는 피부과"}
        defaults.update(kwargs)
        return SearchQuery(**defaults)

    # (a) 필터에 team_id="clinic-focus" 가 항상 포함된다
    @patch("boto3.client")
    @patch.dict(os.environ, _RETRIEVE_ENV)
    def test_filter_always_includes_team_id(self, mock_boto3):
        """KB Retrieve 호출 시 team_id="clinic-focus" 필터가 반드시 포함된다."""
        mock_runtime = MagicMock()
        mock_runtime.retrieve.return_value = {
            "retrievalResults": [_make_kb_result("h_001", 0.9)]
        }
        mock_boto3.return_value = mock_runtime

        query = self._make_query()
        retrieve_hospital(query)

        call_kwargs = mock_runtime.retrieve.call_args[1]
        kb_filter = (
            call_kwargs["retrievalConfiguration"]["vectorSearchConfiguration"]["filter"]
        )

        # 단일 조건 또는 andAll 안에 team_id 조건이 있어야 한다
        def _has_team_id_filter(f: dict) -> bool:
            if f.get("equals", {}).get("key") == "team_id":
                return f["equals"]["value"] == "clinic-focus"
            for cond in f.get("andAll", []):
                if _has_team_id_filter(cond):
                    return True
            return False

        assert _has_team_id_filter(kb_filter), f"team_id 필터 없음: {kb_filter}"

    # (a-2) process_query 연동 — 추론 진료과가 메타필터에 들어가고 동의어 확장본으로 검색
    @patch("boto3.client")
    @patch.dict(os.environ, _RETRIEVE_ENV)
    def test_query_processor_infers_specialty_and_expands(self, mock_boto3):
        """specialty 미지정 의료 쿼리 → process_query 가 진료과를 추론해 필터에 넣고,
        동의어 확장본을 KB Retrieve 쿼리 텍스트로 사용한다."""
        mock_runtime = MagicMock()
        mock_runtime.retrieve.return_value = {
            "retrievalResults": [_make_kb_result("h_001", 0.9)]
        }
        mock_boto3.return_value = mock_runtime

        # "사마귀" → 피부과 추론 + 동의어(냉동치료 등) 확장. specialty 명시 안 함.
        query = self._make_query(query_text="사마귀 어디가 좋을까")
        results = retrieve_hospital(query)

        call_kwargs = mock_runtime.retrieve.call_args[1]
        kb_filter = (
            call_kwargs["retrievalConfiguration"]["vectorSearchConfiguration"]["filter"]
        )
        retrieve_text = call_kwargs["retrievalQuery"]["text"]

        def _specialty_in_filter(f: dict, value: str) -> bool:
            if f.get("equals", {}).get("key") == "standard_specialty":
                return f["equals"]["value"] == value
            return any(_specialty_in_filter(c, value) for c in f.get("andAll", []))

        assert _specialty_in_filter(kb_filter, "피부과"), f"추론 진료과 필터 없음: {kb_filter}"
        assert retrieve_text != "사마귀 어디가 좋을까", "동의어 확장이 적용되지 않음"
        assert "사마귀" in retrieve_text
        # query_interpretation("이렇게 이해했어요") 가 결과에 채워져야 한다
        assert results and results[0].query_interpretation is not None
        assert "사마귀" in results[0].query_interpretation
        assert "피부과" in results[0].query_interpretation

    # (a-3) 사용자가 specialty 를 명시하면 추론값보다 우선한다
    @patch("boto3.client")
    @patch.dict(os.environ, _RETRIEVE_ENV)
    def test_explicit_specialty_overrides_inference(self, mock_boto3):
        """query.specialty 가 있으면 process_query 추론값을 덮어쓰지 않고 명시값을 쓴다."""
        mock_runtime = MagicMock()
        mock_runtime.retrieve.return_value = {
            "retrievalResults": [_make_kb_result("h_001", 0.9)]
        }
        mock_boto3.return_value = mock_runtime

        # "사마귀"는 피부과를 추론하지만 사용자가 가정의학과를 명시 → 명시값 우선
        query = self._make_query(query_text="사마귀 어디가 좋을까", specialty="가정의학과")
        retrieve_hospital(query)

        call_kwargs = mock_runtime.retrieve.call_args[1]
        kb_filter = (
            call_kwargs["retrievalConfiguration"]["vectorSearchConfiguration"]["filter"]
        )

        def _specialty_value(f: dict) -> str | None:
            if f.get("equals", {}).get("key") == "standard_specialty":
                return f["equals"]["value"]
            for c in f.get("andAll", []):
                v = _specialty_value(c)
                if v is not None:
                    return v
            return None

        assert _specialty_value(kb_filter) == "가정의학과"

    # (b) 같은 hospital_id 여러 result → 최고 score 1개로 dedup
    @patch("boto3.client")
    @patch.dict(os.environ, _RETRIEVE_ENV)
    def test_dedup_same_hospital_id_keeps_best_score(self, mock_boto3):
        """같은 hospital_id 에서 여러 청크 매칭 시 최고 score 1개만 남긴다."""
        mock_runtime = MagicMock()
        mock_runtime.retrieve.return_value = {
            "retrievalResults": [
                _make_kb_result("h_dupe", 0.75),   # 낮은 score
                _make_kb_result("h_dupe", 0.92),   # 높은 score — 이것만 살아야 함
                _make_kb_result("h_dupe", 0.60),   # 더 낮은 score
                _make_kb_result("h_other", 0.80),
            ]
        }
        mock_boto3.return_value = mock_runtime

        query = self._make_query(limit=10)
        results = retrieve_hospital(query)

        hospital_ids = [r.hospital_id for r in results]
        assert hospital_ids.count("h_dupe") == 1, "h_dupe 가 dedup 되지 않아 중복 존재"

        # h_dupe 결과의 similarity_score 가 최고값(0.92)이어야 한다
        h_dupe_result = next(r for r in results if r.hospital_id == "h_dupe")
        assert h_dupe_result.similarity_score == pytest.approx(0.92, abs=1e-4)

    # (c) SearchResult 매핑 정확
    @patch("boto3.client")
    @patch.dict(os.environ, _RETRIEVE_ENV)
    def test_search_result_mapping(self, mock_boto3):
        """KB 결과가 SearchResult 필드에 정확히 매핑된다."""
        mock_runtime = MagicMock()
        mock_runtime.retrieve.return_value = {
            "retrievalResults": [
                _make_kb_result(
                    "h_map_test",
                    0.88,
                    specialty="피부과",
                    primary_focus=["여드름", "미용 시술"],
                )
            ]
        }
        mock_boto3.return_value = mock_runtime

        from shared.models import SearchResult
        query = self._make_query()
        results = retrieve_hospital(query)

        assert len(results) == 1
        r = results[0]
        assert isinstance(r, SearchResult)
        assert r.hospital_id == "h_map_test"
        assert r.similarity_score == pytest.approx(0.88, abs=1e-4)
        assert r.distance_km is None  # 위치 없으므로 None
        assert "여드름" in r.matched_focus
        assert "미용 시술" in r.matched_focus

    # (d) 빈 결과 fallback — 필터 완화 후 재시도
    @patch("boto3.client")
    @patch.dict(os.environ, _RETRIEVE_ENV)
    def test_empty_result_fallback_relaxes_filter(self, mock_boto3):
        """1차 결과 0건 시 지역/specialty/confidence 필터를 완화해 재시도한다."""
        mock_runtime = MagicMock()
        # 1차 호출(엄격한 필터) → 빈 결과
        # 2차 호출(완화된 필터) → 결과 있음
        mock_runtime.retrieve.side_effect = [
            {"retrievalResults": []},
            {"retrievalResults": [_make_kb_result("h_fallback", 0.70)]},
        ]
        mock_boto3.return_value = mock_runtime

        query = self._make_query(sigungu="강남구", specialty="피부과", min_confidence=80)
        results = retrieve_hospital(query)

        assert mock_runtime.retrieve.call_count == 2, "fallback 재시도가 발생하지 않음"
        assert len(results) == 1
        assert results[0].hospital_id == "h_fallback"

    # (d-2) 빈 결과 fallback 없을 때 빈 리스트 반환
    @patch("boto3.client")
    @patch.dict(os.environ, _RETRIEVE_ENV)
    def test_empty_result_no_fallback_when_no_extra_filters(self, mock_boto3):
        """필터가 team_id 만인 경우 fallback 없이 빈 리스트를 반환한다."""
        mock_runtime = MagicMock()
        mock_runtime.retrieve.return_value = {"retrievalResults": []}
        mock_boto3.return_value = mock_runtime

        # 위치/지역/specialty 없는 순수 자연어 쿼리 → fallback 분기 없이 종료.
        # 의료 키워드가 없어 process_query 가 진료과를 추론하지 않는 쿼리를 써야
        # effective_specialty 가 None 으로 남아 "필터 team_id 만" 조건이 성립한다.
        query = self._make_query(query_text="집 근처 추천 좀")
        results = retrieve_hospital(query)

        # retrieve 는 1회만 호출돼야 한다 (fallback 없음)
        assert mock_runtime.retrieve.call_count == 1
        assert results == []

    # (e) query_text 비어있으면 InvalidQueryError
    def test_empty_query_text_raises_error(self):
        """query_text 가 비어있으면 InvalidQueryError 를 발생시킨다."""
        from ai.core.exceptions import InvalidQueryError
        from shared.models import SearchQuery

        query = SearchQuery(query_text="   ", lat=37.4979, lng=127.0430)
        with pytest.raises(InvalidQueryError, match="비어있습니다"):
            retrieve_hospital(query)

    # (f) KB_ID 미설정 시 KBRetrieveError
    @patch("boto3.client")
    def test_missing_kb_id_raises_error(self, mock_boto3):
        """KB_ID 환경변수가 없으면 KBRetrieveError 를 발생시킨다."""
        from ai.core.exceptions import KBRetrieveError

        env_no_kb = {k: v for k, v in _RETRIEVE_ENV.items() if k != "KB_ID"}
        with patch.dict(os.environ, env_no_kb, clear=False):
            os.environ.pop("KB_ID", None)
            query = self._make_query()
            with pytest.raises(KBRetrieveError, match="KB_ID"):
                retrieve_hospital(query)

    # (g) limit 이 결과 수를 제한한다
    @patch("boto3.client")
    @patch.dict(os.environ, _RETRIEVE_ENV)
    def test_limit_caps_results(self, mock_boto3):
        """query.limit 이 결과 수를 제한한다."""
        mock_runtime = MagicMock()
        mock_runtime.retrieve.return_value = {
            "retrievalResults": [
                _make_kb_result(f"h_{i}", 1.0 - i * 0.05) for i in range(10)
            ]
        }
        mock_boto3.return_value = mock_runtime

        query = self._make_query(limit=3)
        results = retrieve_hospital(query)

        assert len(results) <= 3
