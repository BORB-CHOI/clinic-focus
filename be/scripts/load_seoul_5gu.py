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

# 공공 데이터(전문의·비급여) 적재 여부 — 키 미승인 상태에서도 graceful degrade
LOAD_PUBLIC_DATA = os.environ.get("LOAD_PUBLIC_DATA", "false").lower() == "true"

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
        public_loaded = 0

        for raw in raw_hospitals:
            try:
                meta = hira.parse_hospital_meta(raw)
                db.save_hospital_meta(meta)
                success += 1
                if meta.contact.website_url:
                    with_url += 1

                # 심평원 전문의·비급여 공공 데이터 적재 (LOAD_PUBLIC_DATA=true 시).
                # 키 미승인(403) 상태에선 빈값이지만 코드 경로 유효 확인용으로도 사용 가능.
                if LOAD_PUBLIC_DATA:
                    try:
                        # 총 의사 수는 per-ykiho API 가 없어 base 목록의 drTotCnt 를 넘긴다
                        # (전 과목 전문의 0명인데 의사 N명 = 일반의 단독 추론 보조).
                        dr_tot = int(raw.get("drTotCnt") or 0) or None
                        public_data = hira.get_public_data(meta.hospital_id, dr_tot_cnt=dr_tot)
                        # 전문의·의료장비 적재 (specialists_by_dept, total_doctors, registered_devices)
                        db.save_public_doctors(meta.hospital_id, public_data)
                        # 비급여 데이터 적재 (nonpay_items)
                        if public_data.nonpay_items:
                            db.save_public_nonpay(meta.hospital_id, public_data.nonpay_items)
                        public_loaded += 1
                    except Exception as pe:
                        pass  # 공공 데이터 실패는 META 적재 성공에 영향 없음

            except Exception as e:
                failed += 1

        public_suffix = f" | 공공데이터: {public_loaded}개" if LOAD_PUBLIC_DATA else ""
        print(f"  ✅ 성공: {success}개 | ❌ 실패: {failed}개 | 🌐 URL: {with_url}개{public_suffix}")

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
