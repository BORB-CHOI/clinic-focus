"""심평원 API에서 병원 목록 가져와서 DynamoDB에 적재하는 스크립트."""

import os
import sys

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from be.adapters.hira_adapter import HiraAdapter
from be.adapters.dynamo_adapter import DynamoAdapter


def main():
    hira = HiraAdapter()
    db = DynamoAdapter()

    sido_code = os.environ.get("SIDO_CODE", "110000")  # 서울
    sigungu_code = os.environ.get("SIGUNGU_CODE", "110012")  # 성북구

    print("=" * 60)
    print(f"심평원 API → DynamoDB 적재")
    print(f"시도: {sido_code}, 시군구: {sigungu_code}")
    print("=" * 60)

    # 1. 심평원에서 병원 목록 조회
    print("\n심평원 API 조회 중...")
    raw_hospitals = hira.get_hospitals_by_region(
        sido_code=sido_code,
        sigungu_code=sigungu_code,
    )
    print(f"  조회된 병원 수: {len(raw_hospitals)}개")

    # 2. DynamoDB에 적재
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

            if i % 50 == 0:
                print(f"  [{i}/{len(raw_hospitals)}] 적재 중...")

        except Exception as e:
            failed += 1
            print(f"  ❌ 실패: {raw.get('yadmNm', '?')} — {e}")

    print("\n" + "=" * 60)
    print("적재 완료!")
    print(f"  ✅ 성공: {success}개")
    print(f"  ❌ 실패: {failed}개")
    print(f"  🌐 홈페이지 URL 있음: {with_url}개")
    print(f"  📍 크롤링 대상 (URL 있는 병원): {with_url}개")
    print("=" * 60)


if __name__ == "__main__":
    main()
