"""FastAPI 서버 API 테스트 — DynamoDB에서 병원 데이터 조회 확인."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

import httpx

BASE_URL = "http://localhost:8000"


def main():
    client = httpx.Client(timeout=10.0)

    print("=" * 60)
    print("FastAPI 서버 API 테스트")
    print("=" * 60)

    # 1. Health check
    print("\n[1] GET /health")
    try:
        resp = client.get(f"{BASE_URL}/health")
        print(f"  상태: {resp.status_code}")
        print(f"  응답: {resp.json()}")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        print("  → 서버가 실행 중인지 확인하세요: uvicorn be.handlers.api:app --host 0.0.0.0 --port 8000")
        return

    # 2. DynamoDB에서 병원 ID 하나 가져오기
    print("\n[2] DynamoDB에서 병원 ID 조회...")
    import boto3
    dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    table = dynamodb.Table("Hospitals")
    scan_resp = table.scan(Limit=1)
    items = scan_resp.get("Items", [])

    if not items:
        print("  ❌ DynamoDB에 데이터가 없습니다.")
        return

    hospital_id = items[0]["hospital_id"]
    hospital_name = items[0]["name"]
    print(f"  테스트 대상: {hospital_name} ({hospital_id})")

    # 3. GET /api/hospitals/{id}
    print(f"\n[3] GET /api/hospitals/{hospital_id}")
    try:
        resp = client.get(f"{BASE_URL}/api/hospitals/{hospital_id}")
        print(f"  상태: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            # 주요 필드만 출력
            meta = data.get("meta", {})
            print(f"  병원명: {meta.get('name', 'N/A')}")
            print(f"  주소: {meta.get('location', {}).get('address', 'N/A')}")
            print(f"  전화: {meta.get('contact', {}).get('phone', 'N/A')}")
            print(f"  AI 설명: {data.get('ai_description', '아직 없음')}")
            print(f"  분류: {data.get('classification', '아직 없음')}")
        else:
            print(f"  응답: {resp.text[:200]}")
    except Exception as e:
        print(f"  ❌ 실패: {e}")

    # 4. GET /api/hospitals/없는ID (404 테스트)
    print(f"\n[4] GET /api/hospitals/nonexistent_id (404 테스트)")
    try:
        resp = client.get(f"{BASE_URL}/api/hospitals/nonexistent_id")
        print(f"  상태: {resp.status_code}")
        print(f"  응답: {resp.json()}")
    except Exception as e:
        print(f"  ❌ 실패: {e}")

    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
