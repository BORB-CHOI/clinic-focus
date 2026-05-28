# AWS 환경 세팅 — 팀 온보딩 가이드

> clinic-focus 의 EC2·Bedrock·KB·DDB·S3 환경을 처음부터 따라잡기 위한 단계별 가이드.
> 2026-05-24 최비성이 실제 진행한 과정을 기준으로 작성, 2026-05-26 KB ingest·DDB·S3 통과 반영.
> EC2 가동 후의 서비스 띄우기·systemd·SSH는 [`../../deploy/README.md`](../../deploy/README.md) 참조.

---

## 이 문서가 다루는 범위

✅ **다룸**: 로컬 VSCode → EC2 SSH 접속 / 자격증명 확인 / Bedrock 모델 가용성 확인 / boto3 설치 / 강사 제공 KB 확인 / Titan v2 임베딩 hello-world / 개인 계정 Sonnet 4.6 Vision 연결 + 실측 응답 카탈로그 / DDB 7테이블 수동 생성 / S3 자체 버킷

✅ **2026-05-25~26 추가 통과**: KB DataSource S3 권한 부여 후 더미·실데이터 ingest 성공 / 자연어 검색 e2e 4쿼리 통과 / Bedrock Haiku 4.5 도 개인 계정 ap-northeast-2로 라우팅 변경

❌ **안 다룸**: 서비스 띄우기·systemd 등록은 [`../../deploy/README.md`](../../deploy/README.md). V2 sprint 큐는 [`../plans/task-queue.md`](../plans/task-queue.md).

---

## 사전 조건 (Prerequisites)

- 강사가 발급한 **EC2 인스턴스 정보** — 퍼블릭 IP, SSH 키 파일(`.pem`), 사용자명
  - Amazon Linux 2023: `ec2-user`
  - Ubuntu: `ubuntu`
- 로컬 PC에 **VSCode 설치** (Windows / macOS / Linux 모두 가능)
- 강사가 EC2 인스턴스 프로파일에 부착해둔 IAM Role
  - 본 프로젝트 기준: `SafeInstanceProfile-kmuproj-10` → Role `SafeRole-kmuproj-10` (지원 계정 `730335373015`)

> ⚠️ **로컬 PC에서 지원 계정 자원을 직접 호출할 수 없다.** 강사 계정 정책상 IAM Role만 발급되고 Access Key를 받을 수 없기 때문. 코드 실행은 **무조건 EC2에서**.

---

## Step 0 — VSCode Remote-SSH로 EC2 접속

### 0-1. 로컬 VSCode에 Remote-SSH 확장 설치

VSCode 확장 패널 (`Cmd/Ctrl+Shift+X`) → "Remote - SSH" 검색 → **Microsoft 공식** 확장 설치.

### 0-2. SSH 키 권한 설정 (로컬)

다운받은 `.pem` 파일은 권한이 헐거우면 SSH가 거부한다.

```bash
# macOS / Linux
chmod 400 ~/.ssh/your-key.pem

# Windows (PowerShell)
icacls .\your-key.pem /inheritance:r /grant:r "$($env:USERNAME):(R)"
```

### 0-3. `~/.ssh/config`에 호스트 등록 (로컬)

```ssh-config
Host clinic-focus-ec2
    HostName <ec2-public-ip>
    User ec2-user
    IdentityFile ~/.ssh/<key>.pem
```

> 호스트명(`clinic-focus-ec2`)은 자유 — VSCode 접속 시 이걸로 골라준다.

### 0-4. VSCode로 접속

1. `F1` 또는 `Cmd/Ctrl+Shift+P` → `Remote-SSH: Connect to Host`
2. 등록한 호스트(`clinic-focus-ec2`) 선택
3. 새 VSCode 창이 열리고, **좌하단에 `SSH: clinic-focus-ec2`** 표시되면 성공
4. 첫 접속 시 fingerprint 확인 프롬프트 → `Continue`

### 0-5. EC2 위에 레포 클론

VSCode 터미널 (`Ctrl+`` `) 열고:

```bash
cd ~
git clone https://github.com/BORB-CHOI/clinic-focus.git
cd clinic-focus
```

