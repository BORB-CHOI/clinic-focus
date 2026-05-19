"""심평원 API 연동 테스트 — 성북구 병원 목록 조회."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from be.scripts._utils import load_env
load_env()

api_key = os.environ.get("HIRA_API_KEY", "")
if not api_key:
    print("ERROR: .env 파일에 HIRA_API_KEY를 설정해주세요.")
    print("  .env 파일 내용: HIRA_API_KEY=발급받은키")
    sys.exit(1)

from be.adapters.hira_adapter import HiraAdapter
from shared.region_codes import SEOUL_SIDO_CODE, SEOUL_SIGUNGU_CODES

hira = HiraAdapter()

print("=" * 50)
print("심평원 API 연동 테스트 — 성북구 병원 목록")
print("=" * 50)

hospitals = hira.get_hospitals_by_region(
    sido_code=SEOUL_SIDO_CODE,
    sigungu_code=SEOUL_SIGUNGU_CODES["성북구"],
)

print(f"\n성북구 전체 병원 수: {len(hospitals)}")
print(f"\n상위 10개:")
print("-" * 50)

for i, h in enumerate(hospitals[:10], 1):
    name = h.get("yadmNm", "")
    addr = h.get("addr", "")
    specialty = h.get("dgsbjtCdNm", "")
    url = h.get("hospUrl", "")
    print(f"{i:2d}. {name}")
    print(f"    주소: {addr}")
    print(f"    진료과목: {specialty}")
    print(f"    홈페이지: {url or '없음'}")
    print()

with_url = [h for h in hospitals if h.get("hospUrl", "")]
print(f"\n홈페이지 URL 있는 병원: {len(with_url)} / {len(hospitals)}")
print("(이 병원들만 크롤링 대상)")
