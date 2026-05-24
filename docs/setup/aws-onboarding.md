# AWS 환경 세팅 — 팀 온보딩 가이드

> clinic-focus 프로젝트의 AI 트랙 작업 환경을 처음부터 따라잡기 위한 단계별 가이드.
> 2026-05-24 최비성이 실제 진행한 과정을 기준으로 작성.
> Step 2 이후(Titan 호출·KB 적재·Sonnet Vision)는 아직 검증 안 된 상태라 이 문서에서 제외.

---

## 이 문서가 다루는 범위

✅ **다룸**: 로컬 VSCode → EC2 SSH 접속 / 자격증명 확인 / Bedrock 모델 가용성 확인 / boto3 설치 / 강사 제공 KB 발견

❌ **안 다룸**: Titan 임베딩 실제 호출(Step 2) / KB Retrieve 왕복(Step 3) / DataSource 적재(Step 4) / 개인 계정 Sonnet 4.5 Vision(Step 5). 진행 후 별도 가이드 추가 예정.

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

## 다음 단계

이후 Step은 `docs/plans/task-queue.md` "AI 트랙 AWS 세팅 todo" 섹션 참조.
검증 완료되는 대로 본 문서에 Step 2~5 추가 예정.

## 관련 문서

- [`docs/plans/task-queue.md`](../plans/task-queue.md) — 전체 작업 큐 (이 문서는 Step 0~1의 재현 가이드)
- [`docs/API-BE-AI.md`](../API-BE-AI.md) — BE↔AI 함수 명세 (KB Retrieve/ingest 구조)
- [`ai/CLAUDE.md`](../../ai/CLAUDE.md) — AI 트랙 운영 규칙
- [`CLAUDE.md`](../../CLAUDE.md) — 프로젝트 전체 컨텍스트 (AWS 계정·인프라 구조)