> 첫 clone 시 GitHub 자격증명을 묻는다. 두 가지 방법:
> - **gh CLI** (권장): `sudo dnf install -y gh && gh auth login` → 웹 브라우저 토큰 흐름
> - **HTTPS + PAT**: Username에 GitHub 아이디, Password에 [Personal Access Token](https://github.com/settings/tokens) 입력
>
> 자격증명은 once-only — 한 번 인증하면 `git credential` 캐시에 저장됨.

### 0-6. (선택) Claude Code 확장을 원격에 설치

로컬 VSCode 확장 패널에서 Claude Code 항목 → **"Install on SSH: clinic-focus-ec2"** 버튼.
CLI(`npm i -g @anthropic-ai/claude-code`)는 확장만 쓸 거면 불필요.

---

## Step 1 — 자격증명·자원 가용성 확인

EC2 터미널에서 다음 명령을 차례로 실행. 모두 EC2 인스턴스 프로파일이 자동 인증하므로 `aws configure` 불필요.

### 1-1. Caller identity 확인

```bash
aws sts get-caller-identity
```

**기대 출력:**

```json
{
    "UserId": "AROA...:i-0b...",
    "Account": "730335373015",
    "Arn": "arn:aws:sts::730335373015:assumed-role/SafeRole-kmuproj-10/i-..."
}
```

- `Account`: 지원 계정 `730335373015`이어야 함
- `Arn`: `assumed-role/SafeRole-kmuproj-10/<인스턴스ID>` 형식

> ⚠️ `Account`가 다르거나 `Arn`이 IAM User 형식(`user/`)이면 강사에게 문의. 강사 발급 EC2가 맞다면 항상 인스턴스 프로파일 형식이어야 한다.

### 1-2. Bedrock 모델 가용성 확인

```bash
# Titan v2 임베딩 + Haiku + Nova 가용성
aws bedrock list-foundation-models \
  --region us-east-1 \
  --query "modelSummaries[?contains(modelId, 'titan-embed') || contains(modelId, 'haiku') || contains(modelId, 'nova')].modelId" \
  --output table
```

**기대 출력에 다음이 포함:**
- `amazon.titan-embed-text-v2:0` ← 임베딩 모델
- `anthropic.claude-haiku-4-5-20251001-v1:0` ← 트랙 B LLM
- `amazon.nova-lite-v1:0` / `amazon.nova-pro-v1:0` 등 Nova 라인업

```bash
# Claude 4.x 가용성 (Sonnet 4.5 등)
aws bedrock list-foundation-models \
  --region us-east-1 \
  --query "modelSummaries[?contains(modelId, 'claude-sonnet-4') || contains(modelId, 'claude-haiku-4') || contains(modelId, 'claude-opus-4')].[modelId,modelLifecycle.status]" \
  --output table
```

> `list-foundation-models`에 보인다고 해서 **호출 권한이 있다는 보장은 아니다**. 실제 invoke 테스트는 Step 2에서.

### 1-3. boto3 설치

```bash
# 설치 여부 확인
python3 -c "import boto3; print('boto3', boto3.__version__)" 2>&1 || echo "boto3 not installed"

# 미설치 시
pip3 install --user boto3 --upgrade
```

> `--user` 플래그를 쓰는 이유: 시스템 Python에 sudo 없이 설치 가능. 본 EC2는 `sudo pip` 권한이 없을 수 있음.

설치 확인:

```bash
python3 -c "import boto3; print('boto3', boto3.__version__)"
# 기대: boto3 1.43.x 이상
```

### 1-4. 강사 제공 Bedrock Knowledge Base 확인

clinic-focus는 **벡터 검색을 Bedrock KB 경유로 한다** (S3 Vectors 직접 호출 ❌). 강사가 미리 만들어둔 KB를 사용.

```bash
# KB 목록
aws bedrock-agent list-knowledge-bases --region us-east-1
```

**우리 팀 KB:** `kmuproj-team-03` (ID `GTBJ6HLFDK`)

```bash
# KB 상세 — Titan v2 + S3 Vectors storage 확인
aws bedrock-agent get-knowledge-base \
  --knowledge-base-id GTBJ6HLFDK \
  --region us-east-1
```

**기대 출력 핵심 필드:**

```json
{
  "knowledgeBase": {
    "name": "kmuproj-team-03",
    "status": "ACTIVE",
    "knowledgeBaseConfiguration": {
      "vectorKnowledgeBaseConfiguration": {
        "embeddingModelArn": "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
      }
    },
    "storageConfiguration": {
      "type": "S3_VECTORS",
      "s3VectorsConfiguration": {
        "indexArn": "arn:aws:s3vectors:us-east-1:730335373015:bucket/bedrock-knowledge-base-1tvot3/index/bedrock-knowledge-base-default-index"
      }
    }
  }
}
```

→ **임베딩 모델: Titan v2**, **storage: S3 Vectors 버킷 `bedrock-knowledge-base-1tvot3`**

```bash
# DataSource 확인
aws bedrock-agent list-data-sources \
  --knowledge-base-id GTBJ6HLFDK \
  --region us-east-1
```

**우리 팀 DataSource:** `main-datasource` (ID `PLC6QYALDU`)

```bash
# Retrieve API 권한 확인 (빈 결과여도 호출 자체가 성공하면 OK)
aws bedrock-agent-runtime retrieve \
  --knowledge-base-id GTBJ6HLFDK \
  --retrieval-query '{"text":"테스트"}' \
  --region us-east-1
```

**기대 출력:** `{"retrievalResults": [], "guardrailAction": null}` (또는 결과 배열)
- 빈 배열은 정상 — 아직 데이터 적재 안 됨
- `AccessDeniedException` 나오면 강사에게 문의

---

## 자주 마주치는 문제 (이번에 실제로 겪은 것들)

### Q1. `aws s3vectors list-vector-buckets` → AccessDeniedException

```
User: arn:aws:sts::730335373015:assumed-role/SafeRole-kmuproj-10/...
is not authorized to perform: s3vectors:ListVectorBuckets
```

**원인:** `SafeRole-kmuproj-10`에 `s3vectors:*` 권한이 없음.

**해결:** **권한 요청 불필요.** clinic-focus는 S3 Vectors 직접 호출 대신 **Bedrock KB 경유**로 결정. KB Retrieve API는 권한이 이미 있음 (1-4 확인).

### Q2. `pip3 list | grep boto3` → 빈 출력 / `pip3` permission error

**원인:** 시스템 Python에 boto3 미설치 + sudo 권한 없음.

**해결:** `--user` 플래그.
```bash
pip3 install --user boto3 --upgrade
```

### Q3. `git clone` 시 GitHub 자격증명을 묻는데 모름

**해결 옵션 (택1):**

1. **gh CLI** (권장):
   ```bash
   sudo dnf install -y gh
   gh auth login   # → GitHub.com → HTTPS → 웹 브라우저 토큰 흐름
   ```
2. **PAT 직접 입력**: Username = GitHub 아이디 / Password = [Personal Access Token](https://github.com/settings/tokens)
3. **SSH remote**: SSH 키 생성 후 GitHub Settings → SSH keys에 공개키 등록, remote URL을 `git@github.com:...`로 변경

### Q4. `.pem` 파일 권한 에러

```
WARNING: UNPROTECTED PRIVATE KEY FILE!
```

**해결:**
```bash
chmod 400 ~/.ssh/your-key.pem
```

### Q5. Sonnet 4.5가 지원 계정에서도 보임 — 트랙 C 개인 계정 분리 필요?

`bedrock list-foundation-models`에 `anthropic.claude-sonnet-4-5-20250929-v1:0`이 ACTIVE로 표시되지만, **list에 보인다고 invoke 권한이 있는 건 아니다**. 실제 호출 테스트(Step 2/5)에서 확인 전까지는 `task-queue.md` 원안대로 **Sonnet = 개인 계정, Haiku/Nova = 지원 계정** 유지.

---

## Step 1 완료 체크리스트

- [ ] VSCode Remote-SSH로 EC2 접속됨 (좌하단 `SSH: clinic-focus-ec2` 표시)
- [ ] `cd ~/clinic-focus` 작동 (레포 클론됨)
- [ ] `aws sts get-caller-identity` → Account `730335373015`, Role `SafeRole-kmuproj-10`
- [ ] `aws bedrock list-foundation-models` → Titan v2 + Haiku 4.5 + Nova 가용
- [ ] `python3 -c "import boto3; print(boto3.__version__)"` → 1.43+ 출력
- [ ] `aws bedrock-agent get-knowledge-base --knowledge-base-id GTBJ6HLFDK` → ACTIVE 확인
- [ ] `aws bedrock-agent-runtime retrieve --knowledge-base-id GTBJ6HLFDK --retrieval-query '{"text":"테스트"}'` → 정상 응답 (빈 배열 OK)

전부 ✅면 Step 2(Titan v2 임베딩 hello-world)로 진행 가능.

---

## Step 2 — Titan v2 임베딩 hello-world

> 강사 제공 KB가 내부에서 호출하는 임베딩 모델(`amazon.titan-embed-text-v2:0`)을 직접 한 번 두드려보는 단계. KB Retrieve(Step 3)에 들어가기 전 (a) 출력 차원 (b) 재현성 (c) 의료 도메인 의미 유사도가 어느 정도인지 감을 잡는 게 목적.

### 2-1. 실행

EC2 터미널에서 그대로 실행 (별도 스크립트 파일 없이 heredoc).

```bash
python3 - <<'PY'
import json
import math
import boto3

MODEL_ID = "amazon.titan-embed-text-v2:0"
REGION = "us-east-1"

client = boto3.client("bedrock-runtime", region_name=REGION)

def embed(text: str) -> list[float]:
    resp = client.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({"inputText": text, "dimensions": 1024, "normalize": True}),
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(resp["body"].read())["embedding"]

def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb)

# (1) 1024 dim 확인
ko = "강남에서 사마귀 잘 보는 피부과를 찾고 있어"
en = "Looking for a dermatology clinic in Gangnam that treats warts well"
vec_ko = embed(ko)
vec_en = embed(en)
print(f"[1] dim(KO)={len(vec_ko)}  dim(EN)={len(vec_en)}")
print(f"    KO head: {vec_ko[:4]}")
print(f"    EN head: {vec_en[:4]}")

# (2) 재현성
vec_ko_again = embed(ko)
identical = vec_ko == vec_ko_again
max_delta = max(abs(a - b) for a, b in zip(vec_ko, vec_ko_again))
print(f"[2] repeatable: identical={identical}  max|delta|={max_delta:.2e}")

# (3) 의미 유사도 — 사마귀 치료 vs 심상성 우췌 냉동요법
pair_a = "사마귀 치료"
pair_b = "심상성 우췌 냉동요법"
negative = "임플란트 보험 적용 치과"
va = embed(pair_a)
vb = embed(pair_b)
vneg = embed(negative)
print(f"[3] cos('{pair_a}', '{pair_b}')           = {cosine(va, vb):.4f}")
print(f"    cos('{pair_a}', '{negative}') (대조군) = {cosine(va, vneg):.4f}")
print(f"    cos(KO, EN, 같은 의도)               = {cosine(vec_ko, vec_en):.4f}")
PY
```

### 2-2. 실제 출력 (2026-05-24 EC2 `i-0b6142523ec5b5383`)

```
[1] dim(KO)=1024  dim(EN)=1024
    KO head: [-0.07367467880249023, -0.01503063179552555, 0.03014872781932354, -0.008742183446884155]
    EN head: [-0.08316284418106079, 0.057086776942014694, 0.010893149301409721, 0.018127767369151115]
[2] repeatable: identical=True  max|delta|=0.00e+00
[3] cos('사마귀 치료', '심상성 우췌 냉동요법')           = 0.2507
    cos('사마귀 치료', '임플란트 보험 적용 치과') (대조군) = 0.1937
    cos(KO, EN, 같은 의도)               = 0.3273
```

### 2-3. 통과 기준

| 항목 | 기대 | 실제 |
|---|---|---|
| 출력 차원 | 1024 (KO·EN 모두) | ✅ 1024 / 1024 |
| 재현성 | 동일 입력 → 동일 벡터 (`max|Δ|≈0`) | ✅ 비트 단위 동일 |
| 의미 유사도 | 의료 동의어 쌍 > 무관 도메인 대조군 | ✅ 0.2507 > 0.1937 |

### 2-4. 해석 메모 — Step 3 진입 전 알아둘 것

- **재현성이 비트 단위 동일.** `normalize=True`로 호출했고 두 번 호출 결과의 `max|Δ|`가 정확히 0 — 같은 텍스트는 항상 같은 벡터가 나온다. 이건 **사업화 시 hash diff 전략의 전제**가 된다 ([`task-queue.md` PR #6 `feat/be/hash-diff-foundation`](../plans/task-queue.md) 참조). 본문이 안 바뀌었으면 임베딩도 안 바뀌므로, 병원 파일 단위 SHA-256만 비교하면 KB 재ingestion이 필요한지 판단 가능.
- **의료 동의어 유사도 마진이 좁다.** `사마귀 치료` ↔ `심상성 우췌 냉동요법`(같은 질환의 학명+치료법)의 cos가 0.2507, 무관 도메인(`임플란트 보험 적용 치과`) 대조군이 0.1937 — 갭이 0.06뿐. Titan v2가 한국어 의학 학명에 약하다는 신호. **Step 3 KB Retrieve에서 top-k가 의도대로 안 나올 가능성**이 있어, 대응책 두 가지:
  - (A) 트랙 A 룰 기반에서 **동의어 사전**(`사마귀 ↔ 우췌 ↔ verruca`)을 채워 KB ingest 전 본문에 주입
  - (B) Step 4 metadata 스키마에 `aliases: list[string]`을 두고 진료과목별 동의어를 메타로 함께 적재
- **KO↔EN 동일 의도 cos = 0.3273.** 다국어 일정 수준은 되지만 폭이 좁아 자연어 검색 UI는 한국어 입력 가정.

### 2-5. 자주 마주치는 문제

**Q. `AccessDeniedException` — `bedrock:InvokeModel` on `titan-embed-text-v2:0`**

- 원인: 지원 계정에서 Titan v2 model access가 활성화 안 됨 (강사 발급 EC2면 보통 활성화돼 있음)
- 해결: 강사에게 모델 활성화 요청. 콘솔 Bedrock → Model access에서 켜는 작업

**Q. `ValidationException` — `dimensions` 또는 `normalize` 미지원**

- 원인: boto3 버전이 낮으면 새 파라미터 안 받음
- 해결: `pip3 install --user boto3 --upgrade` → 1.43+ 확인

**Q. 동일 입력인데 `identical=False` 나옴**

- 원인: `normalize=False`로 호출했거나 모델 버전이 다름
- 해결: `normalize=True` + `MODEL_ID = "amazon.titan-embed-text-v2:0"` 확인

### 2-6. Step 2 완료 체크리스트

- [ ] 위 스크립트 실행 성공 (3개 출력 블록 전부 나옴)
- [ ] dim = 1024 확인
- [ ] `identical=True` 확인
- [ ] 의료 동의어 cos > 대조군 cos 확인 (마진은 작아도 됨)

전부 ✅면 Step 3(Bedrock KB Retrieve 왕복)로 진행 가능.

---

## Step 3·4 — KB Retrieve 왕복 + DataSource 적재 ✅ 통과 (2026-05-25~26)

**2026-05-25 강사 권한 부여**: `kmuproj-02-vector` 버킷에 `kmuproj-02`·`kmuproj-10`·`kmuproj-11` Role 권한 부여 (Put/Get/List/Delete). 단 *"누가 올렸는지 추적 불가"* + *"Delete 권한 사고 주의"*. → prefix 분리(`clinic-focus/prod/`, `clinic-focus/probe/`) + 운영 코드 Delete 호출 금지 + metadata `team_id` 필수 규약 박음.

**2026-05-26 통과 사실**: 14개 병원 본문 + metadata.json 14쌍 업로드 → `StartIngestionJob` `numberOfDocumentsFailed: 0` → 자연어 검색 4쿼리 통과 (PR [#25](https://github.com/BORB-CHOI/clinic-focus/pull/25) scratch 우회로 — 제거됨). 본체는 [`ai/search/kb_store.py`](../../ai/search/kb_store.py) `ingest_hospital`·`retrieve_hospital` 로 마이그레이션 완료.

### 핵심 함정 (실측으로 확인됨, 본체 구현 시 반영 필수)

자세한 건 [`../API-BE-AI.md` `ingest_hospital` 섹션](../API-BE-AI.md). 요약:

1. **`metadataAttributes`는 단순 dict, list-form 거절** — `[{"key": "...", "value": {"type": "STRING", "value": "..."}}]` 같은 list 포맷 거절. `{"hospital_id": "...", "team_id": "clinic-focus", ...}` 단순 dict만.
2. **빈 list·None 값 거절** — `primary_focus: []`, `lat: None` 같은 빈 값은 KB가 invalid metadata로 거절. dict에서 키 자체 제외.
3. **`team_id="clinic-focus"` 필수** — KB·DataSource를 02팀과 공유하므로 Retrieve 시 `filter = {equals: {key: "team_id", value: "clinic-focus"}}`로 격리.
4. **본문 자르지 말 것** — `vectorIngestionConfiguration: {}` 셋팅이라 KB가 기본 청크(300토큰) 자동 처리. 우리가 1KB·8KB로 자르면 메뉴·푸터만 들어가는 사고.
5. **자체 사이트 텍스트 필수** — DDB 분류·설명만으론 구체 시술명(사마귀·냉동치료기) 매칭 불가. `crawl_data.pages[*].html_text`가 본문에 들어가야 함. page_type 우선순위(service·about · main · doctors · blog).
6. **부정 문장 매칭** — `generate_description`이 "X 정보 없음"이라 적어도 임베딩 공간에서 X 쿼리와 매칭. 약점 단락이 점수 1위로 잡혀 사용자 혼동 가능 — 부정 단락 분리 검토(현재는 무시).

### Delete 권한 운영 대응

- 본문 갱신·hash diff → PutObject 덮어쓰기로 해결 (Delete 불필요, KB가 변경된 파일 청크 자동 재생성)
- 폐업 병원 → soft-delete: 본문을 폐업 안내로 덮어쓰고 `metadata.status="closed"`로 retrieve 필터 제외
- 잘못 올린 테스트 파일 → 강사에게 청소 부탁. `clinic-focus/probe/` vs `clinic-focus/prod/` prefix로 영역 분리

---

## Step 5 — 개인 계정 Sonnet 4.6 Vision 연결 (서울 리전, Global cross-region inference)

> 트랙 C(이미지 분석 시연)는 지원 계정 KB 권한과 무관해서 Step 3·4 권한 대기 중에도 진행 가능. **개인 AWS 계정**에서 Bedrock Sonnet 4.6만 호출하는 최소 권한 IAM User를 만들어 EC2에 named profile로 등록. 2026-05-24 검증 완료.

> ⚠️ **사용자가 직접 콘솔에서 해야 하는 부분(5-1~5-3)이 포함됨.** Claude가 대신 못 함. 5-4 (EC2 credentials 등록)부터는 Claude가 같이 진행.

### 핵심 결론 먼저 (이 섹션의 모든 결정사항)

| 항목 | 값 | 근거 |
|---|---|---|
| 리전 | `ap-northeast-2` (서울) | 사용자 기존 자원이 한국이고 서울에서 Sonnet 4.6 호출 가능 — 데이터 거주성/관리 일관성 |
| 모델 | `global.anthropic.claude-sonnet-4-6` (**Global cross-region inference profile**) | Sonnet 4.6은 foundation-model 직접 호출 불가, inference profile 필수. APAC profile 없고 Global만 제공 |
| IAM | 별도 User + 인라인 정책 (관리자 키 재사용 ❌) | 최소 권한 원칙. 키 유출 시 피해를 Sonnet 호출 비용으로만 한정 |
| 정책 ARN | **3개 모두 필요** (inference-profile + regional FM + global FM) | Global inference profile은 권한 평가 시 3개 ARN 전부 검사 ([AWS 공식](https://docs.aws.amazon.com/bedrock/latest/userguide/global-cross-region-inference.html)) |

### 5-1. 개인 계정 콘솔에서 Bedrock model access 활성화

1. 개인 AWS 계정 콘솔 로그인 → 우측 상단 리전 드롭다운 **`Asia Pacific (Seoul) ap-northeast-2`** 선택
2. Amazon Bedrock → 좌측 **Model access** → **Modify model access**
3. **Anthropic Claude Sonnet 4.6** 체크 → Submit
4. 상태가 **Access granted**로 변경 (보통 즉시, 가끔 몇 분 소요)

> **만약 콘솔 model catalog에 Sonnet 4.6이 안 보이면** 4.5로 진행 (정책·MODEL_ID의 `sonnet-4-6` → `sonnet-4-5-20250929-v1:0`로 치환). 본 가이드는 4.6 기준.

### 5-2. IAM User 생성 + 인라인 정책

> 본 가이드의 User 이름은 예시로 `clinic-focus-ai`. 학원·조직 명명규칙이 있으면 그대로 따르면 됨 (예: `26-1-aws-real`). 이름은 무관, **관리자 키 재사용은 금지**.

1. IAM → Users → **Create user**
2. User name: `clinic-focus-ai` (또는 조직 규칙대로)
3. Permissions options → **Attach policies directly** → 일단 아무것도 선택 안 함 → Next → Create user
4. 생성된 User 클릭 → **Permissions** 탭 → **Add permissions** → **Create inline policy**
5. JSON 탭에서 다음 정책 붙여넣기 (`<ACCOUNT_ID>`는 본인 계정 ID로 치환):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvokeSonnet46GlobalProfile",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:ap-northeast-2:<ACCOUNT_ID>:inference-profile/global.anthropic.claude-sonnet-4-6",
        "arn:aws:bedrock:ap-northeast-2::foundation-model/anthropic.claude-sonnet-4-6",
        "arn:aws:bedrock:::foundation-model/anthropic.claude-sonnet-4-6"
      ]
    }
  ]
}
```

6. Policy name: `BedrockSonnet46InvokeOnly` → Create policy

> ⭐ **3개 ARN 모두 필요한 이유**: Global cross-region inference profile은 IAM 권한 평가 시 (a) inference profile 자체 + (b) 요청 리전 FM + (c) 실제 실행되는 다른 리전의 **region/account 비어있는 global FM ARN** 3가지를 모두 검사합니다. 셋 중 하나만 빠져도 `AccessDeniedException` 발생. **3번째 `arn:aws:bedrock:::foundation-model/...`은 콜론 사이가 비어있는 게 정상** — 오타 아님.
>
> 출처: [AWS Bedrock 공식 — Global cross-Region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/global-cross-region-inference.html), [Identity-based policy examples](https://docs.aws.amazon.com/bedrock/latest/userguide/security_iam_id-based-policy-examples.html)

> **왜 `AmazonBedrockFullAccess` 안 쓰나**: 이 키는 EC2 파일 시스템에 저장되고 git에 잘못 올라갈 위험이 0이 아님. 키 유출 시 피해를 Sonnet 4.6 호출 비용으로만 한정.

> **왜 디스커버리 권한(`ListFoundationModels` 등) 안 넣나**: 정책에 박아둔 ARN이 실제로 존재하는지 검증할 때 한 번만 필요. 검증 끝나면 빼는 게 최소 권한 원칙. 정확한 모델 ID는 본 가이드에 이미 명시돼 있어 디스커버리 불필요.

### 5-3. Access Key 발급

1. `clinic-focus-ai` (또는 본인 User) → **Security credentials** 탭 → **Create access key**
2. Use case: **Command Line Interface (CLI)** 선택 → 체크박스 동의 → Next
3. Description: `clinic-focus EC2 Vision` → Create access key
4. **Access key ID**와 **Secret access key** 둘 다 확인 — Secret은 이 화면 닫으면 다시 못 봄
5. Download .csv 또는 안전한 곳에 임시 보관 (5-4에서 즉시 사용 후 폐기)

> **선택 안전망 — Budgets 알람**: 키 유출 대비 청구 알람을 함께 거는 게 정석. 개인 계정에 다른 IAM User가 이미 Bedrock을 쓰고 있으면 Cost Category·Service 필터로는 정확한 분리 불가 (AWS Cost는 IAM User 차원을 기본 제공 안 함). 정확히 분리하려면 IAM User에 Tag(예: `Project=clinic-focus`) 부착 + Cost Allocation Tag 활성화 후 **24시간 대기** → Tag-filtered budget. 임시 안전망으로 전체 계정 budget 1개($현재 사용량 + α)를 먼저 깔아두면 24시간 공백을 메울 수 있음. PoC 며칠짜리면 최소 권한 정책으로도 1차 방어 충분.

### 5-4. EC2 `~/.aws/credentials`에 named profile 등록

EC2 SSH 터미널에서:

```bash
mkdir -p ~/.aws && chmod 700 ~/.aws

# 기존 파일 있으면 백업
[ -f ~/.aws/credentials ] && cp ~/.aws/credentials ~/.aws/credentials.bak.$(date +%s)

# named profile 추가 (append). Access Key / Secret은 5-3에서 받은 값으로 치환
cat >> ~/.aws/credentials <<EOF

[personal]
aws_access_key_id = <AKIA...>
aws_secret_access_key = <...>
region = ap-northeast-2
EOF

chmod 600 ~/.aws/credentials
```

검증:

```bash
aws --profile personal sts get-caller-identity
```

기대 출력:

```json
{
    "UserId": "AIDA...",
    "Account": "<개인 계정 ID>",
    "Arn": "arn:aws:iam::<개인 계정 ID>:user/<본인 User 이름>"
}
```

확인 포인트:
- `Account`가 **개인 계정 ID** (지원 계정 `730335373015`이면 잘못 쓴 것)
- `Arn`의 User 이름이 5-2에서 만든 User와 일치
- **다른 User 이름이 나오면** 같은 계정의 다른 IAM User Access Key가 잘못 등록됐다는 뜻 → 5-3에서 받은 정확한 키로 재등록

> ⚠️ **Secret Access Key는 절대 git에 올리지 말 것.** `~/.aws/credentials`는 EC2 파일 시스템에만 두고, repo 안에 복사하면 안 됨.

### 5-5. Sonnet 4.6 Vision 호출 검증

한국어 텍스트가 포함된 이미지 1장을 `~/test_banner.png` (또는 `.jpg`)로 EC2 홈에 올리고:

```bash
python3 - <<'PY'
import base64
import json
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

IMG_PATH = Path.home() / "test_banner.png"
if not IMG_PATH.exists():
    sys.exit(f"테스트 이미지 없음: {IMG_PATH} — 한국어 텍스트가 포함된 PNG/JPG를 올려두세요")

MODEL_ID = "global.anthropic.claude-sonnet-4-6"

session = boto3.Session(profile_name="personal", region_name="ap-northeast-2")
client = session.client("bedrock-runtime")

img_bytes = IMG_PATH.read_bytes()
img_b64 = base64.b64encode(img_bytes).decode()
media_type = "image/png" if IMG_PATH.suffix.lower() == ".png" else "image/jpeg"
print(f"image: {IMG_PATH} ({len(img_bytes)//1024} KB, {media_type})")
print(f"model: {MODEL_ID}\n")

body = {
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 1024,
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_b64}},
                {"type": "text", "text": "이 이미지에 한국어 텍스트가 있다면 모두 추출해 주세요. 그리고 이미지의 시각적 내용을 한국어로 2~3문장 요약해 주세요."},
            ],
        }
    ],
}

