"""AI 트랙 dev 표본 적재 — 강남구 4과목 ~85개 HospitalMeta를 DDB에 박는다.

전략: HIRA `getHospBasisList`는 응답에 진료과목 정보를 포함하지 않고(필드 자체 없음),
ykiho 단위로 `getDgsbjtInfo2` 따로 호출해야 하는데 3124번 호출은 PoC 범위 초과라
**병원 이름(yadmNm) 키워드 매칭**으로 우회.

- 후보 키워드: '피부' / '정형' / '이비인후' / '안과'
- 강남구 전체 조회 → 이름에 키워드 포함된 의원 → 과목별 ~22개 sampling → dedupe(ykiho)
- URL 없는 병원도 포함 (P0.5 검증 — `crawler._empty_crawl_data` 폴백 케이스)

정확도 한계 — 이름에 과목 안 쓴 의원은 누락. PoC 시연 검증엔 충분.

실행:
    .venv/bin/python ai/scratch/load_dev_subset.py

전제: .env 의 TABLE_PREFIX=kmuproj-10-clinic-, HIRA_API_KEY 설정됨.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from be.scripts._utils import load_env  # noqa: E402

load_env()

from be.adapters.dynamo_adapter import DynamoAdapter  # noqa: E402
from be.adapters.hira_adapter import HiraAdapter  # noqa: E402
from shared.region_codes import SEOUL_SIDO_CODE, SEOUL_SIGUNGU_CODES  # noqa: E402

# 키워드 → 표준 진료과목 매핑. 이름에 키워드가 있으면 그 과목으로 라벨.
SPECIALTY_KEYWORDS: dict[str, str] = {
    "피부": "피부과",
    "정형": "정형외과",
    "이비인후": "이비인후과",
    "안과": "안과",
}
SAMPLES_PER_SPECIALTY = 22  # 4 × 22 = 88 → dedupe 후 ~85±5


def _match_specialty(name: str) -> str | None:
    for kw, specialty in SPECIALTY_KEYWORDS.items():
        if kw in name:
            return specialty
    return None


def main() -> None:
    print("=" * 60)
    print(f"AI dev 표본 적재 — 강남구 {len(SPECIALTY_KEYWORDS)}과목 ~85개")
    print("=" * 60)

    hira = HiraAdapter()
    db = DynamoAdapter()

    print("\n[1/3] HIRA — 강남구 전체 조회")
    raw_all = hira.get_hospitals_by_region(
        sido_code=SEOUL_SIDO_CODE,
        sigungu_code=SEOUL_SIGUNGU_CODES["강남구"],
    )
    print(f"  강남구 전체: {len(raw_all)}개")

    print("\n[2/3] 이름 키워드 매칭 + 과목별 sampling")
    by_specialty: dict[str, list[dict]] = defaultdict(list)
    for h in raw_all:
        specialty = _match_specialty(h.get("yadmNm", ""))
        if specialty:
            by_specialty[specialty].append(h)

    selected: dict[str, dict] = {}
    for specialty in SPECIALTY_KEYWORDS.values():
        candidates = by_specialty.get(specialty, [])
        sample = candidates[:SAMPLES_PER_SPECIALTY]
        for h in sample:
            ykiho = h.get("ykiho", "")
            if ykiho and ykiho not in selected:
                selected[ykiho] = h
        print(f"  {specialty}: 후보 {len(candidates)}개 → 샘플 {len(sample)}개")

    targets = list(selected.values())
    print(f"  dedupe 후 최종: {len(targets)}개")

    print("\n[3/3] HospitalMeta 변환 + DDB 적재")
    saved = 0
    url_yes = 0
    coord_missing = 0
    for h in targets:
        try:
            meta = hira.parse_hospital_meta(h)
            db.save_hospital_meta(meta)
            saved += 1
            if meta.contact.website_url:
                url_yes += 1
            if meta.location.lat is None or meta.location.lng is None:
                coord_missing += 1
        except Exception as e:
            print(f"  ❌ {h.get('yadmNm', '?')}: {e}")

    print("\n" + "=" * 60)
    print("적재 완료")
    print(f"  저장: {saved}/{len(targets)}개")
    print(f"  URL 보유: {url_yes}개 ({url_yes / saved * 100:.1f}%)" if saved else "  URL 보유: 0개")
    print(f"  좌표 누락: {coord_missing}개")
    print("=" * 60)


if __name__ == "__main__":
    main()
