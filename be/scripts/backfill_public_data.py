"""심평원 공공데이터(전문의·의료장비·비급여) — 강남구 한정 추가 적재(backfill).

★강남만. load_seoul_5gu(5개구+META 재기록)와 달리 이 스크립트는:
  - 강남구(sgguCd=110001) base 목록만 조회
  - META 는 건드리지 않고 PUBLIC#DOCTORS / PUBLIC#NONPAY entity 만 추가(additive)
  - 재실행 가능(SKIP_EXISTING=true 기본 — 이미 적재된 PUBLIC#DOCTORS 는 건너뜀)

total_doctors 는 base getHospBasisList 의 drTotCnt 사용(상세 서비스엔 per-ykiho 의사수 없음).
사용: `.venv/bin/python be/scripts/backfill_public_data.py`
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from be.adapters.dynamo_adapter import DynamoAdapter
from be.adapters.hira_adapter import HiraAdapter

GANGNAM_SIGUNGU = "110001"
SEOUL_SIDO = "110000"
SKIP_EXISTING = os.environ.get("SKIP_EXISTING", "true").lower() == "true"


def main() -> None:
    hira = HiraAdapter()
    db = DynamoAdapter()

    print("심평원 공공데이터 강남구 backfill (전문의·의료장비·비급여) — META 무손상", flush=True)
    raw_hospitals = hira.get_hospitals_by_region(sido_code=SEOUL_SIDO, sigungu_code=GANGNAM_SIGUNGU)
    total = len(raw_hospitals)
    print(f"강남 병원 {total}개 조회. SKIP_EXISTING={SKIP_EXISTING}", flush=True)

    done = skipped = with_spec = with_nonpay = with_dev = errors = 0
    t0 = time.time()

    for i, raw in enumerate(raw_hospitals, 1):
        ykiho = raw.get("ykiho")
        if not ykiho:
            continue
        try:
            if SKIP_EXISTING and db.load_public_doctors(ykiho):
                skipped += 1
            else:
                dr_tot = int(raw.get("drTotCnt") or 0) or None
                pd = hira.get_public_data(ykiho, dr_tot_cnt=dr_tot)
                db.save_public_doctors(ykiho, pd)
                if pd.nonpay_items:
                    db.save_public_nonpay(ykiho, pd.nonpay_items)
                    with_nonpay += 1
                if any(c >= 1 for c in pd.specialists_by_dept.values()):
                    with_spec += 1
                if pd.registered_devices:
                    with_dev += 1
            done += 1
        except Exception as e:  # 개별 실패는 전체를 막지 않음(재실행으로 회복)
            errors += 1
            if errors <= 10:
                print(f"  [err] {ykiho[:16]}: {e}", flush=True)

        if i % 100 == 0 or i == total:
            rate = i / max(1e-9, time.time() - t0)
            eta = (total - i) / max(1e-9, rate)
            print(
                f"  {i}/{total} | 적재 {done} 스킵 {skipped} | 전문의보유 {with_spec} "
                f"비급여 {with_nonpay} 장비 {with_dev} 오류 {errors} | "
                f"{rate:.1f}/s ETA {eta/60:.1f}분",
                flush=True,
            )

    print(
        f"\n완료: 총 {total} | 적재 {done} 스킵 {skipped} | 전문의보유 {with_spec} "
        f"비급여 {with_nonpay} 장비 {with_dev} 오류 {errors} | {(time.time()-t0)/60:.1f}분",
        flush=True,
    )


if __name__ == "__main__":
    main()
