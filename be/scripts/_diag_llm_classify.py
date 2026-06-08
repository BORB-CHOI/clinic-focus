"""LLM 세부분류 프로토타입 — '기타' 병원을 크롤 자칭 텍스트로 Nova가 제대로 재분류하나.
DB 미수정(읽기 전용). 콘솔 전용."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

import boto3  # noqa: E402

SPECIALTIES = (
    "내과 소아청소년과 이비인후과 안과 피부과 성형외과 정형외과 신경외과 외과 산부인과 "
    "비뇨의학과 정신건강의학과 가정의학과 재활의학과 마취통증의학과 신경과 한의원 치과 "
    "종합병원 요양병원 보건소 기타"
).split()

PROMPT = (
    "다음은 한 병원이 자기 사이트에 적은 진료 관련 키워드/주력 분야다.\n"
    "병원명: {name}\n자칭 키워드: {kw}\n현재 주력(primary_focus): {pf}\n\n"
    "이 병원의 표준 진료과목을 아래 목록에서 정확히 하나 고르라(평가·추천 말고 분류만):\n"
    "{specs}\n\n"
    "JSON 한 줄로만 출력: {{\"specialty\": \"<목록 중 하나>\", \"reason\": \"<10자 이내>\"}}"
)


def nova_classify(name, kw, pf, client):
    prompt = PROMPT.format(name=name, kw=", ".join(kw[:25]), pf=", ".join(pf),
                           specs=" / ".join(SPECIALTIES))
    resp = client.converse(
        modelId="amazon.nova-lite-v1:0",
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 120, "temperature": 0.0},
    )
    txt = resp["output"]["message"]["content"][0]["text"].strip()
    # JSON 추출
    a, b = txt.find("{"), txt.rfind("}")
    if a >= 0 and b > a:
        try:
            return json.loads(txt[a:b + 1])
        except Exception:
            pass
    return {"specialty": "?", "reason": txt[:30]}


def main(limit=8):
    region = os.environ.get("AWS_REGION", "us-east-1")
    ddb = boto3.resource("dynamodb", region_name=region).Table(os.environ["DYNAMO_TABLE"])
    bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

    # 기타 분류 병원 스캔
    kw_filter = {"FilterExpression": "entity = :e AND standard_specialty = :s",
                 "ExpressionAttributeValues": {":e": "CLASSIFICATION", ":s": "기타"}}
    resp = ddb.scan(**kw_filter, Limit=400)
    items = resp.get("Items", [])
    # 자칭 키워드가 있는 것 위주로 limit개
    picked = []
    for it in items:
        ds = it.get("detailed_signals", {}) or {}
        sc = ds.get("self_claim") or {}
        kw = sc.get("keywords") or sc.get("extracted_keywords") or []
        if kw:
            picked.append((it, kw))
        if len(picked) >= limit:
            break

    print(f"기타 병원 {len(picked)}개 LLM 재분류 (Nova Lite, 읽기전용):\n")
    print(f"{'병원명':<22} {'현 분류':<6} → {'LLM 재분류':<10} 근거 | 자칭키워드")
    print("-" * 100)
    for it, kw in picked:
        name = it.get("hospital_id", "?")
        # META 에서 이름
        meta = ddb.get_item(Key={"hospital_id": it["hospital_id"], "entity": "META"}).get("Item", {})
        nm = meta.get("name", it["hospital_id"][:12])
        pf = it.get("primary_focus", [])
        res = nova_classify(nm, kw, pf, bedrock)
        print(f"{nm[:22]:<22} {'기타':<6} → {res.get('specialty','?'):<10} "
              f"{res.get('reason','')[:12]:<12} | {', '.join(kw[:6])}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
