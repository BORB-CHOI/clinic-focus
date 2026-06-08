"""LLM 재랭커 — 2-stage RAG 의 2단계.

1차(임베딩 + 주력강도 `_focus_intensity`)로 회수·정렬된 후보를, 검색 *런타임* 시점에
LLM(개인 계정 Haiku)으로 한 번 더 정렬한다. 1차는 "이 병원이 이 토픽을 얼마나
주장하나"를 빈도 휴리스틱으로만 보지만, 회수된 상위가 노이즈(여러 분야를 한 줄씩
언급한 병원)로 1위를 차지하는 케이스를 휴리스틱은 못 거른다(NDCG baseline 분해상
P@1 여지 +0.202). 질의 주제와의 매칭도로 상위 순서를 보정하는 게 목적이다.

설계 원칙:
- **opt-in.** `RERANK_MODE=off`(기본)면 이 모듈은 호출되지 않는다(`kb_store` 가 가드).
  검색 런타임 LLM 0건 기본값을 유지하고, A/B·비용off 를 양립시킨다.
- **AI 모듈 안에서 끝낸다.** BE 는 relevance 정렬을 보존만 하므로(주력강도 정렬을
  코사인으로 덮어쓰는 회귀 방지), 재랭킹은 반드시 여기서 마친다.
- **graceful fallback.** Bedrock 오류·파싱 실패·점수 누락 시 입력 순서를 그대로
  반환한다(절대 raise 안 함). 검색이 리랭커 때문에 죽으면 안 된다.
- **의료법 §56③.** 발췌(청크 본문)는 LLM *채점 입력*으로만 쓰고 출력엔 싣지 않는다.
  반환값은 입력 group dict 리스트의 *순서만 바꾼 것* — SearchResult 스키마 불변.
- **개인 계정 쿼터 의식.** 검색당 LLM 1회라 (query, 후보집합) 결과를 캐시해 반복
  쿼리를 방어한다. 모델은 Haiku 를 명시 전달(describe.py 의 default 는 Sonnet 이므로
  default 에 기대지 않는다).
"""

from __future__ import annotations

import json
import logging
import os
import threading

from ai.core import bedrock_client

logger = logging.getLogger(__name__)

# 재랭킹할 상위 후보 수. 최종 출력은 query.limit 로 캡되므로 limit 보다 넉넉히 본다.
_DEFAULT_TOP_N = 20
# 후보당 발췌 길이(채점 입력용). 길수록 비용·지연↑, 너무 짧으면 판단 근거 부족.
_EXCERPT_CHARS = 500
# describe.py default 는 Sonnet 4.6 이므로 reranker 는 Haiku 를 명시한다(쿼터·비용).
_DEFAULT_HAIKU = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "rerank_relevance.md")

# (query, model, 후보 hid 튜플) → 재정렬된 인덱스 순열. 모듈 수명 동안 유지(데모 반복쿼리 방어).
# eval 은 ThreadPoolExecutor(8 worker)로 retrieve_hospital 을 병렬 호출하므로, check-then-set
# 경쟁으로 같은 쿼리에 중복 Haiku 호출(=개인계정 쿼터 낭비)이 나지 않게 Lock 으로 보호.
_cache: dict[tuple, list[int]] = {}
_cache_lock = threading.Lock()


def _load_template() -> str:
    with open(_PROMPT_PATH, encoding="utf-8") as f:
        return f.read()


def _candidate_view(g: dict, idx: int) -> dict:
    """group dict 에서 채점에 필요한 최소 정보만 뽑는다(kb_store 비의존)."""
    best = g.get("best") or {}
    md = best.get("metadata") or {}
    content = best.get("content")
    text = content.get("text", "") if isinstance(content, dict) else str(content or "")
    focus = g.get("pf") or []
    return {
        "i": idx,
        "hid": md.get("hospital_id") or "",
        "name": md.get("name") or "",
        "focus": ", ".join(str(f) for f in focus) if focus else "—",
        "excerpt": " ".join(text.split())[:_EXCERPT_CHARS],
    }