try:
    resp = client.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(resp["body"].read())
    print("✅ SUCCESS\n=== 응답 ===")
    for block in result.get("content", []):
        if block.get("type") == "text":
            print(block["text"])
    usage = result.get("usage", {})
    print(f"\n=== usage: input={usage.get('input_tokens')} output={usage.get('output_tokens')} ===")
except ClientError as e:
    print(f"❌ {e.response['Error']['Code']}: {e.response['Error']['Message']}")
PY
```

### 5-6. 실제 출력 — 시연 응답 카탈로그 (2026-05-24)

> 발표·향후 비교용 베이스라인. 같은 이미지를 다른 모델·다른 프롬프트로 다시 호출할 때 비교 기준이 됨.

**환경:**
- 모델: `global.anthropic.claude-sonnet-4-6`
- 리전: `ap-northeast-2` (서울)
- 입력 이미지: 글로웰의원 메인 페이지 캡처, 512KB PNG
- 토큰: input=1648, output=752

**응답 본문:**

```markdown
## 텍스트 추출

### 상단 네비게이션
글로웰 / 글로웰소개 / 모발이식 / 헤어라인 / 이터널두피문신 / 수염·눈썹이식 / 문신제거 / 전후사진 및 후기 / 커뮤니티 / LOGIN / JOIN

