"""DynamoDB에 저장된 병원 중 홈페이지 URL 없는 병원을 카카오/네이버로 보강."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

import boto3
from be.adapters.kakao_adapter import KakaoAdapter
from be.adapters.dynamo_adapter import DynamoAdapter


def main():
    kakao = KakaoAdapter()
    db = DynamoAdapter()

    print("=" * 60)
    print("홈페이지 URL 보강 (카카오 로컬 검색)")
    print("=" * 60)

    # DynamoDB에서 URL 없는 병원 조회
    dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    table = dynamodb.Table("Hospitals")

    # 전체 스캔 (PoC 규모라 괜찮음)
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

    # 카카오 검색으로 URL 보강
    enriched = 0
    failed = 0

    for i, item in enumerate(no_url, 1):
        name = item.get("name", "")
        location = item.get("location", {})
        address = location.get("address", "")

        kakao_info = kakao.search_hospital(name, address)

        if kakao_info and kakao_info.get("place_url"):
            # DynamoDB 업데이트 — contact.website_url에 카카오맵 URL 저장
            hospital_id = item["hospital_id"]
            table.update_item(
                Key={"hospital_id": hospital_id},
                UpdateExpression="SET contact.website_url = :url",
                ExpressionAttributeValues={":url": kakao_info["place_url"]},
            )
            enriched += 1
            print(f"  [{i}/{len(no_url)}] ✅ {name} → {kakao_info['place_url']}")
        else:
            failed += 1
            if i % 100 == 0:
                print(f"  [{i}/{len(no_url)}] 진행 중... (성공: {enriched}, 실패: {failed})")

        # API 호출 제한 방지 (초당 10회 제한)
        time.sleep(0.15)

    print("\n" + "=" * 60)
    print("URL 보강 완료!")
    print(f"  ✅ 보강 성공: {enriched}개")
    print(f"  ❌ 검색 실패: {failed}개")
    print(f"  📍 총 크롤링 가능 병원: {enriched + 62}개 (기존 62 + 보강 {enriched})")
    print("=" * 60)


if __name__ == "__main__":
    main()
