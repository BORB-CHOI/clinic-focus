"""검색 품질 정량 평가 (retrieval eval) — read-only, LLM 0회.

정답지(아래 QUERY_SET) 각 쿼리를 retrieve_hospital 로 검색하고, 상위 결과가 기대
focus/진료과에 맞는지 채점한다. 신뢰도(신호 합의도)와 별개로 *검색 품질*을 숫자로 본다.

채점(약한 정답 weak ground truth):
- 한 결과가 "정답"인 조건 = 그 병원 DDB 분류의 primary_focus 가 expect_focus 중 하나를
  부분일치(substring)로 포함  OR  standard_specialty 가 expect_specialty 집합에 속함.
- precision@5 = 상위 5 중 정답 비율, MRR = 첫 정답의 역순위(1/rank).
- 두 지표의 매크로 평균이 요약.

기대 라벨은 "이 쿼리에 *어떤 성격의 병원*이 떠야 자연스러운가"의 약한 기준일 뿐,
완벽한 golden 이 아니다. 절대값보다 **수정 전/후 델타**를 보는 용도.

실행: .venv/bin/python be/scripts/_retrieval_eval.py [--k 5] [--limit 10]
주의: 재인제스트/BE 코드 변경 후 데이터가 안정된 상태에서 돌릴 것.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))
os.environ.setdefault("KB_MIN_SCORE", "0.3")

import boto3  # noqa: E402

from ai import retrieve_hospital  # noqa: E402
from shared.models import SearchQuery  # noqa: E402

# 강남 PoC 정답지 — (쿼리, 기대 focus 키워드[부분일치], 기대 진료과 집합)
# 기대 focus 와 기대 진료과는 OR 로 채점(둘 중 하나만 맞아도 정답).
QUERY_SET: list[dict] = [
    # --- 명확한 진료과 쿼리 ---
    {"q": "임플란트", "focus": ["임플란트"], "spec": {"치과"}},
    {"q": "치아교정", "focus": ["교정"], "spec": {"치과"}},
    {"q": "사랑니 발치", "focus": ["사랑니", "발치"], "spec": {"치과"}},
    {"q": "라식 라섹", "focus": ["시력교정", "라식", "라섹"], "spec": {"안과"}},
    {"q": "백내장 수술", "focus": ["백내장"], "spec": {"안과"}},
    {"q": "코성형", "focus": ["코성형", "코"], "spec": {"성형외과"}},
    {"q": "비염 치료", "focus": ["비염", "알레르기"], "spec": {"이비인후과"}},
    # 통증·근골격은 한국 임상상 정형외과·재활·마취통증·신경외과·한의원(한방통증)이 모두 정답.
    {"q": "무릎 관절염 주사", "focus": ["무릎", "관절", "주사", "통증재활", "도수", "체외충격파"],
     "spec": {"정형외과", "재활의학과", "마취통증의학과", "신경외과", "한의원"}},
    {"q": "허리 디스크 도수치료", "focus": ["척추", "디스크", "도수", "통증재활"],
     "spec": {"정형외과", "재활의학과", "마취통증의학과", "신경외과", "한의원"}},
    {"q": "어깨 회전근개", "focus": ["어깨", "회전근개", "통증재활", "도수", "주사치료", "체외충격파"],
     "spec": {"정형외과", "재활의학과", "마취통증의학과", "한의원"}},
    # --- focus 주도 / 기타 부티크 (specialty 하드필터에 가장 취약했던 부류) ---
    {"q": "M자 탈모", "focus": ["모발", "탈모"], "spec": {"피부과", "성형외과"}},
    {"q": "탈모약 처방", "focus": ["모발", "탈모"], "spec": {"피부과"}},
    {"q": "코골이 수면무호흡", "focus": ["코골이", "수면", "코·수면호흡"], "spec": {"이비인후과"}},
    {"q": "보톡스 필러", "focus": ["보톡스", "필러"], "spec": {"피부과", "성형외과"}},
    {"q": "여드름 흉터", "focus": ["여드름", "흉터"], "spec": {"피부과"}},
    {"q": "기미 색소 레이저", "focus": ["기미", "색소"], "spec": {"피부과"}},
    {"q": "지방흡입 체형", "focus": ["지방흡입", "체형"], "spec": {"성형외과"}},
    {"q": "리프팅 탄력", "focus": ["리프팅", "탄력"], "spec": {"피부과", "성형외과"}},
    {"q": "다이어트 한약", "focus": ["비만", "다이어트", "한약"], "spec": {"한의원"}},
    {"q": "추나 도수 한방", "focus": ["추나", "도수"], "spec": {"한의원"}},
    # --- 자연어/모호 ---
    {"q": "발 무좀 피부", "focus": ["무좀", "아토피·피부질환", "일반 진료"], "spec": {"피부과"}},
    {"q": "손목 저림 손 저림", "focus": ["수부", "손", "저림", "통증재활", "침"],
     "spec": {"정형외과", "신경외과", "신경과", "재활의학과", "한의원", "외과"}},
    {"q": "갑상선 결절", "focus": ["갑상선"], "spec": {"이비인후과", "내과", "외과"}},
    {"q": "사마귀 제거", "focus": ["사마귀", "일반 진료", "아토피·피부질환"], "spec": {"피부과"}},
    {"q": "위 내시경", "focus": ["내시경", "위장", "소화기"], "spec": {"내과"}},
    {"q": "우울 불안 상담", "focus": ["우울", "불안", "정신"], "spec": {"정신건강의학과"}},
]


def _focus_specialty(table, hid: str) -> tuple[list[str], str]:
    item = table.get_item(Key={"hospital_id": hid, "entity": "CLASSIFICATION"}).get("Item") or {}
    pf = item.get("primary_focus") or (item.get("classification") or {}).get("primary_focus") or []
    if isinstance(pf, str):
        pf = [pf]
    sp = item.get("standard_specialty") or (item.get("classification") or {}).get("standard_specialty") or "?"
    return [str(x) for x in pf], str(sp)


def _is_hit(pf: list[str], sp: str, expect_focus: list[str], expect_spec: set[str]) -> bool:
    if sp in expect_spec:
        return True
    joined = " ".join(pf)
    return any(ef in joined for ef in expect_focus)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="검색 품질 정량 평가")
    ap.add_argument("--k", type=int, default=5, help="precision@k 의 k")
    ap.add_argument("--limit", type=int, default=10, help="retrieve_hospital limit")
    args = ap.parse_args(argv)

    table = boto3.resource("dynamodb", "us-east-1").Table("kmuproj-10-clinic-Main")

    p_at_k_sum = 0.0
    mrr_sum = 0.0
    n = len(QUERY_SET)
    print(f"{'쿼리':22} P@{args.k}  MRR   상위{args.k} 적중(focus/과)")
    print("-" * 78)
    for case in QUERY_SET:
        res = retrieve_hospital(SearchQuery(query_text=case["q"], sigungu="강남구", limit=args.limit))
        topk = res[: args.k]
        hits = []
        first_rank = 0
        for rank, r in enumerate(topk, 1):
            pf, sp = _focus_specialty(table, r.hospital_id)
            hit = _is_hit(pf, sp, case["focus"], set(case["spec"]))
            hits.append(hit)
            if hit and first_rank == 0:
                first_rank = rank
        p_at_k = sum(hits) / args.k if topk else 0.0
        mrr = (1.0 / first_rank) if first_rank else 0.0
        p_at_k_sum += p_at_k
        mrr_sum += mrr
        mark = "".join("●" if h else "·" for h in hits)
        flag = "" if p_at_k >= 0.6 else ("  ⚠약" if p_at_k > 0 else "  ✗미스")
        print(f"{case['q']:22} {p_at_k:.2f}  {mrr:.2f}  {mark}{flag}")
    print("-" * 78)
    print(f"{'매크로 평균':22} {p_at_k_sum/n:.3f} {mrr_sum/n:.3f}   (쿼리 {n}개, KB_MIN_SCORE={os.environ.get('KB_MIN_SCORE')})")


if __name__ == "__main__":
    main()