### 메인 배너
- GLOBAL WELLNESS
- **이터널 두피문신**
- 이젠 힘들게 가릴 필요 없습니다!
간단한 시술로 고민을 해결해드립니다.

### 우측 퀵메뉴
빠른상담 / 전후사진 / 오시는길 / 진료시간 / 플러스친구 **글로웰의원** / ▲TOP

### 하단 상담 예약 폼
- **무료 상담예약**
- 이름 / 연락처 / 010
- 상담 내용: 모발이식 / 헤어라인교정 / ☑두피문신 / 수염이식 / 탈모치료 / 기타
- 상담을 위해 개인정보 수집 및 활용에 동의합니다. [자세히 보기]
- 고민이 있으신가요? 지금 바로 문의하세요 **무료상담예약**

### 하단 사업자 정보
상호명 : 글로웰의원 / 서울특별시 영등포구 여의도동 44-11 인영빌딩 3층 글로웰의원 / 02-2631-9900 / 사업자등록번호 : 107-18-38739 / 의료면허 : 제52297호 / 대표자 : 조성민 / 개인정보보호책임자 : 조성민 / 비급여진료수가확인

---

## 이미지 시각적 요약

이 이미지는 **글로웰의원**의 **이터널 두피문신** 시술을 홍보하는 웹사이트 메인 화면입니다. 어두운 배경에 근육질 남성의 뒷모습이 배치되어 있으며, 탈모 고민을 두피문신으로 해결할 수 있다는 메시지를 전달하고 있습니다. 하단에는 무료 상담 예약 폼이 있어 방문자가 즉시 상담을 신청할 수 있도록 구성되어 있습니다.
```

### 5-7. 해석 메모 — 트랙 C 구현 전 알아둘 것

- **OCR 품질이 매우 높음.** 메뉴·배너·폼·사업자정보 4개 영역 텍스트가 거의 누락 없이 추출. 사업자등록번호·의료면허번호 같은 숫자까지 정확. Textract 없이 Vision 단독으로 OCR + 시각 해석을 동시에 처리 가능 — task-queue.md "OCR: Bedrock Vision으로 흡수 (Textract 한국어 미지원으로 제거)" 결정 검증.
- **의료법 회색지대 표현 자동 흡수.** 응답에 "이터널 두피문신 시술을 **홍보하는** 웹사이트 메인 화면" 같이 자연스럽게 **주체 명시 어조**가 나옴 — 강제 프롬프트 없이도. 다만 발표·시연용 본문 생성 시에는 [`generate_description` 프롬프트](../../ai/prompts/)에서 5규칙을 명시적으로 강제할 것 (Vision의 자연 어조에만 의존하지 말 것).
- **토큰 비용 추정.** 입력 1648 tok / 출력 752 tok = 1회 호출 약 $0.012 (Sonnet 4.6 기준 input $3/M + output $15/M). 시연 10개 병원 × Vision 1회 = 약 $0.12. PoC 비용 통제는 `MAX_LLM_DEMO_HOSPITALS=10`으로 강제.
- **재현성·결정성**: Vision 응답은 Titan 임베딩과 달리 결정적 동일 결과 보장 X. 같은 이미지·같은 프롬프트 두 번 호출하면 응답 텍스트가 미세하게 다를 수 있음 — 발표 자료엔 첫 호출 결과 고정해서 사용.

### 5-8. 통과 기준

- [x] 5-1: 콘솔에서 Sonnet 4.6 model access **Access granted** 확인
- [x] 5-2~5-3: IAM User + 인라인 정책 `BedrockSonnet46InvokeOnly` (3-ARN) + Access Key 발급
- [x] 5-4: `aws --profile personal sts get-caller-identity` → 개인 계정 + 본인 User
- [x] 5-5: 스크립트 응답에 (a) 한국어 텍스트가 정확히 추출되고 (b) 시각 요약 한국어로 출력. `input_tokens` / `output_tokens` 정상 표시

### 5-9. 자주 마주치는 문제

**Q. `AccessDeniedException` — `bedrock:InvokeModel` on `arn:aws:bedrock:::foundation-model/anthropic.claude-sonnet-4-6` (region·계정 비어있는 ARN)**

- 원인: 정책에 **3번째 ARN (global FM, region/account 비어있는 형식)** 누락. 가장 흔한 실수
- 해결: 5-2 정책의 3개 ARN 모두 있는지 재확인. `arn:aws:bedrock:::foundation-model/anthropic.claude-sonnet-4-6` — 콜론 사이 비어있는 게 맞음

**Q. `ValidationException` — `Invocation of model ID ... with on-demand throughput isn't supported. Retry your request with the ID or ARN of an inference profile`**

