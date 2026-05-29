# 신뢰도 계산 — 시그널 수집 결손 처리 결정 (2026-05-29)

> 결정 노트. **아직 미구현** — "나중에 개발" 대상. Phase C 신뢰도 로직 보정 작업의 명세.
> 상위 컨텍스트: [`task-queue.md`](task-queue.md) Phase C "남은 것".
> 담당 위임 후보: `signal-fusion-engineer` (+ 회귀 테스트 `tdd-guide`).

대상 코드: [`ai/pipeline/classify.py`](../../ai/pipeline/classify.py)
관련 모델: `Confidence`, `SignalContributions` ([`shared/models.py`](../../shared/models.py))

---

## 1. 문제 정의

4 시그널(자칭 25% / Vision 30% / 블로그 20% / 후기 25%)을 합쳐 `confidence.score`(0~100)와
`level`(확실/추정/정보 부족)을 산정한다. 그런데 **"시그널이 없음"과 "시그널이 있는데 주력과 안 맞음"을
같게 취급**해, 다음 두 오작동이 난다.

### 1-1. 결손 시그널이 "반값 기여"를 받는다

`_cross_validate_signals` 의 정렬도 함수 ([classify.py:803](../../ai/pipeline/classify.py#L803)):

```python
def _signal_alignment(norm):
    if top_focus is None or not norm: return 0.0   # 시그널 없음 → 0
    return norm.get(top_focus, 0.0)                 # 있는데 안 맞음 → 0
```

둘 다 `0.0` 을 돌려주므로, 기여도 공식 `weight × (0.5 + 0.5 × align)` 에서 **둘 다 `weight × 0.5`** 의
반값 베이스라인을 받는다. 즉 **데이터가 0건인 블로그 시그널도 "절반은 있는 셈"** 으로 점수에 들어가고,
화면 `SignalContributions` 에 가짜 비율(예: 블로그 21%)이 찍힌다.

### 1-2. 가장 신뢰하는 Vision 이 빠지면 오히려 score 100 "확실"

`_compute_confidence` 의 Vision-None 재정규화 ([classify.py:837](../../ai/pipeline/classify.py#L837))가
비-Vision 기여 합을 **무조건 1.0 으로** 끌어올려(`contrib[k] *= 1/other_sum`), 정렬 페널티를 통째로 지운다.

**실측 (2026-05-29, 내부 헬퍼 직접 호출):**

입력 — 자칭만 `primary_focus=["미용 시술"]`, 블로그·후기 빈 시그널, Vision `None`:

| 경로 | score | level | signals 비율 |
|---|---:|---|---|
| demo (`use_llm=True`, cap 없음) | **100** | **확실** ❌ | self 53 / vision 0 / **blog 21 / reviews 26** (데이터 0건인데) |
| 룰 (`use_llm=False`, cap 70) | 70 | 추정 | self 53 / vision 0 / **blog 21 / reviews 26** (비율 거짓 그대로) |
| 대조군) 같은 입력 + Vision 있음 | 62 | 정보 부족 ✅ | — |

→ Vision 이 **있을 때 62 "정보 부족"** 이던 게 **빠지면 100 "확실"** 로 뒤집힌다(가장 믿는 30% 시그널이
사라졌는데 신뢰도가 올라감). 룰 경로는 `_cap_rule_only_confidence` ([classify.py:879](../../ai/pipeline/classify.py#L879))가
70 으로 덮어 "확실"은 막지만, **비율 거짓(blog 21/reviews 26)은 룰 경로에서도 그대로 노출**된다.

> 직전 커밋 `ea2d9b7`("주력 미식별 시 신뢰도 100 확실 오산정 버그 수정")은
> *focus 후보가 하나도 없는* 경우(`all_focus_candidates` 빈 집합 → 전부 0)만 막았다.
> *자칭 하나라도 focus 를 만들고 나머지가 결손인* 경우는 안 막혀 있다 — 같은 계열의 미처리 잔여.

---

## 2. 왜 "0점 처리"는 답이 아닌가

우리 파이프라인에서 시그널 결손은 대부분 **"병원에 진짜 후기/블로그가 없다"가 아니라 "우리가 아직 안 긁어왔다"** 이다.

- 외부 시그널(카카오/네이버/구글)은 **회색지대라 시연 10개 한정**으로만 수집한다(운영자 결정).
  1만 풀커버 병원은 외부 시그널이 구조적으로 `None` — 이건 *미수집*이지 *부재*가 아니다.
- 결손을 0점으로 깎으면 **신뢰도가 병원의 실체가 아니라 우리 수집 커버리지를 반영**하게 된다.
  자칭 하나만 또렷한 병원을 "증언이 엇갈려 못 믿겠다"가 아니라 "우리가 안 모아서 못 믿겠다"로
  부당하게 깎는 셈.

핵심 통찰: 지금 score 하나에 **성격이 다른 두 축**이 섞여 있다.

| 축 | 의미 | 지금 |
|---|---|---|
| **일치도** (agreement) | 모은 시그널끼리 같은 주력을 가리키는가 | 진짜 "확실/추정"을 가를 축 |
| **근거 두께** (coverage) | 시그널을 몇 종이나 모았는가 | 우리 수집 범위 문제 — score 에 섞이면 안 됨 |

점수가 낮아져야 하는 건 **수집 안 됐을 때가 아니라, 수집된 시그널끼리 엇갈릴 때** 여야 한다.

---

## 3. 결정 — 3원칙

### 원칙 1. 결손 시그널은 점수 계산에서 **제외**(0점도 반값도 아님)

수집된 시그널만 남기고 그들끼리 가중치를 재분배해 **일치도**로 score 를 낸다.
"present" 판정 기준(아래 §5)에 미달하는 시그널은 가중치 풀에서 빠진다.

### 원칙 2. score 천장은 **모은 시그널 종류 수**로 제한 (coverage → level cap)

일치도가 아무리 높아도 근거가 얇으면 "확실"을 못 준다.

- 시그널 **1종**만 present → level 천장 **"추정"** (score 도 상한 cap, 예: 70)
- 시그널 **2종 이상** present 이고 교차 일치 → **"확실"** 가능

이건 현재 룰 경로의 70 cap(`_cap_rule_only_confidence`)을 **모든 경로로 일반화**한 것.
"교차검증 없이는 확실 불가"라는 기존 철학을 결손 일반에 확장한다.

### 원칙 3. 결손 시그널은 화면에 **"수집 안 됨"** 으로 표시 (가짜 비율 금지)

`SignalContributions` 에서 결손 시그널은 0(또는 별도 sentinel)로 두고, FE 는 회색/“미수집”
배지로 차등 렌더. "블로그 21%" 같은 데이터 없는 기여 비율은 노출 금지.

---

## 4. 구체 알고리즘 명세 (의사코드)

> 정책 파라미터(`PRESENT_*`, level cap 기준)는 §5 에서 결정 대기. 아래는 골격.

```python
# (A) present 판정 — 시그널별
def _is_present(signal_type, sig) -> bool:
    if signal_type == "self_claim":
        return bool(sig.primary_focus) or bool(sig.keywords)
    if signal_type == "blog":
        return sig.total_posts > 0            # 또는 keyword_frequency 비지 않음
    if signal_type == "reviews":
        return sig.total_reviews > 0 or bool(sig.keyword_frequency)
    if signal_type == "vision":
        return sig is not None and sig.total_images_analyzed > 0
    return False

# (B) 가중치 재분배 — present 시그널만 남기고 합 1.0 로 정규화
present = {k for k in WEIGHTS if _is_present(k, signals[k])}
if not present:
    return Confidence(score=0, level="정보 부족", signals=ZERO)   # 진짜 아무것도 없음
w = {k: _WEIGHTS[k] for k in present}
norm = sum(w.values())
w = {k: v / norm for k, v in w.items()}      # present 끼리 합 1.0

# (C) 일치도 점수 — present 시그널의 top_focus 지지 비율만 가중합
#     ※ 1-1 의 0.5 베이스라인 제거. align 0 이면 그대로 0 기여(결손이 아니라 "엇갈림"이라서)
score_raw = sum(w[k] * _signal_alignment(norm_votes[k]) for k in present)
score = round(score_raw * 100)               # 0~100

# (D) coverage 기반 level 천장
n_present = len(present)
if n_present <= 1:
    score = min(score, LEVEL1_CAP)           # 예: 70 — "확실" 불가
    level = "추정" if score >= LOW else "정보 부족"
else:
    level = "확실" if score >= HIGH else "추정" if score >= LOW else "정보 부족"

# (E) SignalContributions — 결손은 0(또는 None), present 는 일치 기여 비율
contributions = {k: int(round(w[k] * _signal_alignment(...) / score_raw * 100))
                 if k in present and score_raw > 0 else 0
                 for k in _WEIGHTS}
```

핵심 변경점:
1. **§1-1 의 `0.5 + 0.5*align` 베이스라인 제거.** present 시그널도 안 맞으면 0 기여 → "엇갈림"이
   정직하게 점수를 깎는다. (단 이러면 부분일치 가산 곡선이 바뀌므로 §5-3 회귀 검증 필요.)
2. **§1-2 의 Vision-None 무조건 1.0 재정규화 제거.** (B)의 present 기반 재분배가 이를 대체.
3. `_cap_rule_only_confidence` 의 70 cap 은 **(D)의 n_present≤1 천장**에 흡수 — `use_llm` 분기 대신
   "근거 종류 수"가 cap 의 진짜 기준이 됨. (`use_llm=False` 도 외부 후기 2종이 들어오면 "확실"
   후보가 될 수 있게 되는데, 이게 의도인지 §5-2 에서 결정.)

---

## 5. 미결정 파라미터 (개발 착수 전 사용자 확정)

### 5-1. "확실" 최소 시그널 종류 수
- **2종**(자칭+후기만 일치해도 확실) vs **3종**(자칭+블로그+후기 또는 +Vision).
- 권고: **2종** (현 수집 현실상 Vision/블로그가 자주 비어 3종은 너무 빡빡).

### 5-2. 룰 경로(`use_llm=False`)도 "확실" 허용?
- 현재는 LLM·Vision 없으면 무조건 70 cap. 새 설계는 "근거 종류 수" 기준이라,
  룰 경로라도 **외부 후기(카카오 strength + 구글)** 2종이 자칭과 일치하면 "확실"이 될 수 있음.
- 결정 필요: (a) 기존 유지(룰 = 무조건 ≤70) vs (b) 근거 종류 수 기준으로 통일.
- 권고: **(b)** — `use_llm` 은 "텍스트 추출 품질"이지 "교차검증 종류 수"가 아니므로.

### 5-3. present 인데 엇갈리는 시그널의 감점 강도
- §4 (C)에서 0.5 베이스라인을 없애면 부분일치 점수가 전반적으로 낮아짐.
  완전 제거 대신 약한 베이스라인(예: 0.2)을 둘지 결정.
- 권고: **완전 제거(0)** 후 시연 10개 실측으로 LOW/HIGH 임계 재조정.

### 5-4. LEVEL1_CAP / LOW / HIGH 값
- 현재: HIGH=95, LOW=70 (`CONFIDENCE_THRESHOLD_*`, env override 가능). LEVEL1_CAP 신설(예: 70).
- 시연 10개 분포 보고 미세조정.

---

## 6. 영향 범위 / 회귀 위험

| 영역 | 영향 |
|---|---|
| `classify.py` | `_cross_validate_signals` 기여도 공식 · `_compute_confidence` 재정규화 · `_cap_rule_only_confidence` 흡수 |
| `shared/models.py` | `SignalContributions` 결손 표현(0 유지 vs `int|None` 도입) — None 이면 BE/FE/OpenAPI 타입 동기화 필요 |
| BE `_hospital_card` / `/hospitals/{id}` | confidence 그대로 패스스루라 코드 변경 없음. 단 표시 의미가 바뀜 |
| FE 4시그널 시각화 (Phase E) | "수집 안 됨" 배지 렌더 분기 추가 |
| 테스트 | `ai/tests/test_classify_rule.py` 기존 신뢰도 단언 다수 재작성 필요 |

회귀 위험 큼 — **score 분포 자체가 바뀐다.** 기존 분류 결과(DDB CLASSIFICATION) 재산정이
필요한지(재분류 배치) 별도 판단.

---

## 7. 검증 케이스 (구현 시 테스트로 박을 것)

| # | 입력 | 기대 score/level | 기대 signals |
|---|---|---|---|
| 1 | 자칭만 present, "미용" 일치 | ≤70, **추정** (1종 cap) | self 100 / 나머지 0 |
| 2 | 자칭+블로그+후기 모두 "척추" 일치 | 높음, **확실** | 3종 비율 |
| 3 | 자칭 "미용" / 블로그·후기 "탈모" (엇갈림) | **낮음** (수집은 됐으나 불일치) | present 끼리 비율 |
| 4 | Vision 결손 + 자칭만 일치 | 케이스 1과 동일(100 "확실" 안 나와야) | vision 0 |
| 5 | 전 시그널 결손 | score 0, **정보 부족** | 전부 0 |
| 6 | 자칭+후기 2종 일치 (룰 경로) | §5-2 결정 따라 "확실" 가부 | — |

---

## 8. 한 줄 요약

> 결손 시그널은 **점수에서 빼고**(0점·반값 아님), **근거 종류 수로 등급 천장을 제한**하며,
> 화면엔 **"수집 안 됨"** 으로 정직하게 표시한다. "확실"은 여러 시그널이 실제로 교차 일치할
> 때만, 수집이 덜 된 병원은 부당하게 깎이지 않으면서 "근거가 얇다"가 등급에 드러나게 한다.
