"""네이버 검색 API로 병원 홈페이지 URL 보강.

카카오와 달리 네이버 지역 검색은 'link' 필드에 병원 홈페이지 URL을 직접 제공.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

import boto3

from be.adapters.naver_map_adapter import NaverMapAdapter
from be.adapters.dynamo_adapter import DynamoAdapter


def main():
    naver = NaverMapAdapter()
    db = DynamoAdapter()

    print("=" * 60)
    print("홈페이지 URL 보강 (네이버 검색 API)")
    print("=" * 60)

    # DynamoDB에서 URL 없는 병원 조회
    dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    table = dynamodb.Table("Hospitals")

    all_items = []
    resp = table.scan()
    all_items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        all_items.extend(resp.get("Items", []))

    # URL 없는 병원 필터
    no_url = []
    for item in all_items:
        contact = item.get("contact", {})
        url = contact.get("website_url")
        if not url:
            no_url.append(item)

    print(f"  전체 병원: {len(all_items)}개")
    print(f"  URL 없는 병원: {len(no_url)}개")
    print("-" * 60)

    enriched = 0
    failed = 0

    for i, item in enumerate(no_url, 1):
        name = item.get("name", "")
        location = item.get("location", {})
        address = location.get("address", "")

        # 네이버 검색 — link 필드에 홈페이지 URL 있음
        naver_info = naver.search_hospital(name, address)

        if naver_info and naver_info.get("link"):
            link = naver_info["link"]
            # 실제 홈페이지 URL인지 확인 (네이버 블로그/카페 제외)
            if "blog.naver" in link or "cafe.naver" in link:
                failed += 1
                continue

            hospital_id = item["hospital_id"]
            table.update_item(
                Key={"hospital_id": hospital_id},
                UpdateExpression="SET contact.website_url = :url",
                ExpressionAttributeValues={":url": link},
            )
            enriched += 1
            print(f"  [{i}/{len(no_url)}] ✅ {name} → {link}")
        else:
            failed += 1
            if i % 100 == 0:
                print(f"  [{i}/{len(no_url)}] 진행 중... (성공: {enriched}, 실패: {failed})")

        # 네이버 API 호출 제한 (초당 10회)
        time.sleep(0.12)

    print("\n" + "=" * 60)
    print("URL 보강 완료!")
    print(f"  ✅ 보강 성공: {enriched}개")
    print(f"  ❌ 검색 실패/블로그: {failed}개")
    print("=" * 60)


if __name__ == "__main__":
    main()