- 원인: foundation-model ID를 직접 호출. Sonnet 4.6은 inference profile 필수
- 해결: `MODEL_ID = "global.anthropic.claude-sonnet-4-6"` (foundation-model ID 아님)

**Q. `ValidationException` — `The provided model identifier is invalid`**

- 원인: 날짜 suffix 포함된 옛 형식(예: `...-20251001-v1:0`) 또는 `apac.` prefix 사용. Sonnet 4.6은 날짜 suffix 없고 Global profile만 제공
- 해결: 정확한 ID는 `global.anthropic.claude-sonnet-4-6` (날짜 없음, `global.` prefix)

**Q. `UnrecognizedClientException` — `The security token included in the request is invalid`**

- 원인: `~/.aws/credentials`의 Access Key가 잘못됐거나 비활성화됨
- 해결: 콘솔에서 Access Key 상태 Active 확인. 새 키 발급 후 옛 키 비활성화 권장

**Q. `aws sts get-caller-identity`가 다른 User 이름으로 인증됨**

- 원인: 같은 계정의 다른 IAM User Access Key를 실수로 `[personal]` 프로파일에 넣음. 정책이 다른 User에 부착돼 있어 호출도 실패
- 해결: `~/.aws/credentials`의 `[personal]` 섹션 키를 5-3에서 받은 정확한 키로 재등록. 첫 4자·끝 4자만 확인하려면 `awk '/^\[/{p=$0} /aws_access_key_id/{print p, substr($3,1,4) "****" substr($3, length($3)-3)}' ~/.aws/credentials`

