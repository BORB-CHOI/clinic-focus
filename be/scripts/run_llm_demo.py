"""LLM+Vision 시연 배치 (트랙 B+C) — 시연 N개 병원 풀 파이프라인.

run_index_pipeline(demo=True) 를 시연 대상에 돌린다:
  classify_hospital(use_llm=True, use_vision=True, vision_results=VISION#RESULTS)
  → DDB CLASSIFICATION (4축: 자칭LLM·블로그·후기·Vision)
  → generate_description / extract_services_and_doctors / find_related_hospitals (LLM)
  → build_signal_chunks(스크럽·동의어 적용) → KB DataSource S3 (trigger_ingestion=False)

대상 기본값 = VISION#RESULTS 적재된 병원(=run_vision_demo 가 처리한 시연 셋).
KB 인제스션은 --ingest 일 때만 마지막에 1회 트리거(다른 ingestion job 진행 중이면 충돌하니
스크럽 배치 잡이 끝난 뒤 따로 트리거할 것).

실행: .venv/bin/python be/scripts/run_llm_demo.py [--hospital-ids ID...] [--ingest]
"""

from __future__ import annotations

import argparse
import os
import sys

sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from be.adapters.dynamo_adapter import DynamoAdapter  # noqa: E402
from be.handlers.index_hospital import run_index_pipeline  # noqa: E402


def _vision_holders(db: DynamoAdapter) -> list[str]:
    """VISION#RESULTS 가 적재된 병원 id (=시연 대상)."""
    import boto3
    t = boto3.resource("dynamodb", "us-east-1").Table("kmuproj-10-clinic-Main")
    ids, lek = [], None
    while True:
        kw = {"FilterExpression": "entity = :e",
              "ExpressionAttributeValues": {":e": "VISION#RESULTS"},
              "ProjectionExpression": "hospital_id"}
        if lek:
            kw["ExclusiveStartKey"] = lek
        r = t.scan(**kw)
        ids += [it["hospital_id"] for it in r["Items"]]
        lek = r.get("LastEvaluatedKey")
        if not lek:
            break
    return ids


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="LLM+Vision 시연 배치 (트랙 B+C)")
    ap.add_argument("--hospital-ids", nargs="*", default=None, help="대상 id (생략 시 VISION#RESULTS 보유분)")
    ap.add_argument("--ingest", action="store_true", help="마지막에 KB ingestion job 1회 트리거")
    args = ap.parse_args(argv)

    db = DynamoAdapter()
    ids = args.hospital_ids or _vision_holders(db)
    print(f"{'='*60}\nLLM+Vision 시연 배치 — {len(ids)}개\n{'='*60}")

    ok = err = 0
    for i, hid in enumerate(ids, 1):
        try:
            res = run_index_pipeline(hid, demo=True, trigger_ingestion=False)
            if res.get("status") == "error":
                err += 1
                print(f"  [{i}/{len(ids)}] ⚠️ {hid[:16]} — {res.get('reason')}")
                continue
            ok += 1
            cls = res.get("classification") or {}
            conf = (cls.get("confidence") or {}) if isinstance(cls, dict) else {}
            print(f"  [{i}/{len(ids)}] ✅ {res.get('name', hid[:16])} — "
                  f"{cls.get('primary_focus') if isinstance(cls, dict) else ''} "
                  f"(신뢰도 {conf.get('score','?')} {conf.get('level','?')})")
        except Exception as e:  # noqa: BLE001
            err += 1
            print(f"  [{i}/{len(ids)}] ❌ {hid[:16]} — {type(e).__name__}: {str(e)[:120]}")

    print(f"\n{'='*60}\n완료 — ✅ {ok} / ❌ {err}")
    if args.ingest and ok:
        import boto3
        ag = boto3.client("bedrock-agent", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        job = ag.start_ingestion_job(knowledgeBaseId=os.environ["KB_ID"],
                                     dataSourceId=os.environ["KB_DATA_SOURCE_ID"])
        print(f"KB ingestion job: {job['ingestionJob']['ingestionJobId']} {job['ingestionJob']['status']}")
    else:
        print("KB 인제스션 미트리거(--ingest 로 트리거). 다른 job 진행 중이면 끝난 뒤 트리거할 것.")
    print('='*60)


if __name__ == "__main__":
    main()
