"""S3 표본 502개 본문 키워드 분포 측정 (일회성).

목적:
- HIRA getHospBasisList 응답에 진료과목 정보가 없음 (실측).
- 의원(종별)으로 분류된 99개의 양방 진료과목을 본문 키워드로 추정.
- 한의원·치과의원·한방병원 등은 종별로 식별되므로 본 스크립트 제외 (별도 표).

방법:
- S3 crawl_data.json `pages[*].html_text` 를 합쳐 전체 본문 1건/병원.
- 진료과목·시술명 키워드 사전을 본문에서 정규식 매칭.
- 매칭 카운트로 병원당 상위 1~3개 과목 추정.

산출:
- ai/scratch/body-keywords-2026-05-27.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from be.adapters.hira_adapter import HiraAdapter  # noqa: E402
from shared.region_codes import SEOUL_SIDO_CODE, SEOUL_SIGUNGU_CODES  # noqa: E402

S3_BUCKET = "kmuproj-10-clinic-focus-crawl"
S3_PREFIX = "crawl/"
OUT_JSON = Path(__file__).resolve().parent / "body-keywords-2026-05-27.json"

# 본문 키워드 사전 — 표준 진료과목 후보 + 시술명·증상 키워드.
# 한의원·치과·한방병원은 종별로 이미 식별되므로 제외 (양방 의원만 대상).
SPECIALTY_KEYWORDS: dict[str, list[str]] = {
    "피부과": ["피부과", "피부 진료", "기미", "여드름", "아토피", "보톡스", "필러",
              "레이저 토닝", "리프팅", "여드름 흉터", "사마귀", "탈모", "모발 이식"],
    "정형외과": ["정형외과", "척추", "디스크", "관절", "무릎", "어깨", "도수치료",
                "체외충격파", "수부외과", "스포츠의학", "회전근개", "허리"],
    "이비인후과": ["이비인후과", "비염", "축농증", "수면 무호흡", "코골이", "중이염",
                  "이명", "어지럼", "갑상선", "편도", "알레르기 비염"],
    "안과": ["안과", "라식", "라섹", "백내장", "녹내장", "노안", "망막", "스마일 라식",
            "ICL"],
    "내과": ["내과", "당뇨", "고혈압", "위장", "위내시경", "대장내시경", "갑상선 검진",
            "건강검진", "위염", "역류성 식도염"],
    "소아청소년과": ["소아청소년과", "소아과", "예방접종", "신생아", "성장", "발달"],
    "산부인과": ["산부인과", "여성의학", "임신", "출산", "자궁", "난소", "월경",
                "산전", "산후"],
    "가정의학과": ["가정의학과", "가의과", "비만", "다이어트", "감기"],
    "비뇨의학과": ["비뇨의학과", "비뇨기과", "전립선", "요로", "성기능", "포경"],
    "정신건강의학과": ["정신건강의학과", "정신과", "우울", "공황", "불면", "ADHD",
                      "수면장애"],
    "성형외과": ["성형외과", "성형 수술", "코 성형", "눈 성형", "쌍꺼풀", "가슴 성형",
                "지방흡입"],
    "신경과": ["신경과", "두통", "어지럼증", "치매", "파킨슨", "뇌졸중"],
    "재활의학과": ["재활의학과", "재활 치료", "운동 치료", "도수 재활"],
    "외과": ["외과", "탈장", "갑상선 수술", "유방", "치질", "치핵"],
    "마취통증의학과": ["마취통증의학과", "통증 클리닉", "신경 차단"],
}


def list_s3_hospital_ids() -> set[str]:
    s3 = boto3.client("s3")
    ids: set[str] = set()
    for page in s3.get_paginator("list_objects_v2").paginate(
        Bucket=S3_BUCKET, Prefix=S3_PREFIX, Delimiter="/"
    ):
        for p in page.get("CommonPrefixes") or []:
            hid = p["Prefix"][len(S3_PREFIX):].rstrip("/")
            if hid:
                ids.add(hid)
    return ids


def fetch_clinic_type_map() -> dict[str, str]:
    """ykiho → clCdNm 매핑 (HIRA 강남 1회 호출)."""
    hira = HiraAdapter()
    rows = hira.get_hospitals_by_region(
        sido_code=SEOUL_SIDO_CODE,
        sigungu_code=SEOUL_SIGUNGU_CODES["강남구"],
    )
    return {r["ykiho"]: r.get("clCdNm", "") for r in rows if r.get("ykiho")}


def load_body_text(hospital_id: str) -> str:
    """S3 에서 crawl_data.json 읽어 pages 본문 전체를 1개 문자열로."""
    s3 = boto3.client("s3")
    key = f"{S3_PREFIX}{hospital_id}/crawl_data.json"
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    data = json.loads(obj["Body"].read())
    return "\n".join(p.get("html_text", "") for p in data.get("pages", []))


def count_keywords(text: str) -> dict[str, int]:
    """본문에서 진료과목별 키워드 매칭 총량."""
    out: dict[str, int] = {}
    for spec, kws in SPECIALTY_KEYWORDS.items():
        total = sum(text.count(kw) for kw in kws)
        if total > 0:
            out[spec] = total
    return out


def main() -> None:
    print("[1/4] S3 hospital_id 수집...")
    s3_ids = sorted(list_s3_hospital_ids())
    print(f"  {len(s3_ids)}개")

    print("[2/4] HIRA 종별 매핑 수집...")
    type_map = fetch_clinic_type_map()
    print(f"  {len(type_map)}개")

    print("[3/4] 의원만 추려서 본문 다운로드 + 키워드 매칭...")
    uiwon_ids = [hid for hid in s3_ids if type_map.get(hid) == "의원"]
    print(f"  의원: {len(uiwon_ids)}개")

    # 종별별 카운트
    type_counter: Counter[str] = Counter()
    for hid in s3_ids:
        type_counter[type_map.get(hid, "<unknown>")] += 1
    print(f"  표본 종별: {dict(type_counter)}")

    # 의원 본문 키워드 매칭
    per_hospital: dict[str, dict[str, int]] = {}
    top_specialty_per_hospital: dict[str, str | None] = {}
    primary_counter: Counter[str] = Counter()
    matched_no_keyword = 0

    for i, hid in enumerate(uiwon_ids, 1):
        try:
            text = load_body_text(hid)
        except Exception as e:
            print(f"    [{i}/{len(uiwon_ids)}] {hid[:10]}... 로드 실패: {e}")
            continue
        counts = count_keywords(text)
        per_hospital[hid] = counts
        if counts:
            top = max(counts.items(), key=lambda kv: kv[1])
            top_specialty_per_hospital[hid] = top[0]
            primary_counter[top[0]] += 1
        else:
            top_specialty_per_hospital[hid] = None
            matched_no_keyword += 1
        if i % 20 == 0:
            print(f"    [{i}/{len(uiwon_ids)}] 진행 중...")

    print("[4/4] 결과 정리...")
    print()
    print("=" * 60)
    print(f"의원 {len(uiwon_ids)}개의 추정 대표 진료과목 분포 (키워드 매칭 최다)")
    print("=" * 60)
    for spec, n in primary_counter.most_common():
        print(f"    {spec:20s} {n:4d}")
    print(f"    (키워드 매칭 0건: {matched_no_keyword}개)")

    # 전체 카운트 — 의원만, 단일과목 아닌 다중과목 어느 정도?
    multi_specialty = sum(1 for c in per_hospital.values() if len(c) >= 2)
    print(f"\n다중 과목 매칭(2개 이상): {multi_specialty}개")

    out = {
        "generated_at": "2026-05-27",
        "source": {
            "s3_bucket": S3_BUCKET,
            "s3_prefix": S3_PREFIX,
            "method": "body keyword regex match on uiwon-class hospitals",
        },
        "sample_type_distribution": dict(type_counter),
        "uiwon_count": len(uiwon_ids),
        "uiwon_primary_specialty_distribution": dict(primary_counter.most_common()),
        "uiwon_no_keyword_count": matched_no_keyword,
        "uiwon_multi_specialty_count": multi_specialty,
        "keywords_used": SPECIALTY_KEYWORDS,
        "per_hospital_top_specialty": top_specialty_per_hospital,
        "per_hospital_keyword_counts": per_hospital,
    }
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {OUT_JSON}")


if __name__ == "__main__":
    main()
