"""심평원 getDtlInfo2.8 운영시간 — 강남구 한정 추가 적재(backfill).

★강남만·additive·META 무손상.

- 강남구(sgguCd=110001) base 목록 조회
- META / PUBLIC#NONPAY 는 건드리지 않고 PUBLIC#DOCTORS entity 에 operating_hours 필드만 추가
- 기존 PUBLIC#DOCTORS 에 operating_hours 가 이미 있으면 SKIP_EXISTING=true(기본) 시 건너뜀
- getDtlInfo2.8 가 비어 있거나(종합병원 등) 예외 시 graceful skip (오류 카운트만)
- 요청 간격 조절(REQUEST_DELAY_SEC) — 심평원 API 과부하 방지

사용:
  SKIP_EXISTING=true .venv/bin/python be/scripts/backfill_operating_hours.py
  SKIP_EXISTING=false .venv/bin/python be/scripts/backfill_operating_hours.py  # 전체 재적재

★ 이 스크립트는 코드만 제공. 실행 시점은 다른 backfill 작업 순서에 맞춰 수동 결정.
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
# 요청 간격(초) — 심평원 API 부하 분산 (backfill_public_data.py 패턴 준용)
REQUEST_DELAY_SEC = float(os.environ.get("REQUEST_DELAY_SEC", "0.15"))


def main() -> None:
    hira = HiraAdapter()
    db = DynamoAdapter()

    print(
        "심평원 getDtlInfo2.8 운영시간 강남구 backfill — META·PUBLIC#NONPAY 무손상",
        flush=True,
    )
    raw_hospitals = hira.get_hospitals_by_region(sido_code=SEOUL_SIDO, sigungu_code=GANGNAM_SIGUNGU)
    total = len(raw_hospitals)
    print(f"강남 병원 {total}개 조회. SKIP_EXISTING={SKIP_EXISTING}", flush=True)

    done = skipped = filled = no_data = errors = 0
    t0 = time.time()

    for i, raw in enumerate(raw_hospitals, 1):
        ykiho = raw.get("ykiho")
        if not ykiho:
            continue

        try:
            # SKIP_EXISTING: PUBLIC#DOCTORS 에 operating_hours 가 이미 있으면 건너뜀
            if SKIP_EXISTING:
                existing = db.load_public_doctors(ykiho)
                if existing and existing.get("operating_hours") is not None:
                    skipped += 1
                    done += 1
                    continue

            # getDtlInfo2.8 → OperatingHours (의원급만 데이터 있음)
            oh = hira.get_operating_hours(ykiho)
            time.sleep(REQUEST_DELAY_SEC)

            if oh is None:
                # 종합병원·상급종합 또는 신고 미완 의원 — PUBLIC#DOCTORS 갱신 없이 skip
                no_data += 1
                done += 1
                continue

            # PUBLIC#DOCTORS 에 operating_hours 패치 — put_entity 전체 overwrite 방지 위해
            # load → merge → save 패턴 사용 (PUBLIC#DOCTORS 기존 필드 보존)
            existing_raw = db.get_entity(ykiho, "PUBLIC#DOCTORS")
            if existing_raw is None:
                # PUBLIC#DOCTORS entity 자체가 없으면 최소 빈 dict 로 생성
                # (backfill_public_data.py 가 먼저 실행된다는 전제이나 방어적으로 처리)
                from shared.models import PublicData
                empty_pd = PublicData(
                    license_number=ykiho,
                    specialists=[],
                    registered_devices=[],
                )
                db.save_public_doctors(ykiho, empty_pd, operating_hours=oh)
            else:
                # 기존 PUBLIC#DOCTORS entity 에 operating_hours 만 추가 (나머지 필드 보존)
                from be.adapters.dynamo_adapter import _float_to_decimal
                oh_data = _float_to_decimal(oh.model_dump(mode="json", exclude_none=True))
                db._table.update_item(
                    Key={"hospital_id": ykiho, "entity": "PUBLIC#DOCTORS"},
                    UpdateExpression="SET operating_hours = :oh",
                    ExpressionAttributeValues={":oh": oh_data},
                )

            filled += 1
            done += 1

        except Exception as e:
            errors += 1
            done += 1
            if errors <= 10:
                print(f"  [err] {ykiho[:20]}: {e}", flush=True)

        if i % 100 == 0 or i == total:
            rate = i / max(1e-9, time.time() - t0)
            eta = (total - i) / max(1e-9, rate)
            print(
                f"  {i}/{total} | 적재 {filled} 스킵 {skipped} 데이터없음 {no_data} 오류 {errors} "
                f"| {rate:.1f}/s ETA {eta/60:.1f}분",
                flush=True,
            )

    print(
        f"\n완료: 총 {total} | 운영시간 적재 {filled} 스킵 {skipped} 데이터없음 {no_data} 오류 {errors} "
        f"| {(time.time()-t0)/60:.1f}분",
        flush=True,
    )


if __name__ == "__main__":
    main()
