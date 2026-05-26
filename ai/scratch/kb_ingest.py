"""KB DataSource S3 에 14개 병원 ingest + ingestion job 트리거.

DDB에 저장된 Classification + HospitalDescription 을 읽어서
KB 가 인덱싱할 텍스트 파일과 메타데이터 JSON을 S3 에 업로드.

키 규약 (CLAUDE.md):
- 본문: {KB_DATASOURCE_S3_PREFIX}{hospital_id}.txt
- 메타: {KB_DATASOURCE_S3_PREFIX}{hospital_id}.txt.metadata.json
- 메타 필수 필드: team_id="clinic-focus" (02팀과 공유 KB 격리 필터용)

실행:
    .venv/bin/python ai/scratch/kb_ingest.py
"""

from __future__ import annotations

import json
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from be.scripts._utils import load_env  # noqa: E402

load_env()

import boto3  # noqa: E402

from be.adapters.dynamo_adapter import DynamoAdapter  # noqa: E402


def _build_content_text(meta, classification, description) -> str:
    """KB가 임베딩할 본문. 한국어 자연어로 풀어쓴 통합 텍스트."""
    paragraphs = "\n\n".join(p.text for p in description.paragraphs)
    focus = ", ".join(classification.primary_focus) if classification.primary_focus else "특정 분야 없음"
    return f"""병원 이름: {meta.name}
지역: {meta.location.sido} {meta.location.sigungu}
주소: {meta.location.address}
진료과목: {classification.standard_specialty}
주력 분야: {focus}
신뢰도: {classification.confidence.score}

{paragraphs}
"""


def _build_metadata(meta, classification) -> dict:
    """KB Retrieve filter 용 metadata 파일 내용. Bedrock KB DataSource 스펙:
    {"metadataAttributes": {"key": value, ...}} — 단순 dict 형식 (List 아님).
    AWS 문서 "Add metadata to your files" 참조.
    """
    md = {
        "team_id": "clinic-focus",
        "hospital_id": meta.hospital_id,
        "name": meta.name,
        "standard_specialty": classification.standard_specialty,
        "sido": meta.location.sido,
        "sigungu": meta.location.sigungu,
        "confidence_score": classification.confidence.score,
    }
    # 빈 리스트는 AWS KB 가 invalid metadata 로 거절 (2026-05-26 확인).
    # primary_focus 가 비어있으면 메타에서 아예 제외.
    if classification.primary_focus:
        md["primary_focus"] = classification.primary_focus
    if meta.location.lat is not None:
        md["lat"] = meta.location.lat
    if meta.location.lng is not None:
        md["lng"] = meta.location.lng
    return {"metadataAttributes": md}


def main() -> None:
    bucket = os.environ["KB_DATASOURCE_S3_BUCKET"]
    prefix = os.environ["KB_DATASOURCE_S3_PREFIX"].lstrip("/")
    kb_id = os.environ["KB_ID"]
    ds_id = os.environ["KB_DATA_SOURCE_ID"]

    print("=" * 60)
    print(f"KB ingest — bucket={bucket} prefix={prefix}")
    print(f"  KB_ID={kb_id}, DataSource={ds_id}")
    print("=" * 60)

    db = DynamoAdapter()
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))

    # 모든 Hospitals 스캔 후 Classifications + HospitalDescriptions 있는 것만 ingest
    scan_resp = db._table("Hospitals").scan()
    items = scan_resp.get("Items", [])
    print(f"\n전체 Hospitals: {len(items)}개")

    uploaded = 0
    skipped = 0

    for item in items:
        hospital_id = item["hospital_id"]
        meta = db.load_hospital_meta(hospital_id)
        classification = db.load_classification(hospital_id)
        description = db.load_description(hospital_id)

        if not (meta and classification and description):
            skipped += 1
            continue

        content = _build_content_text(meta, classification, description)
        metadata = _build_metadata(meta, classification)

        text_key = f"{prefix}{hospital_id}.txt"
        meta_key = f"{text_key}.metadata.json"

        s3.put_object(
            Bucket=bucket,
            Key=text_key,
            Body=content.encode("utf-8"),
            ContentType="text/plain; charset=utf-8",
        )
        s3.put_object(
            Bucket=bucket,
            Key=meta_key,
            Body=json.dumps(metadata, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )
        uploaded += 1
        print(f"  ✅ {meta.name}: {text_key}")

    print(f"\n업로드: {uploaded}개 (스킵 {skipped}개)")

    if uploaded == 0:
        print("적재할 게 없어 ingestion job 생략")
        return

    print("\n[StartIngestionJob 트리거]")
    agent = boto3.client("bedrock-agent", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    job = agent.start_ingestion_job(
        knowledgeBaseId=kb_id,
        dataSourceId=ds_id,
    )
    job_id = job["ingestionJob"]["ingestionJobId"]
    status = job["ingestionJob"]["status"]
    print(f"  job_id={job_id}, status={status}")

    # 폴링 — ingestion 완료까지 (최대 10분)
    deadline = time.time() + 600
    while time.time() < deadline:
        time.sleep(15)
        resp = agent.get_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
            ingestionJobId=job_id,
        )
        status = resp["ingestionJob"]["status"]
        stats = resp["ingestionJob"].get("statistics", {})
        print(f"  [{int(time.time() - (deadline - 600))}s] status={status} stats={stats}")
        if status in ("COMPLETE", "FAILED", "STOPPED"):
            break

    print("=" * 60)


if __name__ == "__main__":
    main()