**Q. EC2에 boto3 session에서 자꾸 지원 계정으로 인증됨**

- 원인: `Session(profile_name="personal")` 안 쓰면 EC2 인스턴스 프로파일이 우선 적용됨
- 해결: 개인 계정 코드는 **반드시 `profile_name="personal"` 명시**. 지원/개인 계정 클라이언트를 헷갈리지 않게 `ai/core/aws_clients.py`에서 팩토리 분리 ([task-queue PR #1](../plans/task-queue.md))

**Q. 비용이 갑자기 튐**

- Sonnet 4.6은 input $3/M + output $15/M. PoC는 시연용 **10개 병원**으로 제한. 환경변수 `MAX_LLM_DEMO_HOSPITALS=10`으로 강제
- 키 유출 시 1차 방어: 정책이 Sonnet 4.6 InvokeModel만 허용해서 EC2 띄우기·S3 절도 등 불가
- 2차 방어: Budgets 알람 (5-3 안전망 메모 참조)

전부 ✅면 트랙 C(Vision 시연) 구현 진입 가능.

---

## Step 6 — DynamoDB 단일 테이블 수동 생성 (AWS 콘솔)

> 2026-05-27 V2 single-table 갱신. `SafeRole-{username}` (지원 계정)은 `dynamodb:CreateTable` 권한이 **없음** — 자동화 스크립트는 무조건 `AccessDeniedException`. **AWS 콘솔에서 직접 생성**한다. 추가 IAM 발급 없음.

### 6-1. 작명 규칙 (확정)

강사 정책상 자원 이름은 **본인 username prefix**(`kmuproj-XX-*`)로 시작. DynamoDB·S3·EC2 인스턴스 이름 전부 적용.

본 프로젝트 AI 트랙: **`kmuproj-10-clinic-Main`** 한 개. (옛 V1 7-table `kmuproj-10-clinic-Hospitals/...` 은 2026-05-27 삭제)

### 6-2. 콘솔에서 생성할 테이블 스펙

[`be/adapters/dynamo_adapter.py`](../../be/adapters/dynamo_adapter.py) 와 **정확히 일치**해야 e2e 가능. entity 종류 전체 표는 [`../plans/task-queue.md`](../plans/task-queue.md) §3-2.

| 항목 | 값 |
|---|---|
| **Table name** | `kmuproj-10-clinic-Main` |
| **Partition key** | `hospital_id` (String) |
| **Sort key** | `entity` (String) |
| **Capacity mode** | On-demand (PAY_PER_REQUEST) |
| **GSI #1** | `sigungu-specialty-index` — PK=`sigungu_specialty` (String), SK=`confidence_score` (Number), Projection=ALL |
| **GSI #2** | `geo-index` — PK=`geohash_prefix` (String), SK=`lat_lng` (String), Projection=ALL |

> GSI 키는 **모두 META 항목만 sparse 인덱싱**. 분류 완료 시 `save_classification` 이 META 에 `sigungu_specialty` (`"{sigungu}#{standard_specialty}"`)·`confidence_score` 를 patch → sigungu-specialty-index 에 등장 시작. `geohash_prefix`·`lat_lng` 는 지도 검색 진입(Phase D) 시 채움.

### 6-3. 콘솔 절차

1. AWS 콘솔 → DynamoDB → 리전 **`us-east-1`** 확인
2. **Create table**
3. **Table name**: `kmuproj-10-clinic-Main`
4. **Partition key**: `hospital_id` / **String**
5. **Sort key**: `entity` / **String**
6. **Table settings** → Customize settings:
   - **Table class**: Standard
   - **Read/write capacity settings**: **On-demand**
7. **Secondary indexes** → **Create global index** (2 회):

   **GSI #1**
   - Partition key: `sigungu_specialty` / **String**
   - Sort key: `confidence_score` / **Number**
   - Index name: `sigungu-specialty-index`
   - Attribute projections: **All**

   **GSI #2**
   - Partition key: `geohash_prefix` / **String**
   - Sort key: `lat_lng` / **String**
   - Index name: `geo-index`
   - Attribute projections: **All**

8. **Create table** → 상태 `Active` 대기 (보통 30초)

### 6-4. 검증

```bash
aws dynamodb describe-table --table-name kmuproj-10-clinic-Main --region us-east-1 \
  | python3 -c "import sys,json; t=json.load(sys.stdin)['Table']; print('Keys:', t['KeySchema']); print('GSIs:', [(g['IndexName'], g['KeySchema']) for g in t.get('GlobalSecondaryIndexes',[])])"
```

기대 출력:
```
Keys: [{'AttributeName': 'hospital_id', 'KeyType': 'HASH'}, {'AttributeName': 'entity', 'KeyType': 'RANGE'}]
GSIs: [('sigungu-specialty-index', [...sigungu_specialty:HASH..., confidence_score:RANGE]),
       ('geo-index',               [...geohash_prefix:HASH..., lat_lng:RANGE])]
```

### 6-5. 환경변수 확정

`.env` 에:
```
DYNAMO_TABLE=kmuproj-10-clinic-Main
```

(옛 `TABLE_PREFIX` 는 `ai/scratch/` 우회로 전용이었고, scratch 제거와 함께 `.env.example` 에서도 삭제됨.)

### 6-6. 트러블슈팅

**Q. 자동화 스크립트로 만들고 싶다**

- 안 됨. SafeRole 에 `dynamodb:CreateTable` 자체가 없고 추가 IAM 발급도 없다. 콘솔이 유일한 길.

**Q. 다른 계정(BE 등)이 만든 비슷한 이름 테이블이 보임 (`kmuproj-02-team3-backend` 등)**

- 강사 정책상 같은 계정 내 모든 테이블이 `ListTables`에는 보임. 권한은 prefix·account별로 분리. 본인이 만든 것만 read/write 가능
- BE 풀커버 데이터는 BE 계정에 있고, AI 미니 표본은 AI 계정. 데이터 공유 없음 (계정 분리 결정, 2026-05-25)

**Q. 콘솔에서 `Region not supported` 에러**

- 리전이 `ap-northeast-2`(서울)로 잡혀 있을 가능성. 지원 계정 자원은 무조건 **`us-east-1`**. 콘솔 우상단 리전 선택기로 변경

---

## Step 7 — AI 자체 S3 버킷 생성

### 7-1. 버킷 생성

```bash
aws s3 mb s3://kmuproj-10-clinic-focus-crawl --region us-east-1
```

자기 username prefix 버킷이라 권한 OK 예상. 실패 시:

- AccessDenied → AWS 콘솔 → S3 → Create bucket → name `kmuproj-10-clinic-focus-crawl`, region `us-east-1`, 나머지 기본값
- BucketAlreadyExists → 글로벌 네임스페이스 충돌. 다른 이름 시도 (`kmuproj-10-clinic-crawl` 등) 후 `.env` 갱신

### 7-2. 검증

```bash
aws s3 ls | grep kmuproj-10
echo "---"
# 권한 확인 — 더미 객체 put → get → delete
echo "ping" | aws s3 cp - s3://kmuproj-10-clinic-focus-crawl/probe.txt
aws s3 cp s3://kmuproj-10-clinic-focus-crawl/probe.txt -
aws s3 rm s3://kmuproj-10-clinic-focus-crawl/probe.txt
```

put·get·delete 셋 다 성공해야 `S3Adapter` boto3 전환 가능.

### 7-3. 환경변수

`.env` 의 `S3_CRAWL_BUCKET=kmuproj-10-clinic-focus-crawl` 확인. `.env.example` 의 같은 변수는 의도적으로 비워둬서 BE·AI 담당자가 각자 채우게 함 (자기 username prefix).

---

## 다음 단계

여기까지 끝나면 AWS 자원 셋업·dev e2e 검증은 완료. 이후 작업은 **본체 코드 구현**으로 넘어간다:

- AI 트랙 — ✅ `ai/scratch/` 우회로를 `ai/` 본체(`ingest_hospital`·`retrieve_hospital`·`classify_hospital`)로 마이그레이션 완료. scratch 폴더 제거됨. 상세 잔여 작업은 [`../plans/task-queue.md` §4 Phase A~G](../plans/task-queue.md)
- BE 트랙 — `s3_adapter` boto3 전환, `crawl_all.py` `TABLE_PREFIX` 적용, FastAPI 4개 엔드포인트 본체. 위임된 이슈는 [#23](https://github.com/BORB-CHOI/clinic-focus/issues/23) · [#24](https://github.com/BORB-CHOI/clinic-focus/issues/24) · [#13](https://github.com/BORB-CHOI/clinic-focus/issues/13) · [#18](https://github.com/BORB-CHOI/clinic-focus/issues/18)
- FE 트랙 — 9개 영역 컴포넌트, 1-tap 피드백, 분류 변경 이력 UI

서버 띄우기·systemd·SSH는 [`../../deploy/README.md`](../../deploy/README.md).

## 관련 문서

- [`../plans/task-queue.md`](../plans/task-queue.md) — V2 sprint 큐 (이 문서가 다루는 자원 셋업 이후의 본체 구현 작업)
- [`../../deploy/README.md`](../../deploy/README.md) — systemd · uvicorn · SSH · 데이터 적재 명령
- [`../API-BE-AI.md`](../API-BE-AI.md) — BE↔AI 함수 명세 (KB Retrieve/ingest 구조 + 실측 함정)
- [`../API-FE-BE.md`](../API-FE-BE.md) — FE↔BE 인터페이스
- [`../../ai/CLAUDE.md`](../../ai/CLAUDE.md) — AI 트랙 운영 규칙
- [`../../CLAUDE.md`](../../CLAUDE.md) — 프로젝트 전체 컨텍스트 (AWS 계정·인프라 구조)
