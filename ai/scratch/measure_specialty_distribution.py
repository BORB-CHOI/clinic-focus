"""강남 502개 표본의 standard_specialty 분포 측정 (일회성).

목적:
- ai/CLAUDE.md "분류 스키마" 박스 확장 의사결정용 실측 데이터 산출.
- HIRA getHospBasisList 강남(110001) 1회 호출 → 진료과목(dgsbjtCdNm) 분포.
- S3 kmuproj-10-clinic-focus-crawl/crawl/ 의 502개 hospital_id 와 교차.

산출:
- 표준 진료과목별 카운트 (전체 강남)
- S3 표본 502개와 교차한 카운트
- 미커버 과목(현 4과목 — 피부과/정형외과/이비인후과/안과 외) 목록
- JSON 결과를 ai/scratch/specialty-distribution-2026-05-27.json 로 저장

phase C 본체 마이그레이션 후 이 스크립트는 scratch 와 함께 삭제 예정.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from be.adapters.hira_adapter import HiraAdapter  # noqa: E402
from shared.region_codes import SEOUL_SIDO_CODE, SEOUL_SIGUNGU_CODES  # noqa: E402

S3_BUCKET = "kmuproj-10-clinic-focus-crawl"
S3_PREFIX = "crawl/"
OUT_DIR = Path(__file__).resolve().parent
OUT_JSON = OUT_DIR / "specialty-distribution-2026-05-27.json"
CURRENT_COVERED = {"피부과", "정형외과", "이비인후과", "안과"}


def list_s3_hospital_ids() -> set[str]:
    """S3 mirror 의 502개 hospital_id 디렉토리 목록."""
    client = boto3.client("s3")
    paginator = client.get_paginator("list_objects_v2")
    ids: set[str] = set()
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_PREFIX, Delimiter="/"):
        for prefix in page.get("CommonPrefixes") or []:
            key = prefix["Prefix"]
            hospital_id = key[len(S3_PREFIX):].rstrip("/")
            if hospital_id:
                ids.add(hospital_id)
    return ids


def fetch_hira_gangnam() -> list[dict]:
    """HIRA 강남구 전체 병원 — getHospBasisList 응답 그대로."""
    hira = HiraAdapter()
    return hira.get_hospitals_by_region(
        sido_code=SEOUL_SIDO_CODE,
        sigungu_code=SEOUL_SIGUNGU_CODES["강남구"],
    )


def extract_specialty(raw: dict) -> str | None:
    """HIRA 응답 1건에서 진료과목명(dgsbjtCdNm) 추출.

    실측 결과: getHospBasisList 응답 row 에는 진료과목 필드가 없음.
    종별(clCdNm)만 있음. 진료과목 정확치는 ykiho 별 별도 호출 필요.
    """
    return raw.get("dgsbjtCdNm") or None


def extract_cl_cd_nm(raw: dict) -> str | None:
    """HIRA 응답의 종별 명칭 — 진료과목 proxy 로 1차 분포 측정용.

    예: '의원', '치과의원', '한의원', '병원', '한방병원', '치과병원',
    '종합병원', '상급종합병원', '요양병원', '정신병원'.
    종별만으로는 의원의 진료과목(피부과/정형외과/안과/이비인후과 등)을 구분 못 함.
    """
    return raw.get("clCdNm") or None


def main() -> None:
    if not os.environ.get("HIRA_API_KEY"):
        print("HIRA_API_KEY 환경변수가 비어 있음. .env 확인.", file=sys.stderr)
        sys.exit(1)

    print("[1/3] S3 mirror 502개 hospital_id 목록 수집...")
    s3_ids = list_s3_hospital_ids()
    print(f"  S3 mirror: {len(s3_ids)}개")

    print("[2/3] HIRA 강남구 호출...")
    raw_hospitals = fetch_hira_gangnam()
    print(f"  HIRA 응답 row: {len(raw_hospitals)}개")

    # row 한 건의 키 구조 확인
    if raw_hospitals:
        sample_keys = sorted(raw_hospitals[0].keys())
        print(f"  샘플 row keys: {sample_keys}")

    print("[3/3] 분포 집계...")
    # 응답 row 가 병원당 1건이라고 가정 (HIRA getHospBasisList 표준 동작)
    # 진료과목 필드가 없으면 None 분류
    ykiho_to_row: dict[str, dict] = {}
    for raw in raw_hospitals:
        ykiho = raw.get("ykiho", "")
        if not ykiho:
            continue
        ykiho_to_row[ykiho] = raw

    # 전체 강남 (HIRA row 1건 = 병원 1개)
    all_specialty_counter: Counter[str] = Counter()
    all_clcd_counter: Counter[str] = Counter()
    null_count_all = 0
    for ykiho, raw in ykiho_to_row.items():
        spec = extract_specialty(raw)
        if spec:
            all_specialty_counter[spec] += 1
        else:
            null_count_all += 1
        clcd = extract_cl_cd_nm(raw)
        if clcd:
            all_clcd_counter[clcd] += 1

    # 표본 502 교차
    sample_specialty_counter: Counter[str] = Counter()
    sample_clcd_counter: Counter[str] = Counter()
    null_count_sample = 0
    matched_sample = 0
    for hid in s3_ids:
        raw = ykiho_to_row.get(hid)
        if raw is None:
            continue  # S3 에 있는데 HIRA 강남에 없음 (이상 케이스)
        matched_sample += 1
        spec = extract_specialty(raw)
        if spec:
            sample_specialty_counter[spec] += 1
        else:
            null_count_sample += 1
        clcd = extract_cl_cd_nm(raw)
        if clcd:
            sample_clcd_counter[clcd] += 1

    s3_minus_hira = s3_ids - ykiho_to_row.keys()
    hira_minus_s3 = ykiho_to_row.keys() - s3_ids

    # 결과 출력
    print()
    print("=" * 60)
    print(f"[1] clCdNm 분포 — 전체 강남 (HIRA 3128)")
    print("=" * 60)
    for k, n in all_clcd_counter.most_common():
        print(f"    {k:20s} {n:5d}")

    print()
    print("=" * 60)
    print(f"[2] clCdNm 분포 — S3 표본 502 (matched={matched_sample})")
    print("=" * 60)
    for k, n in sample_clcd_counter.most_common():
        print(f"    {k:20s} {n:5d}")

    if all_specialty_counter:
        print()
        print("=" * 60)
        print("[3] dgsbjtCdNm 분포 — 전체 강남 (해당 필드가 응답에 있을 때)")
        print("=" * 60)
        for spec, n in all_specialty_counter.most_common():
            marker = "✓" if spec in CURRENT_COVERED else " "
            print(f"  {marker} {spec:30s} {n:4d}")

    # 미커버 상위 (dgsbjtCdNm 기반 — 응답에 필드 없으면 비어 있음)
    uncovered = [
        (spec, n)
        for spec, n in sample_specialty_counter.most_common()
        if spec not in CURRENT_COVERED
    ]
    if uncovered:
        print()
        print("=" * 60)
        print("[4] 표본 미커버 상위 (분류 스키마 확장 후보)")
        print("=" * 60)
        for spec, n in uncovered[:15]:
            print(f"    {spec:30s} {n:4d}")

    # JSON 저장
    out = {
        "generated_at": "2026-05-27",
        "source": {
            "hira_endpoint": "getHospBasisList",
            "sido_code": SEOUL_SIDO_CODE,
            "sigungu": "강남구",
            "sigungu_code": SEOUL_SIGUNGU_CODES["강남구"],
            "s3_bucket": S3_BUCKET,
            "s3_prefix": S3_PREFIX,
        },
        "counts": {
            "hira_gangnam_rows": len(raw_hospitals),
            "hira_gangnam_unique_ykiho": len(ykiho_to_row),
            "s3_mirror_hospital_ids": len(s3_ids),
            "intersection_s3_in_hira": matched_sample,
            "s3_not_in_hira": len(s3_minus_hira),
            "hira_not_in_s3": len(hira_minus_s3),
            "null_specialty_all": null_count_all,
            "null_specialty_sample": null_count_sample,
        },
        "all_gangnam_clcd_distribution": dict(all_clcd_counter.most_common()),
        "s3_sample_clcd_distribution": dict(sample_clcd_counter.most_common()),
        "all_gangnam_specialty_distribution_dgsbjt": dict(all_specialty_counter.most_common()),
        "s3_sample_specialty_distribution_dgsbjt": dict(sample_specialty_counter.most_common()),
        "s3_sample_uncovered_specialties_dgsbjt": dict(uncovered),
        "currently_covered_in_schema": sorted(CURRENT_COVERED),
        "sample_hira_row_keys": sorted(raw_hospitals[0].keys()) if raw_hospitals else [],
        "note": (
            "getHospBasisList 응답에는 dgsbjtCdNm 필드가 없음 — clCdNm(종별)만 신뢰 가능."
            " 진료과목 정확치는 ykiho 별 별도 호출(getDgsbjtInfo 류) 필요."
        ),
    }
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {OUT_JSON}")


if __name__ == "__main__":
    main()
