"""LLM 질의어 보강 프로토타입 — '무좀' 재작성이 retrieval 을 실제로 개선하나 측정. 콘솔 전용."""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

import boto3  # noqa: E402

from ai.search.query_processor import process_query  # noqa: E402
from ai.search import kb_store  # noqa: E402

EXPAND_PROMPT = (
    "사용자가 병원 검색창에 \"{q}\"라고 입력했다. 이를 한국어 병원 사이트·후기 코퍼스에서 "
    "의미 임베딩으로 잘 매칭되도록, 환자가 실제로 찾는 진료·증상·질환을 풀어쓴 자연어 검색 "
    "문장 하나로 재작성하라. 효능·광고어(최고·전문·완치) 금지, 진료 사실 용어만. "
    "설명 없이 재작성된 검색 문장 한 줄만 출력."
)


def expand_converse(q: str, model_id: str, region: str, profile: str | None) -> str:
    sess = boto3.Session(profile_name=profile) if profile else boto3.Session()
    client = sess.client("bedrock-runtime", region_name=region)
    resp = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": EXPAND_PROMPT.format(q=q)}]}],
        inferenceConfig={"maxTokens": 200, "temperature": 0.2},
    )
    return resp["output"]["message"]["content"][0]["text"].strip()


def try_expand(q: str) -> tuple[str, str]:
    """지원계정 Nova(us-east-1, 기본 자격) 우선, 실패 시 개인계정 Haiku."""
    attempts = [
        ("Nova Lite(지원/us-east-1)", "amazon.nova-lite-v1:0", "us-east-1", None),
        ("Nova Micro(지원/us-east-1)", "amazon.nova-micro-v1:0", "us-east-1", None),
        ("Haiku4.5(개인/서울)", os.environ.get("BEDROCK_LLM_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0"),
         os.environ.get("AI_AWS_REGION", "ap-northeast-2"), None),
    ]
    for label, mid, region, prof in attempts:
        try:
            # Haiku는 AI 세션(개인 자격) — 환경변수 자격이 기본 체인에 있으면 그대로 사용
            txt = expand_converse(q, mid, region, prof)
            return label, txt
        except Exception as e:
            print(f"   [{label}] 실패: {str(e)[:120]}")
    return "ALL_FAILED", q


def retrieve_top(text: str, inferred_sp: str | None, terms: list[str], n=6):
    client = boto3.client("bedrock-agent-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    kb_filter = kb_store._build_kb_filter(specialty=[inferred_sp, "기타"] if inferred_sp else None)
    raw = kb_store._kb_retrieve(client, os.environ["KB_ID"], text, kb_filter, 100)
    min_score = float(os.environ.get("KB_MIN_SCORE", "0.42"))
    groups = kb_store._aggregate_by_hospital(raw, terms)
    kept = [g for g in groups.values() if g["max_score"] >= min_score]
    kept.sort(key=lambda g: (-kb_store._focus_intensity(g), -g["max_score"]))
    out = []
    for g in kept[:n]:
        md = g["best"].get("metadata") or {}
        out.append(f"{md.get('name','?')}({md.get('standard_specialty','?')}) cos={g['max_score']:.3f}")
    return out


def main(q="무좀"):
    p = process_query(q)
    print(f"원쿼리: {q!r}")
    print(f"  사전확장(현재): {p.embedding_text!r}")
    print("  현재 top6:")
    for r in retrieve_top(p.embedding_text, p.inferred_specialty, p.medical_terms):
        print("    -", r)

    print("\nLLM 재작성 시도...")
    label, expanded = try_expand(q)
    print(f"  [{label}] 재작성: {expanded!r}")
    if label != "ALL_FAILED":
        # 재작성문에 사전확장도 한 번 더 입힘(하이브리드) + 단독 둘 다 비교
        pe = process_query(expanded)
        print("  LLM재작성 단독 top6:")
        for r in retrieve_top(expanded, pe.inferred_specialty or p.inferred_specialty, p.medical_terms):
            print("    -", r)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "무좀")
