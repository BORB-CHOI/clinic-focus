"""네이버 검색 API 테스트."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from be.adapters.naver_map_adapter import NaverMapAdapter

naver = NaverMapAdapter()

print("=== 네이버 검색 API 테스트 ===")
print(f"Client ID: {os.environ.get('NAVER_MAP_CLIENT_ID', '없음')[:5]}...")

# 테스트 1: 큰 병원
print("\n[1] 강남세브란스병원")
result = naver.search_hospital("강남세브란스병원", "서울 강남구")
if result:
    print(f"  이름: {result['title']}")
    print(f"  링크(홈페이지): {result['link']}")
    print(f"  주소: {result['road_address']}")
    print(f"  전화: {result['telephone']}")
else:
    print("  ❌ 검색 실패")

# 테스트 2: 동네 의원
print("\n[2] 무병한의원 성북구")
result2 = naver.search_hospital("무병한의원", "서울 성북구")
if result2:
    print(f"  이름: {result2['title']}")
    print(f"  링크(홈페이지): {result2['link']}")
    print(f"  주소: {result2['road_address']}")
    print(f"  전화: {result2['telephone']}")
else:
    print("  ❌ 검색 실패")

# 테스트 3: 피부과
print("\n[3] 연세피부과 성북구")
result3 = naver.search_hospital("연세피부과", "서울 성북구")
if result3:
    print(f"  이름: {result3['title']}")
    print(f"  링크(홈페이지): {result3['link']}")
    print(f"  주소: {result3['road_address']}")
    print(f"  전화: {result3['telephone']}")
else:
    print("  ❌ 검색 실패")
