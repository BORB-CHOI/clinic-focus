"""서울 5개 구 병원 데이터 심평원 → DynamoDB 적재.

PoC 목표: 서울 5개 구 약 1만 병원.
시군구 코드 참고: https://www.data.go.kr
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from be.adapters.hira_adapter import HiraAdapter
from be.adapters.dynamo_adapter import DynamoAdapter

# 서울 5개 구 시군구 코드
SEOUL_SIDO_CODE = "110000"
TARGET_SIGUNGU = {
    "성북구": "110017",
    "강남구": "110001",
    "마포구": "110014",
    "서초구": "110018",
    "송파구": "110020",
}


def main():
    hira = HiraAdapter()
    db = DynamoAdapter()

    print("=" * 60)
    print("서울 5개 구 병원 데이터 적재")
    print("=" * 60)

    total_success = 0
    total_failed = 0
    total_with_url = 0

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

        for raw in raw_hospitals:
            try:
                meta = hira.parse_hospital_meta(raw)
                db.save_hospital_meta(meta)
                success += 1
                if meta.contact.website_url:
                    with_url += 1
            except Exception as e:
                failed += 1

        print(f"  ✅ 성공: {success}개 | ❌ 실패: {failed}개 | 🌐 URL: {with_url}개")

        total_success += success
        total_failed += failed
        total_with_url += with_url

    print("\n" + "=" * 60)
    print("전체 적재 완료!")
    print(f"  ✅ 총 성공: {total_success}개")
    print(f"  ❌ 총 실패: {total_failed}개")
    print(f"  🌐 홈페이지 URL 있음: {total_with_url}개")
    print("=" * 60)


if __name__ == "__main__":
    main()