def _render_candidates(views: list[dict]) -> str:
    return "\n".join(
        f"[{v['i']}] {v['name'] or '(이름미상)'} | 자칭 주력: {v['focus']} | 발췌: {v['excerpt']}"
        for v in views
    )


def _parse_scores(raw_response: dict) -> dict[int, float]:
    """Bedrock 응답에서 {index: score} 를 추출. 실패 시 빈 dict."""
    content = raw_response.get("content")
    if isinstance(content, list):
        text = "\n".join(b.get("text", "") for b in content if b.get("type") == "text").strip()
    else:
        text = str(content or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()
    data = json.loads(text)  # 실패 시 호출부가 잡아 fallback
    scores: dict[int, float] = {}
    for item in data.get("scores", []):
        scores[int(item["i"])] = float(item["s"])
    return scores


def rerank_candidates(query_text: str, groups: list[dict]) -> list[dict]:
    """상위 RERANK_TOP_N 후보를 LLM 매칭도 점수로 재정렬한다. 실패 시 입력 그대로 반환.

    윈도는 **비용 상한**을 위해 `RERANK_TOP_N`(기본 20)으로 고정한다 — 최종 `limit`
    슬라이싱은 호출자(`retrieve_hospital`)가 재랭킹 *뒤에* 수행하므로, 회수가 limit 보다
    많아도 상위 윈도만 LLM 채점한다(limit 이 커도 호출 토큰이 폭증하지 않음). 윈도 밖
    꼬리는 1차 순서를 유지한 채 뒤에 붙인다.

    반환은 입력 group dict 리스트의 *순서만 바꾼 것* — 같은 dict 객체를 재배치하므로
    위치 검색의 `g['dist']` 등 추가 속성도 그대로 보존되고 `SearchResult` 스키마는 불변.

    Args:
        query_text: 사용자 원본 질의(동의어 확장본 아님 — LLM 은 사람 질의를 본다).
        groups: `_aggregate_by_hospital` group dict 리스트(이미 1차 정렬됨).

    Returns:
        재정렬된 group dict 리스트(윈도만 재정렬, 꼬리는 원순서). 길이·객체 동일성 보존.
    """
    top_n = int(os.environ.get("RERANK_TOP_N", str(_DEFAULT_TOP_N)))
    window = groups[:top_n]
    tail = groups[top_n:]
    if len(window) <= 1:
        return groups

    views = [_candidate_view(g, i) for i, g in enumerate(window)]
    model_id = os.environ.get("BEDROCK_LLM_MODEL_ID") or _DEFAULT_HAIKU
    # 모델·질의·후보집합이 같으면 순서가 같다 → 캐시 키에 model_id 포함(모델 바뀌면 무효화).
    cache_key = (query_text, model_id, tuple(v["hid"] for v in views))

    with _cache_lock:
        cached = _cache.get(cache_key)
    if cached is not None and len(cached) == len(window):
        return [window[i] for i in cached] + tail

    try:
        prompt = _load_template().replace("{query}", query_text).replace(
            "{candidates}", _render_candidates(views)
        )
        # 모듈 속성으로 호출 → @patch("ai.core.bedrock_client.invoke_model") 로 mock 가능.
        raw = bedrock_client.invoke_model(prompt=prompt, model_id=model_id)
        scores = _parse_scores(raw)
    except Exception as e:  # Bedrock 오류·JSON 파싱 실패 등 — 검색은 죽지 않는다
        logger.warning("rerank_candidates: LLM 재랭킹 실패, 1차 순서 유지 (query=%r): %s", query_text, e)
        return groups

    # 모든 윈도 후보에 점수가 있어야 신뢰(부분 누락 = 모델 형식 위반 → fallback).
    if any(i not in scores for i in range(len(window))):
        logger.warning("rerank_candidates: 점수 누락(%d/%d), 1차 순서 유지 (query=%r)",
                       len(scores), len(window), query_text)
        return groups

    # 점수 내림차순, 동점은 1차 순서 보존(안정 정렬).
    order = sorted(range(len(window)), key=lambda i: (-scores[i], i))
    with _cache_lock:
        _cache[cache_key] = order
    return [window[i] for i in order] + tail
