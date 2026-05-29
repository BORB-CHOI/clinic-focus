"""
ai/ 패키지 — BE가 import하는 공개 인터페이스.

사용 예:
    from ai import generate_description, embed_text, ingest_hospital, retrieve_hospital
    from shared.models import Classification, DetailedSignals, HospitalMeta, SearchQuery

주의: 하위 모듈(pipeline/, search/ 등)이 boto3 에 의존하므로
module-level 에서 직접 import 하지 않고 lazy import 방식으로 노출한다.
이렇게 하면 boto3 미설치 환경(단위 테스트, 린터 등)에서도 패키지 import 가 가능하다.

폐기된 함수 (사용 금지):
  - index_hospital  → ingest_hospital 으로 대체 (KB 경유, S3 Vectors 직접 호출 ❌)
  - search_similar  → retrieve_hospital 으로 대체 (KB Retrieve API 경유)
"""

from __future__ import annotations

import importlib as _importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # 타입 체커용 — 런타임에는 실행되지 않음
    from ai.pipeline.classify import classify_hospital  # noqa: F401
    from ai.pipeline.describe import generate_description  # noqa: F401
    from ai.pipeline.extract import extract_services_and_doctors  # noqa: F401
    from ai.pipeline.vision import analyze_images  # noqa: F401
    from ai.search.embed import embed_text  # noqa: F401
    from ai.search.feedback import aggregate_feedback_stats, recompute_confidence  # noqa: F401
    from ai.search.kb_store import ingest_hospital, retrieve_hospital  # noqa: F401
    from ai.search.query_processor import ProcessedQuery, process_query  # noqa: F401
    from ai.search.related import find_related_hospitals  # noqa: F401


def __getattr__(name: str):  # noqa: ANN001, ANN202
    """lazy import: 실제 함수가 필요한 시점에만 boto3 의존 모듈을 로드한다."""
    _module_map = {
        "classify_hospital":            ("ai.pipeline.classify",   "classify_hospital"),
        "generate_description":         ("ai.pipeline.describe",   "generate_description"),
        "extract_services_and_doctors": ("ai.pipeline.extract",    "extract_services_and_doctors"),
        "analyze_images":               ("ai.pipeline.vision",     "analyze_images"),
        "embed_text":                   ("ai.search.embed",        "embed_text"),
        "ingest_hospital":              ("ai.search.kb_store",     "ingest_hospital"),
        "retrieve_hospital":            ("ai.search.kb_store",     "retrieve_hospital"),
        "find_related_hospitals":       ("ai.search.related",      "find_related_hospitals"),
        "recompute_confidence":         ("ai.search.feedback",     "recompute_confidence"),
        "aggregate_feedback_stats":     ("ai.search.feedback",     "aggregate_feedback_stats"),
        # 검색어 전처리(불용어·동의어·진료과 추론). boto3 의존 없으나 export 패턴 통일.
        "process_query":                ("ai.search.query_processor", "process_query"),
        "ProcessedQuery":               ("ai.search.query_processor", "ProcessedQuery"),
    }
    if name in _module_map:
        module_path, attr = _module_map[name]
        mod = _importlib.import_module(module_path)
        return getattr(mod, attr)
    raise AttributeError(f"module 'ai' has no attribute {name!r}")


__all__ = [
    "classify_hospital",
    "generate_description",
    "embed_text",
    "ingest_hospital",
    "retrieve_hospital",
    "analyze_images",
    "extract_services_and_doctors",
    "find_related_hospitals",
    "recompute_confidence",
    "aggregate_feedback_stats",
    "process_query",
    "ProcessedQuery",
]
