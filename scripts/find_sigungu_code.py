"""성북구 시군구 코드 찾기 — 심평원 API에서 서울 전체 조회 후 성북구 필터."""
import os
import sys

# .env 로드
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from be.adapters.hira_adapter import HiraAdapter

hira = HiraAdapter()

# 시군구 코드 없이 서울 전체 조회 (첫 페이지만)
hospitals = hira.get_hospitals_by_region(sido_code="110000", sigungu_code="")

# 주소에서 구 이름 추출해서 분포 확인
from collections import Counter
gu_counter = Counter()
for h in hospitals:
    addr = h.get("addr", "")
    # "서울특별시 성북구 ..." 에서 구 이름 추출
    parts = addr.split()
    if len(parts) >= 2:
        gu_counter[parts[1]] += 1

print("서울시 구별 병원 수:")
print("-" * 40)
for gu, count in gu_counter.most_common():
    print(f"  {gu}: {count}")

# 성북구 병원 확인
print(f"\n\n성북구 병원 예시:")
for h in hospitals:
    if "성북구" in h.get("addr", ""):
        print(f"  {h.get('yadmNm')} - {h.get('addr')}")
        break

# sgguCdNm 필드 확인
print(f"\n\nsgguCdNm 필드 값 분포:")
sggu_counter = Counter()
for h in hospitals:
    sggu_counter[h.get("sgguCdNm", "")] += 1
for sggu, count in sggu_counter.most_common(10):
    print(f"  {sggu}: {count}")

# sgguCd 필드 확인 (코드값)
print(f"\n\nsgguCd 코드 매핑:")
sggu_code_map = {}
for h in hospitals:
    name = h.get("sgguCdNm", "")
    code = h.get("sgguCd", "")
    if name and code and name not in sggu_code_map:
        sggu_code_map[name] = code
for name, code in sorted(sggu_code_map.items()):
    marker = " ← 이거!" if "성북" in name else ""
    print(f"  {name}: {code}{marker}")
