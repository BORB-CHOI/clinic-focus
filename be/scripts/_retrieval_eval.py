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
# 기대 focus 또는 기대 진료과 중 하나만 맞아도 정답(약한 정답 weak ground truth).
# 강남 분포(치과 41%·한의원 31%·미용/피부/성형 다수) 반영. 통증·근골격은 한국 임상상
# 정형/재활/마취통증/신경외과/한의원(한방통증)을 모두 정답으로 인정.
_PAIN = {"정형외과", "재활의학과", "마취통증의학과", "신경외과", "한의원"}
QUERY_SET: list[dict] = [
    # === 치과 (강남 최다) ===
    {"q": "임플란트", "focus": ["임플란트"], "spec": {"치과"}},
    {"q": "앞니 임플란트", "focus": ["임플란트", "보철"], "spec": {"치과"}},
    {"q": "치아교정", "focus": ["교정"], "spec": {"치과"}},
    {"q": "투명교정 인비절라인", "focus": ["교정"], "spec": {"치과"}},
    {"q": "라미네이트 앞니", "focus": ["라미네이트", "심미", "보철"], "spec": {"치과"}},
    {"q": "충치 치료", "focus": ["충치", "신경치료"], "spec": {"치과"}},
    {"q": "신경치료 아파요", "focus": ["신경치료", "충치"], "spec": {"치과"}},
    {"q": "사랑니 발치", "focus": ["사랑니", "발치"], "spec": {"치과"}},
    {"q": "잇몸 치료 치주", "focus": ["잇몸", "치주"], "spec": {"치과"}},
    {"q": "스케일링", "focus": ["스케일링", "잇몸", "치주"], "spec": {"치과"}},
    {"q": "틀니 의치", "focus": ["틀니", "보철"], "spec": {"치과"}},
    {"q": "치아미백", "focus": ["미백", "심미"], "spec": {"치과"}},
    {"q": "어린이 소아 치과", "focus": ["소아"], "spec": {"치과"}},
    {"q": "턱관절 통증", "focus": ["턱관절", "구강악안면"], "spec": {"치과"}},
    {"q": "크라운 보철", "focus": ["보철", "크라운"], "spec": {"치과"}},
    # === 피부과 (미용/일반) ===
    {"q": "여드름 흉터", "focus": ["여드름", "흉터"], "spec": {"피부과"}},
    {"q": "기미 색소 레이저", "focus": ["기미", "색소"], "spec": {"피부과"}},
    {"q": "모공 흉터 레이저", "focus": ["모공", "흉터"], "spec": {"피부과"}},
    {"q": "제모 레이저", "focus": ["제모"], "spec": {"피부과", "기타"}},
    {"q": "점 제거", "focus": ["점", "일반 진료", "사마귀"], "spec": {"피부과"}},
    {"q": "사마귀 제거", "focus": ["사마귀", "일반 진료", "아토피·피부질환"], "spec": {"피부과"}},
    {"q": "아토피 피부염", "focus": ["아토피", "일반 진료"], "spec": {"피부과", "한의원"}},
    {"q": "두드러기 알레르기 피부", "focus": ["두드러기", "아토피", "일반 진료"], "spec": {"피부과"}},
    {"q": "미백 피부톤", "focus": ["미백", "피부톤", "기미"], "spec": {"피부과"}},
    {"q": "문신 제거", "focus": ["문신", "제거", "색소"], "spec": {"피부과"}},
    {"q": "발 무좀", "focus": ["무좀", "아토피·피부질환", "일반 진료"], "spec": {"피부과"}},
    # === 미용 시술 (피부과·성형·기타 부티크 다 정답) ===
    {"q": "보톡스 필러", "focus": ["보톡스", "필러"], "spec": {"피부과", "성형외과", "기타"}},
    {"q": "리프팅 탄력", "focus": ["리프팅", "탄력"], "spec": {"피부과", "성형외과", "기타"}},
    {"q": "울쎄라 써마지", "focus": ["리프팅", "탄력"], "spec": {"피부과", "성형외과", "기타"}},
    {"q": "미용 주사 물광", "focus": ["보톡스", "필러", "리프팅", "기미"], "spec": {"피부과", "기타"}},
    # === 성형외과 ===
    {"q": "코성형 매부리코", "focus": ["코성형", "코"], "spec": {"성형외과"}},
    {"q": "쌍커풀 눈성형", "focus": ["눈성형", "눈"], "spec": {"성형외과"}},
    {"q": "가슴성형 확대", "focus": ["가슴성형", "가슴"], "spec": {"성형외과"}},
    {"q": "지방흡입 체형", "focus": ["지방흡입", "체형"], "spec": {"성형외과", "기타"}},
    {"q": "안면윤곽 사각턱", "focus": ["안면윤곽", "윤곽", "양악"], "spec": {"성형외과"}},
    {"q": "양악수술", "focus": ["양악", "안면윤곽", "구강악안면"], "spec": {"성형외과", "치과"}},
    {"q": "눈밑 지방 재배치", "focus": ["눈성형", "눈"], "spec": {"성형외과"}},
    # === 모발/탈모 (기타 부티크 — specialty 게이팅에 가장 취약했던 부류) ===
    {"q": "M자 탈모", "focus": ["모발", "탈모"], "spec": {"피부과", "성형외과", "기타"}},
    {"q": "탈모약 처방", "focus": ["모발", "탈모"], "spec": {"피부과", "기타"}},
    {"q": "모발이식 비절개", "focus": ["모발", "탈모"], "spec": {"기타", "성형외과", "피부과"}},
    {"q": "여성 헤어라인 탈모", "focus": ["모발", "탈모"], "spec": {"기타", "피부과", "성형외과"}},
    # === 한의원 (강남 2위) ===
    {"q": "추나 도수 한방", "focus": ["추나", "도수"], "spec": {"한의원"}},
    {"q": "다이어트 한약", "focus": ["비만", "다이어트", "한약"], "spec": {"한의원"}},
    {"q": "한약 체질 보약", "focus": ["한약", "체질"], "spec": {"한의원"}},
    {"q": "침 약침 치료", "focus": ["침", "약침"], "spec": {"한의원"}},
    {"q": "교통사고 한방 치료", "focus": ["교통사고", "추나", "침"], "spec": {"한의원"}},
    {"q": "불임 난임 한방", "focus": ["불임", "난임", "한약", "체질"], "spec": {"한의원"}},
    {"q": "소아 한방 성장", "focus": ["소아", "성장", "한약"], "spec": {"한의원"}},
    {"q": "비염 한방 치료", "focus": ["비염", "알레르기", "한약"], "spec": {"한의원", "이비인후과"}},
    # === 안과 ===
    {"q": "라식 라섹", "focus": ["시력교정", "라식", "라섹"], "spec": {"안과"}},
    {"q": "스마일 시력교정", "focus": ["시력교정", "라식", "라섹"], "spec": {"안과"}},
    {"q": "백내장 수술", "focus": ["백내장"], "spec": {"안과"}},
    {"q": "노안 교정", "focus": ["노안", "백내장"], "spec": {"안과"}},
    {"q": "녹내장 검사", "focus": ["녹내장"], "spec": {"안과"}},
    {"q": "망막 황반변성", "focus": ["망막"], "spec": {"안과"}},
    {"q": "드림렌즈 소아 근시", "focus": ["드림렌즈", "소아근시", "시력"], "spec": {"안과"}},
    {"q": "안구건조증", "focus": ["안구건조"], "spec": {"안과"}},
    # === 정형/재활/통증/신경외과 (근골격) ===
    {"q": "무릎 관절염 주사", "focus": ["무릎", "관절", "주사", "통증재활", "도수", "체외충격파"], "spec": _PAIN},
    {"q": "어깨 회전근개", "focus": ["어깨", "회전근개", "통증재활", "도수", "주사치료", "체외충격파"], "spec": _PAIN},
    {"q": "허리 디스크 도수치료", "focus": ["척추", "디스크", "도수", "통증재활"], "spec": _PAIN},
    {"q": "목 디스크 거북목", "focus": ["척추", "디스크", "도수", "통증재활"], "spec": _PAIN},
    {"q": "척추관 협착증", "focus": ["척추", "디스크", "통증재활"], "spec": _PAIN},
    {"q": "체외충격파 치료", "focus": ["체외충격파", "통증재활", "도수"], "spec": _PAIN},
    {"q": "발목 인대 손상", "focus": ["발목", "수부·족부", "스포츠손상", "통증재활"], "spec": _PAIN | {"외과"}},
    {"q": "손목 저림", "focus": ["수부", "손", "저림", "통증재활", "침"], "spec": _PAIN | {"신경과", "외과"}},
    {"q": "스포츠 부상 재활", "focus": ["스포츠손상", "통증재활", "도수"], "spec": _PAIN},
    {"q": "도수치료 통증", "focus": ["도수", "통증재활"], "spec": _PAIN},
    # === 이비인후과 ===
    {"q": "비염 치료", "focus": ["비염", "알레르기"], "spec": {"이비인후과", "한의원"}},
    {"q": "축농증 부비동염", "focus": ["축농증", "비염", "코"], "spec": {"이비인후과"}},
    {"q": "코골이 수면무호흡", "focus": ["코골이", "수면", "코·수면호흡"], "spec": {"이비인후과", "기타"}},
    {"q": "이명 귀울림", "focus": ["이명", "청각"], "spec": {"이비인후과"}},
    {"q": "중이염 귀", "focus": ["중이염", "청각", "귀"], "spec": {"이비인후과"}},
    {"q": "어지럼증 이석증", "focus": ["어지럼", "이석", "청각"], "spec": {"이비인후과", "신경과"}},
    {"q": "편도 목 통증", "focus": ["편도", "인후", "목"], "spec": {"이비인후과"}},
    # === 내과 ===
    {"q": "위 내시경", "focus": ["내시경", "위장", "소화기"], "spec": {"내과"}},
    {"q": "대장 내시경 용종", "focus": ["내시경", "대장", "소화기"], "spec": {"내과"}},
    {"q": "당뇨 관리", "focus": ["당뇨", "내분비", "만성질환"], "spec": {"내과"}},
    {"q": "고혈압 진료", "focus": ["고혈압", "순환기", "만성질환"], "spec": {"내과"}},
    {"q": "갑상선 결절", "focus": ["갑상선"], "spec": {"이비인후과", "내과", "외과"}},
    {"q": "역류성 식도염", "focus": ["소화기", "위장", "내시경"], "spec": {"내과"}},
    {"q": "건강검진", "focus": ["검진", "건강검진"], "spec": {"내과", "가정의학과"}},
    # === 정신건강의학과 ===
    {"q": "우울증 상담", "focus": ["우울", "정신"], "spec": {"정신건강의학과"}},
    {"q": "불안 공황장애", "focus": ["불안", "공황", "정신"], "spec": {"정신건강의학과"}},
    {"q": "불면증 수면장애", "focus": ["불면", "수면", "정신"], "spec": {"정신건강의학과", "기타"}},
    {"q": "성인 ADHD", "focus": ["adhd", "정신", "집중"], "spec": {"정신건강의학과"}},
    # === 산부인과/비뇨의학과 ===
    {"q": "산부인과 검진", "focus": ["산부인과", "자궁", "여성"], "spec": {"산부인과"}},
    {"q": "자궁 근종", "focus": ["자궁", "여성"], "spec": {"산부인과"}},
    {"q": "전립선 비뇨기", "focus": ["전립선", "비뇨"], "spec": {"비뇨의학과"}},
    {"q": "요로결석", "focus": ["요로", "결석", "비뇨"], "spec": {"비뇨의학과"}},
    # === 가정의학과/기타 ===
    {"q": "비만 다이어트 클리닉", "focus": ["비만", "다이어트", "체형"], "spec": {"가정의학과", "기타", "내과", "한의원"}},
    {"q": "영양 수액 주사", "focus": ["영양", "수액", "주사"], "spec": {"가정의학과", "내과", "기타"}},
    {"q": "금연 클리닉", "focus": ["금연"], "spec": {"가정의학과", "내과"}},
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
