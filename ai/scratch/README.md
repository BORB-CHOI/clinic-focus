# ai/scratch/ — 임시 작업 폴더 (e2e 검증 후 삭제 예정)

## 목적

[이슈 #23](https://github.com/BORB-CHOI/clinic-focus/issues/23) (BE 위임 — `s3_adapter` boto3 전환 + `crawl_all.py` `TABLE_PREFIX` 패치) 이 머지되기 전, AI 트랙(`kmuproj-10`)이 e2e 결과를 미리 보기 위해 **BE 본체를 안 건드리고** 우회용 사본을 두는 곳.

## 삭제 시점

이슈 #23 머지 → AI 트랙이 본체(`be/adapters/s3_adapter.py`·`be/scripts/crawl_all.py`)로 전환 완료 → **이 폴더 통째 삭제**.

이 폴더의 코드는 어떤 곳에서도 import 하면 안 된다. 검증 스크립트로만 직접 실행.

## 작업 큐

`docs/plans/task-queue.md` Step 6-3a ~ 6-9 항목 참조.

| 파일 | 대응 본체 | 역할 |
|---|---|---|
| `load_dev_subset.py` | (신규) | HIRA 강남구 4과목 ~88개 → `HospitalMeta` → DDB 적재. 이름 키워드 매칭 (HIRA `getHospBasisList` 응답에 진료과목 정보 없음) |
| `crawl_all_ai.py` | `be/scripts/crawl_all.py` | `dynamodb.Table("Hospitals")` 하드코딩만 `TABLE_PREFIX` 적용으로 패치한 사본. 본체 미수정 |
| `classify_one.py` | (신규, 검증용) | 1개 병원으로 `classify_hospital` + `generate_description` 스모크 테스트 |
| `classify_all.py` | (신규) | 크롤 성공 14개 일괄 분류·설명 → DDB Classifications/HospitalDescriptions 저장 |
| `kb_ingest.py` | `ai/__init__.py` 의 `ingest_hospital` (미구현) | DDB → KB DataSource S3 본문·메타 업로드 → `StartIngestionJob` |
| `retrieve_test.py` | `ai/__init__.py` 의 `retrieve_hospital` (미구현) | 하드코딩 4쿼리로 KB Retrieve 검증 |
| `search_one.py` + `search.sh` | (위와 동일) | 인자로 받은 자연어 1건 검색 — 데모·디버깅용 |

## scratch 단계 데이터 흐름 (정본 아님)

> ⚠️ 이 흐름은 이슈 [#23](https://github.com/BORB-CHOI/clinic-focus/issues/23) 머지 전 임시 우회용. 정본 e2e 흐름(BE 본체 통합 후)은 `be/handlers/index_hospital.py` 의 `run_index_pipeline` 참조.

```
1) load_dev_subset.py
   HIRA getHospBasisList (강남구)
     → 이름 키워드 매칭으로 4과목 88개 sampling
     → DDB Hospitals (kmuproj-10-clinic-Hospitals)

2) crawl_all_ai.py
   DDB scan → URL 보유 25개 → httpx 크롤링
     → 로컬 FS data/crawl/{hospital_id}.json (S3Adapter 가 아직 boto3 미전환)
     → 14개 성공 / 11개 JS 렌더링 필요

3) classify_all.py
   for hospital_id in data/crawl/:
     classify_hospital(crawl_data)        ← Bedrock Haiku 4.5 (개인 계정 ap-northeast-2)
     generate_description(...)            ← Bedrock Haiku 4.5
     DDB Classifications + HospitalDescriptions 저장

4) kb_ingest.py
   DDB → 본문 텍스트 + metadata.json 생성
     → S3 kmuproj-02-vector/clinic-focus/prod/{hospital_id}.txt(+.metadata.json)
     → bedrock-agent:StartIngestionJob (KB GTBJ6HLFDK)
     → KB 가 Titan v2 임베딩 + S3 Vectors 인덱스 자동 생성

5) search.sh "자연어 쿼리"
     → bedrock-agent-runtime:Retrieve (LLM 0건, Titan 임베딩만)
     → filter: team_id=clinic-focus (02팀과 KB 공유라 격리 필수)
     → 매칭된 청크 5개 → hospital_id 별 dedupe → 점수순 출력
```

### 정본 흐름과의 차이 (이슈 #23 머지 후 사라짐)

- **2)**: `crawl_all_ai.py` → `be/scripts/crawl_all.py` (TABLE_PREFIX 적용된 버전)
- **2) 저장 경로**: 로컬 FS → `S3Adapter` boto3 (`s3://kmuproj-10-clinic-focus-crawl/crawl/{hospital_id}.json`)
- **3),4)**: 독립 스크립트 → `be/handlers/index_hospital.py:run_index_pipeline` 한 함수가 classify + describe + ingest 통합 호출
- **5)**: 임시 `search.sh` → `ai.retrieve_hospital(query: SearchQuery)` 정식 함수 (`docs/API-BE-AI.md` 명세)

## 본체 `ingest_hospital` 구현 시 주의점 (scratch 검증으로 확인된 사실)

1. **KB 본문은 자르지 말 것** — `vectorIngestionConfiguration: {}` 셋팅이라 KB가 기본 청크 분할(보통 300토큰) 자동 처리. 우리가 1KB·8KB 같은 한도로 자르면 정보 손실. 통째 박고 KB에 맡길 것. (2026-05-26 실측: kb_ingest.py 초안에서 1KB 자르기 했다가 사이트 공통 네비/메뉴만 들어가는 사고)
2. **본문에 자체 사이트 텍스트 필수** — DDB 의 분류·설명만으론 구체 시술명(사마귀·냉동치료기 같은) 매칭 불가. `crawl_data.pages[*].html_text` 가 본문에 반드시 들어가야 함. **page_type 우선순위** (service·about · main · doctors · blog) 로 정렬 권장 (정보 밀도 높은 페이지부터)
3. **HTML 잡음 정제는 BE 이슈 [#13](https://github.com/BORB-CHOI/clinic-focus/issues/13) 의존** — 현재 페이지 텍스트가 사이트 공통 네비/푸터 반복 포함 (페이지마다 첫 500자가 거의 같은 메뉴). 우리 AI 트랙이 임시 정제하면 BE 본체와 충돌. 이슈 #13 머지 후 재-ingest 필요
4. **부정 문장 매칭 함정** — `generate_description` 이 "X 정보 없음"이라고 적은 부정 문장도 임베딩 공간에서 X 쿼리와 매칭됨. 약점·주의 단락은 의도 그대로 노출되지만 점수 1위로 잡혀서 사용자가 혼동할 수 있음. 부정 단락을 별도 필드/메타로 분리 검토 (현재는 무시)
5. **빈 metadata 값 거절** — `primary_focus: []` 같은 빈 리스트는 KB 가 invalid metadata 로 거절. dict 에서 키 자체 제외 필요. `lat`/`lng=None` 도 동일. 자세한 건 [`docs/API-BE-AI.md`](../../docs/API-BE-AI.md) `ingest_hospital` 섹션
6. **데이터 한계 솔직 인정** — 강남 미용 피부과 14개 표본에서 "사마귀" 검색 시 매칭 약한 건 사이트가 안 적어둬서. 사이트가 안 적은 정보는 4시그널(자칭·블로그·후기·Vision)이 풀 자리. 이슈 [#18](https://github.com/BORB-CHOI/clinic-focus/issues/18) 외부 시그널 크롤러가 들어와야 본격 해결
