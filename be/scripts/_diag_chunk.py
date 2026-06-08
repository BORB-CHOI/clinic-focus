"""무좀 1위 병원의 청크 내용 + 분류 primary_focus 분포 진단. 일회성, 콘솔 전용."""
from __future__ import annotations

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


def dump_chunks(query_text: str, target_names: list[str]):
    p = process_query(query_text)
    kb_id = os.environ["KB_ID"]
    region = os.environ.get("AWS_REGION", "us-east-1")
    client = boto3.client("bedrock-agent-runtime", region_name=region)
    kb_filter = kb_store._build_kb_filter(specialty=["피부과", "기타"])
    raw = kb_store._kb_retrieve(client, kb_id, p.embedding_text, kb_filter, 100)

    for r in raw:
        md = r.get("metadata") or {}
        name = md.get("name", "")
        if name not in target_names:
            continue
        loc = r.get("location") or {}
        uri = (loc.get("s3Location") or {}).get("uri", "")
        sig = uri.rsplit("/", 1)[-1] if uri else "?"
        content = r.get("content") or {}
        text = content.get("text", "") if isinstance(content, dict) else str(content)
        cnt = text.count("무좀")
        print(f"\n### {name}  [{sig}]  score={r.get('score'):.4f}  무좀×{cnt}  len={len(text)}")
        # 무좀 주변 ±40자 윈도우 (도배 여부 확인용)
        i = 0
        wins = 0
        while wins < 6:
            j = text.find("무좀", i)
            if j < 0:
                break
            print("   …" + text[max(0, j - 35):j + 37].replace("\n", " ") + "…")
            i = j + 2
            wins += 1


def scan_focus():
    """분류된 강남 병원 중 primary_focus 에 진균/무좀/백선/곰팡이 가 들어간 병원 카운트."""
    region = os.environ.get("AWS_REGION", "us-east-1")
    table_name = os.environ["DYNAMO_TABLE"]
    ddb = boto3.resource("dynamodb", region_name=region).Table(table_name)
    needles = ["무좀", "백선", "진균", "곰팡이", "사마귀", "어루러기", "건선", "두드러기", "습진"]
    hits = {n: [] for n in needles}
    total_classified = 0
    focus_counter: dict[str, int] = {}
    scan_kw = {"FilterExpression": "entity = :e", "ExpressionAttributeValues": {":e": "CLASSIFICATION"}}
    resp = ddb.scan(**scan_kw)
    items = resp.get("Items", [])
    while "LastEvaluatedKey" in resp:
        resp = ddb.scan(**scan_kw, ExclusiveStartKey=resp["LastEvaluatedKey"])
        items += resp.get("Items", [])
    for it in items:
        total_classified += 1
        pf = it.get("primary_focus") or []
        for f in pf:
            focus_counter[f] = focus_counter.get(f, 0) + 1
            for n in needles:
                if n in f:
                    hits[n].append(f)
    print(f"\n=== 분류 완료 병원(CLASSIFICATION) = {total_classified} ===")
    print("=== primary_focus 에 피부질환 키워드 포함 분포 ===")
    for n in needles:
        uniq = sorted(set(hits[n]))
        print(f"  '{n}' 포함 focus 라벨: {len(hits[n])}건  종류={uniq[:8]}")
    print("\n=== 상위 빈출 primary_focus 라벨 25 ===")
    for f, c in sorted(focus_counter.items(), key=lambda x: -x[1])[:25]:
        print(f"  {c:>4}  {f}")


if __name__ == "__main__":
    print("=" * 90)
    print("PART 1 — '무좀' 1위 통증클리닉 vs 피부과 청크 내용")
    print("=" * 90)
    dump_chunks("무좀", ["더건강의원", "리더스피부과의원", "아름다운나라피부과의원"])
    print("\n" + "=" * 90)
    print("PART 2 — 강남 분류 primary_focus 에 진균/피부질환 라벨이 존재하나")
    print("=" * 90)
    scan_focus()
