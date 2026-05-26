# ai/scratch/ — 임시 작업 폴더 (e2e 검증 후 삭제 예정)

## 목적

[이슈 #23](https://github.com/BORB-CHOI/clinic-focus/issues/23) (BE 위임 — `s3_adapter` boto3 전환 + `crawl_all.py` `TABLE_PREFIX` 패치) 이 머지되기 전, AI 트랙(`kmuproj-10`)이 e2e 결과를 미리 보기 위해 **BE 본체를 안 건드리고** 우회용 사본을 두는 곳.

## 삭제 시점

이슈 #23 머지 → AI 트랙이 본체(`be/adapters/s3_adapter.py`·`be/scripts/crawl_all.py`)로 전환 완료 → **이 폴더 통째 삭제**.

이 폴더의 코드는 어떤 곳에서도 import 하면 안 된다. 검증 스크립트로만 직접 실행.

## 작업 큐

`docs/plans/task-queue.md` Step 6-3a 항목 참조.

| 파일 | 대응 본체 | 차이 |
|---|---|---|
| `load_dev_subset.py` | (신규) | HIRA 강남구 4과목 ~85개 → `HospitalMeta` → DDB 적재 |
| `crawl_all_ai.py` | `be/scripts/crawl_all.py` | `dynamodb.Table("Hospitals")` 하드코딩만 `TABLE_PREFIX` 적용으로 패치한 사본. 본체 미수정 |
