"""기타 재분류 DDB 쓰기 — 저장된 dry-run 결과(_reclassify_result.json) 재사용, Nova 재호출 없음.

수술적 규칙: to ∈ {피부과, 성형외과, 기타} 는 기타 유지(미용 의도-강등이 처리), 그 외 명확
의료과목만 이동. save_classification 이 CLASSIFICATION + META GSI(sigungu_specialty·display_category)
를 함께 갱신. 롤백맵(_reclassify_rollback.json) 저장 + HISTORY 기록으로 되돌릴 수 있게.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from be.adapters.dynamo_adapter import DynamoAdapter  # noqa: E402

KEEP_AS_ETC = {"피부과", "성형외과", "기타"}


def main(apply: bool):
    db = DynamoAdapter()
    data = json.loads((ROOT / "be/scripts/_reclassify_result.json").read_text())
    moves = [d for d in data if d["to"] not in KEEP_AS_ETC]
    print(f"이동 대상(수술적): {len(moves)}개  (apply={apply})", flush=True)

    rollback = {}
    done = 0
    errs = 0
    for d in moves:
        hid = d["hospital_id"]
        new_sp = d["to"]
        try:
            cls = db.load_classification(hid)
            if cls is None:
                print(f"  skip(분류없음): {d['name']}")
                continue
            old_sp = cls.standard_specialty
            if old_sp != "기타":
                # 이미 기타가 아니면(중복 실행 등) 건너뜀 — 멱등
                continue
            rollback[hid] = old_sp
            if apply:
                updated = cls.model_copy(update={
                    "standard_specialty": new_sp,
                    "classifier_version": (cls.classifier_version or "") + "+llm_etc_refine",
                    "classified_at": datetime.now(timezone.utc),
                })
                db.save_classification(updated)
                # HISTORY 기록(raw) — 되돌림 근거
                iso = datetime.now(timezone.utc).isoformat()
                db.put_entity(hid, f"HISTORY#{iso}", {
                    "hospital_id": hid, "changed_at": iso,
                    "field": "standard_specialty", "from": old_sp, "to": new_sp,
                    "reason": "llm_etc_refine", "notes": f"Nova Lite 세부분류 kw={d.get('kw', [])[:6]}",
                })
            done += 1
            if done % 20 == 0:
                print(f"  ...{done}/{len(moves)} ({'적용' if apply else 'dry'})", flush=True)
        except Exception as e:
            errs += 1
            print(f"  ERR {d['name']}: {str(e)[:80]}")

    (ROOT / "be/scripts/_reclassify_rollback.json").write_text(
        json.dumps(rollback, ensure_ascii=False, indent=1))
    print(f"\n{'적용 완료' if apply else 'dry-run'}: {done}건  오류 {errs}  "
          f"| 롤백맵 저장: be/scripts/_reclassify_rollback.json")
    if not apply:
        print("실제 적용: python be/scripts/reclassify_etc_write.py --apply")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
