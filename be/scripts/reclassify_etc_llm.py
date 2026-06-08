"""기타 병원 LLM 세부분류 — 수술적(비미용 의료과목만 이동). 기본 dry-run(DB 미수정).

--write 플래그가 있을 때만 DDB CLASSIFICATION.standard_specialty + META GSI 갱신.
KB 메타 재적재는 별도 단계(이 스크립트는 분류 결정까지).
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
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
VALID = set(SPECIALTIES)

# 순수 미용 부티크는 기타(→FE '미용' 버킷) 유지 — 피부과/성형 카테고리 오염 방지.
PROMPT = (
    "한 병원이 자기 사이트에 적은 진료 키워드/주력이다. 표준 진료과목을 분류만 하라(평가 금지).\n"
    "병원명: {name}\n자칭 키워드: {kw}\n주력: {pf}\n\n"
    "규칙:\n"
    "- 보톡스·필러·리프팅·지방흡입 등 '순수 미용/성형 시술만' 하는 의원이면 is_cosmetic_only=true.\n"
    "- 정신·안과·정형·재활·내과·이비인후·비뇨·산부인·신경·외과·소아 등 명확한 질환 진료가 있으면 그 과목.\n"
    "후보: {specs}\n"
    'JSON 한 줄: {{"specialty":"<후보 중 하나>","is_cosmetic_only":<true/false>}}'
)


def classify(name, kw, pf, client) -> dict:
    prompt = PROMPT.format(name=name, kw=", ".join(kw[:25]), pf=", ".join(pf),
                           specs=" / ".join(SPECIALTIES))
    for attempt in range(4):
        try:
            resp = client.converse(
                modelId="amazon.nova-lite-v1:0",
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 80, "temperature": 0.0},
            )
            txt = resp["output"]["message"]["content"][0]["text"]
            a, b = txt.find("{"), txt.rfind("}")
            r = json.loads(txt[a:b + 1])
            sp = r.get("specialty", "기타")
            return {"specialty": sp if sp in VALID else "기타",
                    "cosmetic": bool(r.get("is_cosmetic_only", False))}
        except Exception as e:
            if "throttl" in str(e).lower() or "ThrottlingException" in str(e):
                time.sleep(1.5 * (attempt + 1))
                continue
            return {"specialty": "기타", "cosmetic": False, "err": str(e)[:60]}
    return {"specialty": "기타", "cosmetic": False, "err": "throttled"}


def main(write=False):
    region = os.environ.get("AWS_REGION", "us-east-1")
    ddb = boto3.resource("dynamodb", region_name=region).Table(os.environ["DYNAMO_TABLE"])
    bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

    kw_filter = {"FilterExpression": "entity = :e AND standard_specialty = :s",
                 "ExpressionAttributeValues": {":e": "CLASSIFICATION", ":s": "기타"}}
    resp = ddb.scan(**kw_filter)
    items = resp.get("Items", [])
    while "LastEvaluatedKey" in resp:
        resp = ddb.scan(**kw_filter, ExclusiveStartKey=resp["LastEvaluatedKey"])
        items += resp.get("Items", [])
    print(f"기타 분류 병원: {len(items)}개", flush=True)

    new_dist = Counter()
    reassign = 0
    keep_cosmetic = 0
    no_kw = 0
    samples = []
    results = []
    for i, it in enumerate(items):
        ds = it.get("detailed_signals", {}) or {}
        sc = ds.get("self_claim") or {}
        kw = sc.get("keywords") or sc.get("extracted_keywords") or []
        pf = it.get("primary_focus", []) or []
        if not kw and not pf:
            no_kw += 1
            new_dist["기타(자칭없음)"] += 1
            continue
        meta = ddb.get_item(Key={"hospital_id": it["hospital_id"], "entity": "META"}).get("Item", {})
        nm = meta.get("name", it["hospital_id"][:10])
        r = classify(nm, kw, pf, bedrock)
        # 수술적 규칙: 미용전용이거나 결과가 기타면 유지, 아니면 이동
        if r["cosmetic"] or r["specialty"] == "기타":
            final = "기타"
            keep_cosmetic += 1
        else:
            final = r["specialty"]
            reassign += 1
        new_dist[final] += 1
        results.append({"hospital_id": it["hospital_id"], "name": nm,
                        "from": "기타", "to": final, "cosmetic": r["cosmetic"], "kw": kw[:8]})
        if len(samples) < 30 and final != "기타":
            samples.append(f"  {nm[:18]:<18} 기타 → {final:<8} | {', '.join(kw[:5])}")
        if (i + 1) % 50 == 0:
            print(f"  ...{i+1}/{len(items)} 처리 (이동 {reassign}, 미용유지 {keep_cosmetic})", flush=True)

    print(f"\n=== 결과 (dry-run{'' if not write else ' + WRITE'}) ===", flush=True)
    print(f"  이동(비미용 의료과목): {reassign}  |  미용유지(기타): {keep_cosmetic}  |  자칭없음: {no_kw}")
    print("\n  재분류 후 분포:")
    for sp, n in new_dist.most_common():
        print(f"    {n:>4}  {sp}")
    print("\n  이동 샘플 30:")
    for s in samples:
        print(s)

    out = ROOT / "be" / "scripts" / "_reclassify_result.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"\n  전체 결과 저장: {out}")

    if write:
        print("\n=== WRITE 모드: DDB 갱신 ===", flush=True)
        # 별도 확인 후 구현 — 지금은 dry-run만
        print("  (write 적용 로직은 dry-run 검토 후 활성화)")


if __name__ == "__main__":
    main(write="--write" in sys.argv)
