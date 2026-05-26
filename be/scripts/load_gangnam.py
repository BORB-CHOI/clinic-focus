"""강남구 병원 데이터 심평원 → DynamoDB 적재.

PoC 목표: 강남구 병원 집중 분석.
시군구 코드 참고: https://www.data.go.kr
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from be.adapters.hira_adapter import HiraAdapter
from be.adapters.dynamo_adapter import DynamoAdapter
from shared.region_codes import SEOUL_SIDO_CODE, SEOUL_SIGUNGU_CODES

TARGET_SIGUNGU = {"강남구": SEOUL_SIGUNGU_CODES["강남구"]}


def main():
    hira = HiraAdapter()
    db = DynamoAdapter()

    print("=" * 60)
    print("강남구 병원 데이터 적재")
    print("=" * 60)

    for gu_name, sigungu_code in TARGET_SIGUNGU.items():
        print(f"\n[{gu_name}] 심평원 API 조회 중...")

        raw_hospitals = hira.get_hospitals_by_region(
            sido_code=SEOUL_SIDO_CODE,
            sigungu_code=sigungu_code,
        )
        print(f"  조회: {len(raw_hospitals)}개")

        success = 0
        failed = 0
        with_url = 0

        for i, raw in enumerate(raw_hospitals, 1):
            try:
                meta = hira.parse_hospital_meta(raw)
                db.save_hospital_meta(meta)
                success += 1
                if meta.contact.website_url:
                    with_url += 1
            except Exception as e:
                failed += 1
                print(f"  ❌ 실패: {raw.get('yadmNm', '?')} — {e}")

            if i % 100 == 0:
                print(f"  [{i}/{len(raw_hospitals)}] 적재 중...")

        print(f"\n  ✅ 성공: {success}개 | ❌ 실패: {failed}개 | 🌐 URL: {with_url}개")

    print("\n" + "=" * 60)
    print("적재 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
