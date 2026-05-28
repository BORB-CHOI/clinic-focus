"""카카오 후기 (`tab/reviews/kakaomap/{id}`) probe.

실행: .venv/bin/python ai/scratch/kakao-place-probe-2026-05-28/probe_reviews.py

Endpoint: GET https://place-api.map.kakao.com/places/tab/reviews/kakaomap/{place_id}
Params: order=RECOMMENDED&only_photo_review=false
- 단발 GET. 헤더 셋만 맞으면 200.
- 응답에 score_set (총 리뷰 수·평균 평점·강점 카운트), strength_description (강점 라벨 dict — 가격·전문성 등), reviews[] (후기 본문 raw).
- 네이버 visitorReviews 의 `themes`·`votedKeyword` 빈 배열 문제와 달리 카카오는 자체 강점 집계를 카테고리 무관 노출.

⚠️ robots.txt + 약관 자동화 금지. 의료법 §56③ — raw 본문은 DDB 저장·임베딩만, 화면 노출은 키워드 빈도만.
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

REVIEWS_URL = "https://place-api.map.kakao.com/places/tab/reviews/kakaomap/{pid}"

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
    out = {
        "place_id": place_id,
        "ok": False,
        "review_count": None,
        "average_score": None,
        "strength_top": [],
        "items_len": 0,
        "first_item_keys": [],
        "first_body_excerpt": None,
        "error": None,
    }
    params = {"order": "RECOMMENDED", "only_photo_review": "false"}
    try:
        r = httpx.get(
            REVIEWS_URL.format(pid=place_id),
            params=params,
            headers=make_headers(place_id),
            timeout=15.0,
        )
        if r.status_code != 200:
            out["error"] = f"http {r.status_code}"
            return out
        data = r.json()
        out["ok"] = True
        ss = data.get("score_set") or {}
        out["review_count"] = ss.get("review_count")
        out["average_score"] = ss.get("average_score")
        strengths = ss.get("strength_counts") or []
        labels = {d["id"]: d.get("name") for d in (data.get("strength_description") or [])}
        out["strength_top"] = [
            {"name": labels.get(s["id"], str(s["id"])), "count": s["count"]}
            for s in strengths[:5]
        ]
        items = data.get("reviews") or data.get("items") or data.get("list") or []
        out["items_len"] = len(items)
        if items:
            out["first_item_keys"] = sorted(list(items[0].keys()))
            body = items[0].get("contents") or items[0].get("body") or items[0].get("content")
            out["first_body_excerpt"] = (body or "")[:150]
        SAMPLES.mkdir(parents=True, exist_ok=True)
        (SAMPLES / f"reviews_{place_id}.json").write_text(
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
