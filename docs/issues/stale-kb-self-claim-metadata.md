# 이슈 — KB self_claim 청크의 stale standard_specialty (검색 정밀도 오염)

**상태**: 진단·정량 완료 → **사용자 승인(2026-06-01) → 수정 진행 중**. prune 코드 적용 후 강남
재분류 재실행으로 처리(재실행 중 stale self_claim 자동 삭제 + 메타 갱신 + 재인제스트). 최초
시도한 *수동 대량삭제*는 auto-mode 분류기가 거부했고 **실제 삭제는 일어나지 않았다**(파일 실존 확인).
승인 후 안전한 경로(파이프라인 재실행 + prune)로 전환.
**발견 경위**: "모빈치류 모발의원이 왜 검색에 안 뜨나" 추적 → specialty 하드필터 발견(→ 커밋 `3e644f0`
`[추론,기타]` in-필터로 해소) → 그 검증 중 specialty 메타 자체가 일부 stale함을 발견.

## 증상

`process_query`가 피부과를 추론하는 쿼리("사마귀" 등)에서, **피부과가 아닌 병원(성형외과·한의원·산부인과)이
상위에 끼어든다.** 예: "사마귀" → 리얼리성형외과 #1, 프린세스산부인과 #2 (둘 다 DDB 분류는 성형/산부인과).

## 근본 원인 (증거로 확정)

`run_classification`이 URL 오매칭 병원(`site_mentions_hospital`=False, 크롤 사이트에 병원명이 없음 =
엉뚱한/공유 도메인)의 **자칭 시그널을 빈 사이트로 처리**한다([be/scripts/run_classification.py:88](../../be/scripts/run_classification.py#L88)).
그러면 `build_signal_chunks`가 self_claim 청크를 만들지 않고, `ingest_hospital`은 **현재 있는 청크(reviews 등)만
S3에 쓴다**. 문제: **옛 self_claim.txt + .metadata.json(PR#39 이전 텍스트추론 시절, 62% 피부과 오분류) 이
S3에서 삭제되지 않고 잔존** → KB가 계속 인덱싱 → stale 피부과 메타로 specialty 필터를 통과.

**증거**:
- 모아트의원: `self_claim.txt` LastModified=**06:26**(재인제스트 20:24 이전 = 옛 파일), `reviews.txt`=20:14(갱신).
  `site_mentions_hospital`=False. DDB 분류=기타, KB 사이드카=피부과.
- 리얼리성형외과: 동일 패턴(self_claim 06:26 / reviews 20:15 / mentions=False / DDB=성형, KB=피부과).
- 대조군 압구정리더스피부과(정상): self_claim.txt=20:11(갱신), mentions=True.

## 정량 (강남 3134, KB 사이드카 vs DDB 분류 전수 비교)

- self_claim 사이드카 보유 1755곳 중 **불일치 189곳(10.8%)**, 거의 전부 `X→KB:피부과` (기타 65·성형외과 42·
  한의원 35·외과 6·산부인과 5…).
- 불일치 189곳 중 **182곳이 `site_mentions`=False**(엉뚱사이트 self_claim) → self_claim 삭제 대상.
- 7곳만 `site_mentions`=True(유효 사이트인데 메타만 stale, 다른 경로) → 사이드카 메타 재기록 대상.

## 수정안 (2부, 사용자 승인 필요)

**A. 일회성 정리** (공유 S3 삭제 — 승인 필요):
- 182곳의 `self_claim.txt` + `self_claim.txt.metadata.json` 삭제(엉뚱사이트라 garbage, reviews로 검색 유지).
- 7곳의 self_claim 사이드카 `standard_specialty`를 현재 DDB 분류로 재기록.
- KB ingestion job 1회 트리거(삭제·갱신 반영). 비-LLM(Titan 임베딩만).
- 삭제 목록은 사전에 `be/data/stale_self_claim_deleted.json`로 기록(되돌림 근거).

**B. 재발 방지** (코드):
- `ingest_hospital`에 prune 옵션 — 호출 시 `signal_chunks`에 없는 신호 타입의 S3 파일(.txt + 사이드카)을
  삭제. `run_classification`이 자칭을 비웠을 때 옛 self_claim이 잔존하지 않게.
- 주의: 부분 ingest 호출이 다른 신호를 지우지 않도록 `prune_absent=True` 명시 플래그로(기본 False).

## 영향도

- 커밋 `3e644f0`의 `[추론,기타]` 필터와 **독립**. 그 수정은 유효하며 이 이슈로 약화되지 않음.
- 본 stale 메타는 piece-by-piece 정밀도 문제(피부과류 쿼리에 옛 오분류 병원이 낀다)지, 모발의원 노출
  문제(=3e644f0로 해소)와 별개.
- "사마귀" 등 피부과 추론 쿼리의 상위 정밀도를 개선. 데모 품질 ↑.
