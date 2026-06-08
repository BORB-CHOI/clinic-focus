"""심평원 상세(15001699)·비급여(15001700) 활용신청 승인 + 응답 입도 스모크테스트.

키 승인 전후로 두 신규 서비스가 실제로 동작하는지 샘플 ykiho 1개로 확인하는 재검증 도구.
엔드포인트는 2026-06-08 실측으로 확정됨(403=경로 정확·키 미승인 / 404=op만 오류 / 500=경로 오류):
  - 전문의:  MadmDtlInfoService2.8/getDgsbjtInfo2.8  (dgsbjtCdNm + dgsbjtPrSdrCnt)
  - 의료장비: MadmDtlInfoService2.8/getMedOftInfo2.8  (oftCdNm)
  - 비급여:  nonPaymentDamtInfoService/getNonPaymentItemHospDtlList  (npayKorNm + curAmt)
  ※ 총 의사 수는 base getHospBasisList 의 drTotCnt 사용(상세 서비스엔 per-ykiho 의사수 없음).

사용: `.venv/bin/python be/scripts/_verify_hira_detail.py`
판정: 403 → 아직 활용신청 미승인(계정주 발급 대기). 200+JSON → 승인됨, 필드 입도 출력.
"""

from __future__ import annotations

import json
import os
import sys

import httpx

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

KEY = os.environ.get("HIRA_API_KEY", "")
if not KEY:
    print("HIRA_API_KEY 미설정 — 중단")
    sys.exit(1)

BASE = "https://apis.data.go.kr/B551182/hospInfoServicev2"
DETAIL = "https://apis.data.go.kr/B551182/MadmDtlInfoService2.8"
NONPAY = "https://apis.data.go.kr/B551182/nonPaymentDamtInfoService"

client = httpx.Client(timeout=30.0)


def call(url: str, **params) -> httpx.Response:
    return client.get(url, params={"serviceKey": KEY, "_type": "json", **params})


def verdict(label: str, r: httpx.Response) -> None:
    body = r.text
    print(f"\n----- {label}\n  HTTP {r.status_code} | {str(r.url).replace(KEY, '<KEY>')}")
    if r.status_code == 403:
        print("  >>> 403 Forbidden — 활용신청 미승인(키 발급 대기). 경로는 정확함.")
        return
    if not body.lstrip().startswith("{"):
        print(f"  >>> 비정상 응답: {body[:120]!r}")
        return
    data = json.loads(body)
    hdr = data.get("response", {}).get("header", {})
    print(f"  >>> resultCode={hdr.get('resultCode')} resultMsg={hdr.get('resultMsg')}")
    items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
    if isinstance(items, dict):
        items = [items]
    print(f"  >>> 항목 {len(items)}건. 샘플: {json.dumps(items[0], ensure_ascii=False)[:300] if items else '없음'}")


# 1) base 에서 샘플 ykiho 확보 (병원급·의원급)
r = call(f"{BASE}/getHospBasisList", pageNo=1, numOfRows=5, sidoCd="110000", sgguCd="110001")
items = r.json()["response"]["body"]["items"]["item"]
sample = items[0]["ykiho"]
print(f"base OK — 샘플 ykiho: {sample[:24]}... ({items[0].get('yadmNm')})")

# 2) 확정 엔드포인트 검증 (★2.8 — getDtlInfo2.8 은 운영시간이라 의사수 없음, 제외)
verdict("전문의 getDgsbjtInfo2.8", call(f"{DETAIL}/getDgsbjtInfo2.8", ykiho=sample, pageNo=1, numOfRows=100))
verdict("의료장비 getMedOftInfo2.8", call(f"{DETAIL}/getMedOftInfo2.8", ykiho=sample, pageNo=1, numOfRows=50))
verdict("비급여 getNonPaymentItemHospDtlList", call(f"{NONPAY}/getNonPaymentItemHospDtlList", ykiho=sample, pageNo=1, numOfRows=20))

print("\n검증 종료. (403 이면 키 승인 후 재실행)")
