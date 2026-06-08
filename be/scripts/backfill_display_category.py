"""META 계층 카테고리 키 백필 — display_category + primary_focus 보강.

배경: 계층형 둘러보기(L1=display_category, '기타' 해체 / L2=primary_focus)를 META 스캔
1회로 처리하려고 두 키를 META 에 denormalize 한다. save_classification 은 이제 분류 시
자동으로 채우지만, **이미 분류된 기존 병원**은 비어 있으므로 1회 백필한다.

실행: .venv/bin/python be/scripts/backfill_display_category.py [--sigungu 강남구] [--limit N] [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from be.adapters.dynamo_adapter import DynamoAdapter  # noqa: E402
from shared.etc_category import display_specialty  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="display_category 백필")
    ap.add_argument("--sigungu", default="강남구")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    db = DynamoAdapter()
    metas = db.list_hospitals_by_sigungu(args.sigungu)
    if args.limit:
        metas = metas[: args.limit]
    print(f"대상: {args.sigungu} {len(metas)}곳 (dry_run={args.dry_run})")
    print("-" * 56)

    patched = skipped = 0
    import collections
    l1_dist: collections.Counter = collections.Counter()
    for i, meta in enumerate(metas, 1):
        cls = db.load_classification(meta.hospital_id)
        if not cls:
            skipped += 1  # 분류 전 병원 — 둘러보기 미노출
            continue
        dc = display_specialty(cls.standard_specialty, cls.primary_focus)
        l1_dist[dc] += 1
        if not args.dry_run:
            db.patch_meta_categories(meta.hospital_id, cls.standard_specialty, cls.primary_focus)
        patched += 1
        if i % 400 == 0:
            print(f"  [{i}/{len(metas)}] … {patched} 패치")

    print("-" * 56)
    print(f"✅ 패치 {patched}곳 · ⏭️ 분류 전 {skipped}곳")
    print("L1(display_category) 분포 상위 15:")
    for k, v in l1_dist.most_common(15):
        print(f"  {k:14} {v}")


if __name__ == "__main__":
    main()
