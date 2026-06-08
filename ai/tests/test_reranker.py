"""reranker 단위 테스트 — 2-stage RAG 2단계 LLM 재랭킹.

검증 포인트:
- mock 점수로 윈도 재정렬 (실 Bedrock 호출 0)
- graceful fallback: Bedrock 오류·JSON 깨짐·점수 누락 시 1차 순서 유지
- 윈도 ≤ 1 이면 LLM 미호출
- RERANK_TOP_N 윈도 밖 꼬리는 원순서 보존
- (query, 후보집합) 캐시 → 2회차 LLM 미호출
- 모델은 Haiku 명시 전달, 발췌(청크 본문)는 채점 입력으로만 사용
- 반환은 입력 dict 의 순서만 바꾼 것(객체 동일성) — SearchResult 스키마 불변

Bedrock 은 반드시 mock (``@patch("ai.core.bedrock_client.invoke_model")``).
실 호출 비용이 발생하면 안 된다 (ai/CLAUDE.md).
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from ai.search import reranker
from ai.search.reranker import rerank_candidates


def _group(hid: str, name: str, focus: list[str], text: str, score: float = 0.5) -> dict:
    """_aggregate_by_hospital group dict 의 최소 형태."""
    return {
        "best": {
            "metadata": {"hospital_id": hid, "name": name},
            "content": {"text": text},
        },
        "pf": focus,
        "max_score": score,
        "confidence": 0.8,
    }


def _bedrock_reply(scores: list[tuple[int, float]]) -> dict:
    """Anthropic Messages 형식 응답 mock — scores JSON 을 text 블록에 담는다."""
    payload = {"scores": [{"i": i, "s": s} for i, s in scores]}
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


@pytest.fixture(autouse=True)
def _clear_cache():
    reranker._cache.clear()
    yield
    reranker._cache.clear()


@pytest.fixture(autouse=True)
def _haiku_env(monkeypatch):
    # 기본 모델을 Haiku 로 (describe.py default Sonnet 회피 검증).
    monkeypatch.delenv("BEDROCK_LLM_MODEL_ID", raising=False)
    monkeypatch.delenv("RERANK_TOP_N", raising=False)


# ── 재정렬 ────────────────────────────────────────────────────────────────

@patch("ai.core.bedrock_client.invoke_model")
def test_reorders_by_llm_score(mock_invoke):
    groups = [
        _group("h0", "노이즈클리닉", ["비만·다이어트"], "비만 호흡기 한 줄 언급"),
        _group("h1", "모엠모발의원", ["모발·탈모"], "M자 탈모 모발이식 주력 반복"),
    ]
    # 입력 0,1 → LLM 은 1 을 더 높은 매칭도로 채점 → 1,0 으로 뒤집힌다.
    mock_invoke.return_value = _bedrock_reply([(0, 0.1), (1, 0.95)])

    out = rerank_candidates("탈모", groups)

    assert [g["best"]["metadata"]["hospital_id"] for g in out] == ["h1", "h0"]
    mock_invoke.assert_called_once()


@patch("ai.core.bedrock_client.invoke_model")
def test_tie_preserves_first_stage_order(mock_invoke):
    groups = [_group("h0", "A", ["x"], "t"), _group("h1", "B", ["x"], "t")]
    mock_invoke.return_value = _bedrock_reply([(0, 0.7), (1, 0.7)])  # 동점
    out = rerank_candidates("q", groups)
    assert [g["best"]["metadata"]["hospital_id"] for g in out] == ["h0", "h1"]


@patch("ai.core.bedrock_client.invoke_model")
def test_returns_same_objects_only_reordered(mock_invoke):
    groups = [_group("h0", "A", ["x"], "t"), _group("h1", "B", ["y"], "t")]
    mock_invoke.return_value = _bedrock_reply([(0, 0.2), (1, 0.9)])
    out = rerank_candidates("q", groups)
    # 새 dict 생성 없이 입력 객체를 그대로 재배치(스키마 불변).
    assert out[0] is groups[1]
    assert out[1] is groups[0]


# ── graceful fallback ────────────────────────────────────────────────────

@patch("ai.core.bedrock_client.invoke_model")
def test_fallback_on_bedrock_error(mock_invoke):
    mock_invoke.side_effect = RuntimeError("Bedrock down")
    groups = [_group("h0", "A", ["x"], "t"), _group("h1", "B", ["y"], "t")]
    out = rerank_candidates("q", groups)
    assert out == groups  # 1차 순서 유지


@patch("ai.core.bedrock_client.invoke_model")
def test_fallback_on_malformed_json(mock_invoke):
    mock_invoke.return_value = {"content": [{"type": "text", "text": "이건 JSON 이 아님"}]}
    groups = [_group("h0", "A", ["x"], "t"), _group("h1", "B", ["y"], "t")]
    out = rerank_candidates("q", groups)
    assert [g["best"]["metadata"]["hospital_id"] for g in out] == ["h0", "h1"]


@patch("ai.core.bedrock_client.invoke_model")
def test_fallback_on_missing_scores(mock_invoke):
    # 후보 2개인데 점수 1개만 → 형식 위반 → fallback.
    mock_invoke.return_value = _bedrock_reply([(0, 0.9)])
    groups = [_group("h0", "A", ["x"], "t"), _group("h1", "B", ["y"], "t")]
    out = rerank_candidates("q", groups)
    assert [g["best"]["metadata"]["hospital_id"] for g in out] == ["h0", "h1"]


# ── 가드·꼬리·캐시 ────────────────────────────────────────────────────────

@patch("ai.core.bedrock_client.invoke_model")
def test_single_candidate_skips_llm(mock_invoke):
    groups = [_group("h0", "A", ["x"], "t")]
    out = rerank_candidates("q", groups)
    assert out == groups
    mock_invoke.assert_not_called()


@patch("ai.core.bedrock_client.invoke_model")
def test_tail_outside_window_preserved(mock_invoke, monkeypatch):
    monkeypatch.setenv("RERANK_TOP_N", "2")
    groups = [
        _group("h0", "A", ["x"], "t"),
        _group("h1", "B", ["x"], "t"),
        _group("h2", "C", ["x"], "t"),  # 윈도 밖(꼬리)
        _group("h3", "D", ["x"], "t"),  # 윈도 밖(꼬리)
    ]
    mock_invoke.return_value = _bedrock_reply([(0, 0.1), (1, 0.9)])  # 윈도 0,1 뒤집힘
    out = rerank_candidates("q", groups)
    ids = [g["best"]["metadata"]["hospital_id"] for g in out]
    assert ids == ["h1", "h0", "h2", "h3"]  # 꼬리 h2,h3 원순서 유지(윈도=TOP_N=2, limit 무관)


@patch("ai.core.bedrock_client.invoke_model")
def test_cache_avoids_second_call(mock_invoke):
    groups = [_group("h0", "A", ["x"], "t"), _group("h1", "B", ["y"], "t")]
    mock_invoke.return_value = _bedrock_reply([(0, 0.1), (1, 0.9)])
    out1 = rerank_candidates("탈모", groups)
    out2 = rerank_candidates("탈모", groups)
    assert out1[0]["best"]["metadata"]["hospital_id"] == "h1"
    assert out2[0]["best"]["metadata"]["hospital_id"] == "h1"
    mock_invoke.assert_called_once()  # 2회차는 캐시


# ── 모델·입력 ─────────────────────────────────────────────────────────────

@patch("ai.core.bedrock_client.invoke_model")
def test_uses_haiku_and_feeds_excerpt(mock_invoke):
    groups = [
        _group("h0", "A클리닉", ["x"], "여기 발췌 본문 알파"),
        _group("h1", "B의원", ["y"], "여기 발췌 본문 베타"),
    ]
    mock_invoke.return_value = _bedrock_reply([(0, 0.5), (1, 0.5)])
    rerank_candidates("질의어", groups)

    _, kwargs = mock_invoke.call_args
    assert "haiku" in kwargs["model_id"].lower()  # Sonnet default 회피
    prompt = kwargs["prompt"]
    assert "질의어" in prompt          # 사용자 질의 주입
    assert "발췌 본문 알파" in prompt   # 청크 본문이 채점 입력으로 사용됨
    assert "A클리닉" in prompt
