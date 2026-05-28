"""카카오 상세 홈 (`panel3`) probe.

실행: .venv/bin/python ai/scratch/kakao-place-probe-2026-05-28/probe_panel3.py

Endpoint: GET https://place-api.map.kakao.com/places/panel3/{place_id}
- 단발 GET. 헤더 셋만 맞으면 200.
- 응답 = `medical.{emergency_center, hira, medical_info}` + basicInfo + facilityInfo 류.
- 의료법 §56③ 회피 측면: HIRA·응급의료 공공 데이터 메타라 화면 노출 가능.

⚠️ robots.txt + 약관 자동화 금지.
"""

import json
from pathlib import Path

import httpx

PLACE_IDS = [
    "8094954",    # 춘원당한의원 (사용자 캡처)
    "27388604",   # 자생한방병원 강남
    "202729757",  # 더서울병원 성북
    "544191051",  # 위담한방병원 강남
]

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

PANEL3_URL = "https://place-api.map.kakao.com/places/panel3/{pid}"

SAMPLES = Path(__file__).parent / "samples"


def make_headers(place_id: str) -> dict:
    return {
        "User-Agent": UA,
        "Referer": f"https://place.map.kakao.com/{place_id}",
        "Origin": "https://place.map.kakao.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "pf": "web",
    }


def run_one(place_id: str) -> dict:
    out = {"place_id": place_id, "ok": False, "top_keys": [], "medical_keys": [], "error": None}
    try:
        r = httpx.get(PANEL3_URL.format(pid=place_id), headers=make_headers(place_id), timeout=15.0)
        if r.status_code != 200:
            out["error"] = f"http {r.status_code}"
            return out
        data = r.json()
        out["ok"] = True
        out["top_keys"] = sorted(list(data.keys()))[:20]
        med = data.get("medical") or {}
        out["medical_keys"] = sorted(list(med.keys()))
        SAMPLES.mkdir(parents=True, exist_ok=True)
        (SAMPLES / f"panel3_{place_id}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2)
        )
    except Exception as exc:
        out["error"] = repr(exc)
    return out


def main() -> None:
    for pid in PLACE_IDS:
        print(json.dumps(run_one(pid), ensure_ascii=False))


if __name__ == "__main__":
    main()
