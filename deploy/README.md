# 배포·운영 (EC2)

> **SafeRole 붙은 EC2에서만 동작** — DDB·KB는 IAM Role 인증이라 로컬 PC 불가.
> **자원 생성은 콘솔에서만** — SafeRole 에 `CreateTable`/`CreateBucket` 권한 없음.

## 1. 1회 셋업

**① 콘솔에서 자원 생성**
- **DynamoDB 테이블** (`us-east-1`, On-demand) — 스키마(PK `hospital_id` / SK `entity` + GSI 2개)는 [`../be/CLAUDE.md`](../be/CLAUDE.md) "스키마 — V2 single-table" 그대로.
- **S3 크롤 버킷** — 크롤·재분류 돌릴 때만 필요. `aws s3 mb s3://<username>-clinic-focus-crawl --region us-east-1`

**② 코드·의존성**
```bash
git clone https://github.com/BORB-CHOI/clinic-focus.git && cd clinic-focus
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cd fe && npm install && cd ..
playwright install        # 크롤 돌릴 때만
```

**③ `.env`** (루트 — 데모 서빙에 필요한 최소)
```ini
AWS_REGION=us-east-1
DYNAMO_TABLE=<자기 테이블>          # 예: kmuproj-10-clinic-Main
KB_ID=GTBJ6HLFDK
KB_DATA_SOURCE_ID=PLC6QYALDU
# 크롤/재분류 때만: S3_CRAWL_BUCKET, HIRA_API_KEY, KAKAO_REST_API_KEY, NAVER_MAP_CLIENT_ID/SECRET
```
`fe/.env`:
```ini
VITE_KAKAO_MAP_KEY=<카카오 JS 키>
VITE_API_BASE_URL=                 # 비움 (상대경로 + vite proxy)
```
> 서빙(검색·상세·피드백)은 **KB Retrieve + DDB** 만 호출 → 개인 Bedrock·S3·크롤 API 키 불필요. 전체 키는 [`../.env.example`](../.env.example).

## 2. 데이터

**A. 공유 번들로 (권장)**
```bash
unzip clinic-focus-data-share-*.zip && cd clinic-focus-data-share
python3 restore.py --skip-s3       # DDB만 (서빙엔 S3 불필요). 옛 데이터 섞였으면 --replace
cd ..
```
> KB는 강남-only 로 공유·임베딩 완료 → **재인제스트 금지**.

**B. 처음부터 적재**
```bash
python be/scripts/load_gangnam.py                       # 심평원 → DDB META
python be/scripts/enrich_urls.py                          # 홈페이지 URL 보강
python be/scripts/crawl_all.py                            # 자체사이트 크롤 → S3
python be/scripts/run_classification.py --sigungu 강남구   # 룰 분류 + KB ingest
```

## 3. 기동

```bash
# 백엔드 (:8000) — systemd (영속)
sudo cp deploy/clinicfocus.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now clinicfocus
sudo journalctl -u clinicfocus -f                         # 로그

# 또는 수동 (둘 다 repo 루트에서)
source .venv/bin/activate
python -m uvicorn be.handlers.api:app --host 0.0.0.0 --port 8000   # 권장
python be/main.py                                                   # 동일

# 프론트 (:5173, /api → :8000 proxy)
cd fe && npm run dev
```

### 백그라운드 (SSH 끊어도 유지)

systemd 없이 데모용으로 빠르게 띄울 때. `nohup`으로 띄우면 SSH 세션을 닫아도 프로세스가 살아있다. **둘 다 repo 루트에서:**

```bash
source .venv/bin/activate

# 백엔드 (:8000)
nohup python -m uvicorn be.handlers.api:app --host 0.0.0.0 --port 8000 > be.log 2>&1 &

# 프론트 (:5173) — 외부 접속 허용하려면 --host
nohup npm --prefix fe run dev -- --host > fe.log 2>&1 &
```

```bash
# 상태 확인 / 로그
jobs -l                          # 같은 셸에서 띄웠을 때
ps aux | grep -E 'uvicorn|vite'  # 재접속 후
tail -f be.log fe.log

# 종료 (포트로 PID 찾아서)
kill $(lsof -ti:8000)            # 백엔드
kill $(lsof -ti:5173)            # 프론트
```

> 재부팅 후에도 자동 기동이 필요하면 `nohup` 대신 위의 **systemd**를 쓴다.

## 4. SSH (학교망 등)
```bash
ssh -p 443 -i <key>.pem ec2-user@<ec2-ip>
# API/UI 터널
ssh -p 443 -i <key>.pem -L 8000:localhost:8000 -L 5173:localhost:5173 ec2-user@<ec2-ip>
```

## FE 배포
```bash
cd fe && npm run build && aws s3 sync dist/ s3://<fe-bucket>   # CloudFront
```

## 관련 문서
- [`../be/CLAUDE.md`](../be/CLAUDE.md) — DDB 스키마·엔드포인트
- [`../docs/architecture.md`](../docs/architecture.md) — 데이터·분류·검색 (주력 강도 §5-1)
- [`../docs/API-BE-AI.md`](../docs/API-BE-AI.md) — KB ingest/retrieve 함정·메타 스키마
- [`../docs/known-issues.md`](../docs/known-issues.md) — 알려진 한계 (negation·thin-signal)
- [`../CLAUDE.md`](../CLAUDE.md) — AWS 계정·인프라·권한 정책
