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
from unittest.mock import MagicMock, patch

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
    NonPayItem,
    PublicData,
    ReviewSignal,
    BlogSignal,
    SelfClaimSignal,
    SignalContributions,
)
from ai.search.kb_store import (
    _COSMETIC_FOCUS,
    _THIN_SIGNAL_FOCUS_KEYWORDS,
    _compute_nonpay_ratio,
    _cosmetic_ratio,
    _effective_cosmetic_ratio,
    _is_thin_signal_intent,
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


class TestNoDocSideSynonymInjection:
    """회귀 가드 — build_signal_chunks 는 동의어를 문서-측에 주입하지 않는다.

    옛 _enrich_with_synonyms 제거: 트리거 단어 1회만으로 동의어 클러스터 전체를 청크에
    박아 임베딩 변별력을 파괴했다(치과가 "M자 탈모" 0.708 1위). 동의어 갭은 쿼리-side
    확장(process_query)으로만 메운다."""

    def test_build_signal_chunks_no_doc_side_injection(self):
        """build_signal_chunks 는 doc-side 동의어 주입을 하지 않는다 — 청크=진짜 내용.

        회귀 가드: 트리거 단어 1회만 있어도 동의어 클러스터 전체를 청크에 박던 doc-side
        주입(_enrich_with_synonyms)을 제거했다. 그게 임베딩 변별력을 파괴해(19000자 치과
        사이트의 "탈모" 1회→"M자 탈모" 검색 0.708 1위) 진짜 전문병원이 밀렸다. 동의어 갭은
        쿼리-side 확장(process_query)으로만 메운다 — 문서는 원문 그대로 임베딩(2026-05-31)."""
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
        assert "심상성" in chunks["self_claim"]            # 진짜 내용은 유지
        assert "[관련 의학 용어]" not in chunks["self_claim"]  # 주입 블록 없음
        assert "사마귀" not in chunks["self_claim"]         # doc-side 주입 안 함


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
    def test_prune_absent_deletes_stale_signals(self, mock_boto3):
        """prune_absent=True 면, 이번 청크에 없는 시그널 타입의 옛 S3 파일을 삭제한다.

        URL 오매칭으로 self_claim 이 비워졌을 때 옛 self_claim 청크(stale 메타)가
        잔존해 검색을 오염시키는 버그(docs/issues/stale-kb-self-claim-metadata.md) 방지.
        """
        mock_s3 = MagicMock()
        mock_agent = MagicMock()
        mock_boto3.side_effect = lambda service, region_name=None: (
            mock_s3 if service == "s3" else mock_agent
        )
        # reviews 만 있고 self_claim/blog/vision 은 없음 → 그 셋의 옛 파일이 삭제돼야 함
        ingest_hospital(
            hospital_id="h_prune",
            signal_chunks={"reviews": "방문자 후기 키워드 요약"},
            metadata={"team_id": "clinic-focus", "hospital_id": "h_prune",
                      "standard_specialty": "기타", "sido": "서울",
                      "sigungu": "강남구", "confidence_score": 60},
            trigger_ingestion=False,
            prune_absent=True,
        )
        deleted = {c.kwargs["Key"] for c in mock_s3.delete_object.call_args_list}
        # 없는 시그널(self_claim/blog/vision)의 .txt + 사이드카가 삭제 대상
        assert "clinic-focus/prod/h_prune/self_claim.txt" in deleted
        assert "clinic-focus/prod/h_prune/self_claim.txt.metadata.json" in deleted
        assert "clinic-focus/prod/h_prune/blog.txt" in deleted
        assert "clinic-focus/prod/h_prune/vision.txt" in deleted
        # 존재하는 시그널(reviews)은 절대 삭제 안 됨
        assert not any("reviews.txt" in k for k in deleted), "있는 시그널이 삭제됨"

    @patch("boto3.client")
    @patch.dict(os.environ, _ENV)
    def test_prune_absent_false_no_delete(self, mock_boto3):
        """prune_absent 기본값(False)에서는 어떤 삭제도 일어나지 않는다(부분 ingest 안전)."""
        mock_s3, _ = self._run_ingest(mock_boto3)  # 기본 prune_absent=False
        mock_s3.delete_object.assert_not_called()

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
            # 추론 specialty 는 equals 가 아니라 in [추론, 기타] 형태로 들어간다
            # (기타=분류 못 한 특화 부티크를 하드 배제하지 않으려는 의도).
            if f.get("equals", {}).get("key") == "standard_specialty":
                return f["equals"]["value"] == value
            if f.get("in", {}).get("key") == "standard_specialty":
                return value in f["in"]["value"]
            return any(_specialty_in_filter(c, value) for c in f.get("andAll", []))

        assert _specialty_in_filter(kb_filter, "피부과"), f"추론 진료과 필터 없음: {kb_filter}"
        # 추론 specialty 에는 '기타'가 함께 허용돼야 한다(특화 부티크 배제 방지)
        assert _specialty_in_filter(kb_filter, "기타"), f"추론 필터에 '기타' 미포함: {kb_filter}"
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


# ===========================================================================
# 8. 심평원 공공데이터 — build_ingest_metadata(public_data) 테스트
# ===========================================================================

def _make_public_data(
    specialists_by_dept: dict[str, int] | None = None,
    total_doctors: int | None = None,
    nonpay_items: list | None = None,
) -> PublicData:
    return PublicData(
        license_number="TEST-001",
        specialists=[],
        registered_devices=[],
        specialists_by_dept=specialists_by_dept or {},
        total_doctors=total_doctors,
        nonpay_items=nonpay_items or [],
    )


class TestBuildIngestMetadataPublicData:
    """build_ingest_metadata(public_data=...) 심평원 신호 확장 테스트."""

    def test_no_public_data_returns_baseline(self):
        """public_data=None 이면 기존 필드만 반환 — has_specialist·nonpay_ratio·specialist_depts 없음."""
        meta = _make_meta()
        cls = _make_classification()
        md = build_ingest_metadata(meta, cls, public_data=None)
        assert "nonpay_ratio" not in md
        assert "has_specialist" not in md
        assert "specialist_depts" not in md

    def test_public_data_with_specialist_adds_fields(self):
        """전문의 있으면 has_specialist='true', specialist_depts 포함."""
        pd = _make_public_data(specialists_by_dept={"피부과": 1, "가정의학과": 0})
        meta = _make_meta()
        cls = _make_classification()
        md = build_ingest_metadata(meta, cls, public_data=pd)
        assert md["has_specialist"] == "true"
        # 전문의≥1 과목만 포함 (가정의학과 0 제외)
        assert "피부과" in md["specialist_depts"]
        assert "가정의학과" not in md["specialist_depts"]

    def test_public_data_no_specialist_has_specialist_false(self):
        """전문의 0명인 경우 has_specialist='false', specialist_depts 키 없음."""
        pd = _make_public_data(specialists_by_dept={"피부과": 0})
        meta = _make_meta()
        cls = _make_classification()
        md = build_ingest_metadata(meta, cls, public_data=pd)
        assert md["has_specialist"] == "false"
        assert "specialist_depts" not in md

    def test_public_data_empty_specialists_by_dept(self):
        """specialists_by_dept 빈 dict 이면 has_specialist='false', specialist_depts 없음."""
        pd = _make_public_data(specialists_by_dept={})
        meta = _make_meta()
        cls = _make_classification()
        md = build_ingest_metadata(meta, cls, public_data=pd)
        assert md["has_specialist"] == "false"
        assert "specialist_depts" not in md

    def test_nonpay_ratio_cosmetic_items(self):
        """미용성 비급여 항목이 2개 중 1개면 nonpay_ratio ≈ 0.5."""
        items = [
            NonPayItem(item_name="보톡스", category="미용"),
            NonPayItem(item_name="혈액검사", category="검사료"),
        ]
        pd = _make_public_data(nonpay_items=items)
        meta = _make_meta()
        cls = _make_classification()
        md = build_ingest_metadata(meta, cls, public_data=pd)
        assert md["nonpay_ratio"] == pytest.approx(0.5, abs=0.01)

    def test_nonpay_ratio_all_cosmetic(self):
        """모두 미용성이면 nonpay_ratio=1.0."""
        items = [
            NonPayItem(item_name="라식수술", category="시력교정"),
            NonPayItem(item_name="지방흡입", category="미용"),
        ]
        pd = _make_public_data(nonpay_items=items)
        meta = _make_meta()
        cls = _make_classification()
        md = build_ingest_metadata(meta, cls, public_data=pd)
        assert md["nonpay_ratio"] == pytest.approx(1.0)

    def test_nonpay_ratio_no_items_is_zero(self):
        """비급여 항목 없으면 nonpay_ratio=0.0."""
        pd = _make_public_data(nonpay_items=[])
        meta = _make_meta()
        cls = _make_classification()
        md = build_ingest_metadata(meta, cls, public_data=pd)
        assert md["nonpay_ratio"] == pytest.approx(0.0)

    def test_dochim_therapy_not_hard_excluded(self):
        """도수치료는 _NONPAY_COSMETIC_KEYWORDS 에 없어 미용성으로 분류되지 않는다."""
        items = [NonPayItem(item_name="도수치료", category="처치 및 수술료 등")]
        ratio = _compute_nonpay_ratio(_make_public_data(nonpay_items=items))
        assert ratio == pytest.approx(0.0), "도수치료는 미용성 hard 제외 대상 아님"

    def test_specialist_depts_pipe_separated(self):
        """specialist_depts 는 '|' 구분자 문자열로 평탄화된다 (list KB 거절 방어)."""
        pd = _make_public_data(specialists_by_dept={"피부과": 2, "내과": 1})
        meta = _make_meta()
        cls = _make_classification()
        md = build_ingest_metadata(meta, cls, public_data=pd)
        assert isinstance(md["specialist_depts"], str)
        depts = md["specialist_depts"].split("|")
        assert "피부과" in depts
        assert "내과" in depts


# ===========================================================================
# 9. _effective_cosmetic_ratio 의도 정렬 — nonpay_ratio 있을 때/없을 때 fallback 테스트
# ===========================================================================

class TestEffectiveCosmeticRatio:
    """_effective_cosmetic_ratio: 심평원 nonpay_ratio 우선, 없으면 하드코딩 fallback."""

    def _make_group(self, pf: list[str], nonpay_ratio: float | None = None) -> dict:
        md = {"hospital_id": "h_test"}
        if nonpay_ratio is not None:
            md["nonpay_ratio"] = nonpay_ratio
        return {
            "best": {"metadata": md, "content": {"text": ""}},
            "pf": pf,
            "max_score": 0.8,
            "confidence": 0.7,
        }

    def test_uses_nonpay_ratio_when_present(self):
        """metadata 에 nonpay_ratio 가 있으면 그 값을 사용한다."""
        g = self._make_group(["보톡스·필러"], nonpay_ratio=0.6)
        ratio = _effective_cosmetic_ratio(g)
        assert ratio == pytest.approx(0.6)

    def test_falls_back_to_cosmetic_ratio_when_absent(self):
        """nonpay_ratio 가 없으면 _cosmetic_ratio(하드코딩)로 fallback."""
        g = self._make_group(["보톡스·필러", "리프팅·탄력"])  # 2/2 = 1.0
        ratio = _effective_cosmetic_ratio(g)
        # _cosmetic_ratio: pf 2개 모두 _COSMETIC_FOCUS → 1.0
        assert ratio == pytest.approx(1.0)

    def test_falls_back_for_non_cosmetic_pf(self):
        """nonpay_ratio 없고 일반 pf → fallback ratio 0.0."""
        g = self._make_group(["척추 디스크", "어깨 관절"])
        ratio = _effective_cosmetic_ratio(g)
        assert ratio == pytest.approx(0.0)

    def test_invalid_nonpay_ratio_falls_back(self):
        """nonpay_ratio 가 유효 범위 밖이거나 파싱 불가면 fallback."""
        g = self._make_group(["척추 디스크"], nonpay_ratio=None)
        # None → fallback
        g["best"]["metadata"]["nonpay_ratio"] = "invalid_string"
        ratio = _effective_cosmetic_ratio(g)
        # "척추 디스크"는 _COSMETIC_FOCUS 미포함 → fallback 0.0
        assert ratio == pytest.approx(0.0)

    def test_hard_exclude_uses_cosmetic_ratio_not_nonpay(self):
        """hard 제외 판정(_cosmetic_ratio)과 soft 강등(_effective_cosmetic_ratio)이 독립적.

        nonpay_ratio 0.9 여도 primary_focus 가 비미용이면 hard 제외(cosmetic_ratio<1.0)를 통과.
        """
        g = self._make_group(["척추 디스크"], nonpay_ratio=0.9)
        # hard 제외: _cosmetic_ratio < 1.0 → 통과(제외 안 됨)
        assert _cosmetic_ratio(g) < 1.0
        # soft 강등: _effective_cosmetic_ratio 는 nonpay_ratio 0.9 사용
        assert _effective_cosmetic_ratio(g) == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# thin-signal 동적 임계 완화 — _is_thin_signal_intent
# ---------------------------------------------------------------------------

class TestIsThinSignalIntent:
    """_is_thin_signal_intent 단위 테스트.

    thin-signal 의도(호흡기·감염·예방·소아·비뇨 특화)면 True,
    미용·성형·임플란트 같은 고-임베딩 토픽이면 False 를 반환해야 한다.
    """

    def test_infection_focus_is_thin(self):
        """감염 focus → thin-signal."""
        assert _is_thin_signal_intent(["감염내과", "호흡기 감염"]) is True

    def test_respiratory_focus_is_thin(self):
        """호흡기 focus → thin-signal."""
        assert _is_thin_signal_intent(["호흡기", "급성 일차진료"]) is True

    def test_prevention_focus_is_thin(self):
        """예방접종 focus → thin-signal."""
        assert _is_thin_signal_intent(["건강검진·예방", "예방접종"]) is True

    def test_urological_focus_is_thin(self):
        """요로 focus → thin-signal."""
        assert _is_thin_signal_intent(["요로결석", "신장내과"]) is True

    def test_hand_surgery_focus_is_thin(self):
        """수부 focus → thin-signal."""
        assert _is_thin_signal_intent(["수부·재건"]) is True

    def test_foot_surgery_focus_is_thin(self):
        """족부 focus → thin-signal."""
        assert _is_thin_signal_intent(["족부"]) is True

    def test_cosmetic_focus_is_not_thin(self):
        """미용 focus → thin-signal 아님."""
        assert _is_thin_signal_intent(["미용 시술", "미용주사"]) is False

    def test_dental_focus_is_not_thin(self):
        """치과 임플란트 focus → thin-signal 아님."""
        assert _is_thin_signal_intent(["임플란트"]) is False

    def test_orthopedic_spine_not_thin(self):
        """척추 focus → thin-signal 아님 (고-임베딩 토픽)."""
        assert _is_thin_signal_intent(["척추", "척추·통증"]) is False

    def test_empty_focus_returns_false(self):
        """빈 focus → False."""
        assert _is_thin_signal_intent([]) is False
        assert _is_thin_signal_intent(None) is False

    def test_disabled_by_env(self, monkeypatch):
        """THIN_SIGNAL_BOOST=off 면 항상 False."""
        monkeypatch.setenv("THIN_SIGNAL_BOOST", "off")
        assert _is_thin_signal_intent(["감염내과", "호흡기 감염"]) is False

    def test_enabled_by_default(self, monkeypatch):
        """THIN_SIGNAL_BOOST 미설정(기본 on) → thin-signal 의도 감지."""
        monkeypatch.delenv("THIN_SIGNAL_BOOST", raising=False)
        assert _is_thin_signal_intent(["호흡기"]) is True

    def test_thin_signal_focus_keywords_not_empty(self):
        """_THIN_SIGNAL_FOCUS_KEYWORDS 는 비어있지 않아야 한다."""
        assert len(_THIN_SIGNAL_FOCUS_KEYWORDS) > 0


class TestRetrieveHospitalThinSignalMinScore:
    """retrieve_hospital 의 thin-signal 동적 임계 완화 로직을 mock 으로 검증.

    실제 KB Retrieve 는 mock 처리하고, min_score 가 thin-signal 의도일 때
    THIN_SIGNAL_MIN_SCORE(기본 0.37)로 낮아지는지 확인한다.
    Bedrock 실 호출 비용 발생 0건.
    """

    def _make_retrieve_resp(self, scores: list[float]) -> dict:
        """KB Retrieve 응답 mock — 각 score 에 대한 결과를 반환."""
        results = []
        for i, s in enumerate(scores):
            results.append({
                "score": s,
                "metadata": {
                    "hospital_id": f"h_{i:03d}",
                    "name": f"병원{i}",
                    "team_id": "clinic-focus",
                    "primary_focus": ["호흡기"],
                    "standard_specialty": "내과",
                    "sigungu": "강남구",
                    "confidence_score": 70,
                },
                "content": {"text": "호흡기 내과 진료"},
            })
        return {"retrievalResults": results}

    @patch("boto3.client")
    def test_thin_signal_lowers_min_score(self, mock_boto, monkeypatch):
        """thin-signal 의도(호흡기) → min_score 0.42 → 0.37 로 완화, 코사인 0.39 결과가 살아남아야 함."""
        monkeypatch.delenv("KB_MIN_SCORE", raising=False)
        monkeypatch.delenv("THIN_SIGNAL_BOOST", raising=False)
        monkeypatch.setenv("KB_ID", "test-kb-id")
        monkeypatch.setenv("RERANK_MODE", "off")

        from shared.models import SearchQuery

        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        # 코사인 0.39 결과 1개 — 기본 min_score(0.42)면 컷되고, 0.37이면 살아남아야 함
        mock_client.retrieve.return_value = self._make_retrieve_resp([0.39])

        results = retrieve_hospital(SearchQuery(query_text="호흡기 내과", sigungu="강남구", limit=5))
        # thin-signal 완화 덕분에 결과가 있어야 함
        assert len(results) >= 1

    @patch("boto3.client")
    def test_normal_query_uses_default_min_score(self, mock_boto, monkeypatch):
        """미용 쿼리(보톡스) → thin-signal 아님 → min_score 기본(0.42) 유지, 코사인 0.39 결과 컷."""
        monkeypatch.delenv("KB_MIN_SCORE", raising=False)
        monkeypatch.delenv("THIN_SIGNAL_BOOST", raising=False)
        monkeypatch.setenv("KB_ID", "test-kb-id")
        monkeypatch.setenv("RERANK_MODE", "off")

        from shared.models import SearchQuery

        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        # 코사인 0.39 결과 — 기본 min_score(0.42)면 컷되어야 함
        mock_client.retrieve.return_value = self._make_retrieve_resp([0.39])

        results = retrieve_hospital(SearchQuery(query_text="보톡스 필러", sigungu="강남구", limit=5))
        # thin-signal 아님 → 기본 컷(0.42) 유지 → 0.39 결과 제거 → 빈 결과
        assert len(results) == 0

    @patch("boto3.client")
    def test_env_min_score_overrides_thin_signal(self, mock_boto, monkeypatch):
        """KB_MIN_SCORE env 가 명시되면 thin-signal 완화를 하지 않는다."""
        monkeypatch.setenv("KB_MIN_SCORE", "0.42")
        monkeypatch.delenv("THIN_SIGNAL_BOOST", raising=False)
        monkeypatch.setenv("KB_ID", "test-kb-id")
        monkeypatch.setenv("RERANK_MODE", "off")

        from shared.models import SearchQuery

        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        # 코사인 0.39 결과 — KB_MIN_SCORE=0.42 명시이므로 컷돼야 함(thin-signal 완화 안 됨)
        mock_client.retrieve.return_value = self._make_retrieve_resp([0.39])

        results = retrieve_hospital(SearchQuery(query_text="호흡기 내과", sigungu="강남구", limit=5))
        assert len(results) == 0

    @patch("boto3.client")
    def test_thin_signal_boost_off_disables_relaxation(self, mock_boto, monkeypatch):
        """THIN_SIGNAL_BOOST=off 면 thin-signal 의도여도 min_score 완화 안 함."""
        monkeypatch.delenv("KB_MIN_SCORE", raising=False)
        monkeypatch.setenv("THIN_SIGNAL_BOOST", "off")
        monkeypatch.setenv("KB_ID", "test-kb-id")
        monkeypatch.setenv("RERANK_MODE", "off")

        from shared.models import SearchQuery

        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.retrieve.return_value = self._make_retrieve_resp([0.39])

        results = retrieve_hospital(SearchQuery(query_text="호흡기 내과", sigungu="강남구", limit=5))
        # THIN_SIGNAL_BOOST=off → 완화 없음 → 0.39 컷
        assert len(results) == 0

    @patch("boto3.client")
    def test_unrelated_query_still_returns_empty(self, mock_boto, monkeypatch):
        """무관 쿼리(자동차 수리) → thin-signal 아님, 낮은 점수 결과 컷 유지."""
        monkeypatch.delenv("KB_MIN_SCORE", raising=False)
        monkeypatch.delenv("THIN_SIGNAL_BOOST", raising=False)
        monkeypatch.setenv("KB_ID", "test-kb-id")
        monkeypatch.setenv("RERANK_MODE", "off")

        from shared.models import SearchQuery

        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        mock_client.retrieve.return_value = self._make_retrieve_resp([0.35, 0.38, 0.41])

        results = retrieve_hospital(SearchQuery(query_text="자동차 수리", limit=5))
        # 무관 쿼리 → thin-signal 아님 → 기본 컷(0.42) → 모두 컷 → 빈 결과
        assert len(results) == 0
