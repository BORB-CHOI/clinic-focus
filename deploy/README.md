# EC2 배포·운영

> **역할 경계** — 이 디렉토리는 *이미 준비된 EC2*에서 FastAPI를 systemd로 띄우고 데이터 적재
> 파이프라인을 돌리는 **운영**만 다룬다. AWS 자격증명·Bedrock 모델 가용성·KB·DDB/S3 생성 같은
> **계정/자원 셋업(1회)**은 [`../docs/setup/aws-onboarding.md`](../docs/setup/aws-onboarding.md)가
> 진입점이다. 둘은 겹치지 않게 분리한다 — 셋업은 onboarding, 기동·적재는 여기.

## 파일

| 파일 | 역할 |
|---|---|
| `clinicfocus.service` | systemd unit — `be.handlers.api:app` 을 uvicorn으로 (`AWS_REGION=us-east-1`, `0.0.0.0:8000`, `Restart=always`) |
| `setup.sh` | EC2 최초 1회 — venv 생성 · `requirements.txt` 설치 · 로컬 캐시 디렉토리 생성 · systemd 등록·시작 |

## 서버 자동 시작 (systemd)

```bash
sudo cp deploy/clinicfocus.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable clinicfocus
sudo systemctl start clinicfocus

sudo systemctl status clinicfocus       # 상태
sudo journalctl -u clinicfocus -f       # 실시간 로그
```

## 수동 실행 (개발 중)

```bash
cd ~/clinic-focus
source .venv/bin/activate
python be/main.py                       # uvicorn 진입점 (PORT env, 기본 8000)
# 또는
python -m uvicorn be.handlers.api:app --host 0.0.0.0 --port 8000 --workers 1
```

> `.env`(레포 **루트**)는 `be/handlers/api.py`가 기동 시 자동 로드한다. 별도 export 불필요.

## 데이터 적재 순서 (강남 PoC 기준)

> 자기 계정 자원(DDB·S3) 셋업 전제. 미완료면 [`../docs/setup/aws-onboarding.md`](../docs/setup/aws-onboarding.md) Step 6·7 먼저.

```bash
source .venv/bin/activate

# 1. 심평원(HIRA) → DynamoDB META (강남구; load_seoul_5gu 가 5개 구 코드 보유, 강남만 적재해도 됨)
python be/scripts/load_seoul_5gu.py

# 2. 카카오/네이버로 자체 홈페이지 URL 보강
python be/scripts/enrich_urls.py

# 3. 자체사이트 크롤 (본문 → S3, .env 의 S3_CRAWL_BUCKET/CRAWL_DATA_DIR 따름)
python be/scripts/crawl_all.py

# 4. 네이버 플레이스 후기 합류 (로컬 raw 수집 후 적재)
python be/scripts/crawl_naver_local.py
python be/scripts/ingest_naver_local.py --confirm

# 5. 룰 기반 분류 + KB ingest (LLM 0회, 강남 전수 베이스라인)
python be/scripts/run_classification.py --sigungu 강남구
```

> **시연 10개 한정 LLM/Vision 오버레이**(`run_vision_demo.py` → `run_llm_demo.py`)는 개인 계정
> Sonnet 4.6을 쓴다. **2026-06-01부터 개인 계정 쿼터 소진으로 신규 호출 금지** — 기존 적재분은
> 정적 데이터로 사용한다. 분류/검색 동작 상세는 [`../docs/architecture.md`](../docs/architecture.md),
> 남은 작업은 [`../docs/plans/task-queue.md`](../docs/plans/task-queue.md).

## FE 배포

FE는 별도. `cd fe && npm run build` → `aws s3 sync dist/ s3://<fe-bucket>` (CloudFront). 자세한 건
[`../fe/CLAUDE.md`](../fe/CLAUDE.md). dev 서버는 `npm run dev`(:5173, vite proxy `/api → :8000`).

## SSH 접속

```bash
# <ec2-public-ip> 는 현재 인스턴스 퍼블릭 IP로 치환 (재시작 시 변할 수 있음)
ssh -p 443 -i "키파일.pem" ec2-user@<ec2-public-ip>

# 학교 네트워크 등에서 API 접속용 터널
ssh -p 443 -i "키파일.pem" -L 8000:localhost:8000 ec2-user@<ec2-public-ip>
# → 로컬 브라우저에서 http://localhost:8000/docs
```

> 평소 개발은 VSCode Remote-SSH(로컬 UI + EC2 실행). 셋업은 onboarding Step 0 참조.

## 환경변수

레포 루트 `.env` 에 적재(전체 키·코멘트는 [`.env.example`](../.env.example)). 최소 필수:

- `AWS_REGION=us-east-1` — 지원 계정 자원(DDB·S3·Titan·KB)
- `DYNAMO_TABLE` — 이 EC2(AI 계정)는 `kmuproj-10-clinic-Main`. (BE 계정 배포는 `kmuproj-02-team3-backend`)
- `S3_CRAWL_BUCKET` — 자체사이트 본문 버킷 (계정별 `kmuproj-XX-...`)
- `KB_ID=GTBJ6HLFDK` · `KB_DATA_SOURCE_ID=PLC6QYALDU` — 강사 제공 KB `kmuproj-team-03`
- `HIRA_API_KEY` (공공데이터포털) · `KAKAO_REST_API_KEY` · `NAVER_MAP_CLIENT_ID/SECRET` (URL 보강·외부 시그널)
- `AI_AWS_ACCESS_KEY_ID/SECRET_ACCESS_KEY/REGION` — 개인 계정 Sonnet 4.6 Vision 호출용 IAM User 키(서울 `ap-northeast-2`). onboarding Step 5 참조. (2026-06-01 쿼터 소진, 신규 호출 보류)
- `VITE_KAKAO_MAP_KEY` — FE 카카오맵 JS 키

> 검색 랭킹 튜닝용 `KB_MIN_SCORE`(기본 0.42)·`FOCUS_RANK_WPF/WFREQ/WCHUNK`·`RANK_MODE`는 기본값이
> 운영값이라 평소 설정 불필요 — 의미는 [`../docs/architecture.md`](../docs/architecture.md) §5 참조.

## 관련 문서

- [`../docs/setup/aws-onboarding.md`](../docs/setup/aws-onboarding.md) — 계정·자원 셋업(1회) 진입점
- [`../docs/architecture.md`](../docs/architecture.md) — 데이터·분류·검색 아키텍처(주력 강도 랭킹 §5-1)
- [`../docs/plans/task-queue.md`](../docs/plans/task-queue.md) — 남은 작업
- [`../docs/API-FE-BE.md`](../docs/API-FE-BE.md) · [`../docs/API-BE-AI.md`](../docs/API-BE-AI.md) — 인터페이스 명세
