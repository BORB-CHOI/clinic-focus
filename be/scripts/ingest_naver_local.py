"""로컬 PC가 크롤한 네이버 raw JSON → parse → DDB 적재 (파일 다리 EC2 쪽).

crawl_naver_local.py 가 로컬에서 만든 be/data/naver_raw/{hospital_id}.json 들을 읽어
기존 parse_place() 로 정제(작성자 PII 제거, 본문 보존)한 뒤 DDB NAVER#PLACE#REVIEWS 로
적재한다. 네트워크 없음 — 순수 parse + DynamoDB put 뿐(EC2 인스턴스프로파일 인증).

실행: .venv/bin/python be/scripts/ingest_naver_local.py [--raw-dir be/data/naver_raw] [--confirm]
  --confirm 없으면 dry-run (DDB 미적재, 통계만).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from be.adapters.dynamo_adapter import DynamoAdapter  # noqa: E402
from be.adapters.naver_place_adapter import parse_place  # noqa: E402


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="네이버 raw JSON → DDB NAVER#PLACE#REVIEWS 적재")
    ap.add_argument("--raw-dir", default="be/data/naver_raw", help="로컬에서 받은 raw JSON 폴더")
    ap.add_argument("--confirm", action="store_true", help="지정 시 DDB 적재. 미지정=dry-run")
    args = ap.parse_args(argv)

    files = [f for f in os.listdir(args.raw_dir) if f.endswith(".json")] if os.path.isdir(args.raw_dir) else []
    if not files:
        print(f"raw JSON 없음: {args.raw_dir}")
        return

    db = DynamoAdapter() if args.confirm else None
    mode = "CONFIRM (DDB 적재)" if args.confirm else "DRY-RUN (통계만)"
    print(f"{'='*56}\n네이버 raw 적재 — {mode} | {len(files)}개 파일\n{'='*56}")

    matched = with_reviews = saved = no_pid = empty = 0
    total_reviews = 0

    for i, fn in enumerate(files, 1):
        rec = json.load(open(os.path.join(args.raw_dir, fn), encoding="utf-8"))
        hid = rec.get("hospital_id") or fn[:-5]
        pid = rec.get("place_id")
        raw = rec.get("visitor_reviews_raw")
        if not pid:
            no_pid += 1
            continue
        matched += 1
        if not raw or (isinstance(raw, dict) and raw.get("_error")):
            empty += 1
            continue

        parsed = parse_place(raw, str(pid))   # 작성자 PII 제거 + 본문 보존 (기존 검증 로직)
        nrev = len(parsed.get("reviews") or [])
        total_reviews += nrev
        if nrev > 0:
            with_reviews += 1

        if args.confirm:
            db.put_entity(hid, "NAVER#PLACE#REVIEWS", parsed)
            saved += 1

        if i % 100 == 0:
            print(f"  [{i}/{len(files)}] 매칭 {matched} 후기보유 {with_reviews} 저장 {saved}")

    print(f"\n{'='*56}")
    print(f"  파일:            {len(files)}")
    print(f"  place_id 보유:   {matched}  (없음 {no_pid})")
    print(f"  후기 보유:       {with_reviews}  (raw 비었/에러 {empty})")
    print(f"  수집 후기 합:    {total_reviews}")
    if args.confirm:
        print(f"  DDB 적재:        {saved}건 (NAVER#PLACE#REVIEWS)")
    else:
        print(f"  DRY-RUN — --confirm 시 {with_reviews}건 적재 예정")
    print('='*56)


if __name__ == "__main__":
    main()
