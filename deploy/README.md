# EC2 배포·운영 스크립트

> EC2 인스턴스에 FastAPI를 systemd로 띄우고 데이터 적재 파이프라인을 돌리는 운영 스크립트. **신규 팀원 온보딩**(AWS 자격증명·Bedrock 모델 가용성·KB 확인 등)은 [`../docs/setup/aws-onboarding.md`](../docs/setup/aws-onboarding.md) 가 진입점이다. 이 README는 EC2가 이미 준비된 상태에서 서비스를 띄우는 부분만 다룬다.

## 파일

| 파일 | 역할 |
|---|---|
| `clinicfocus.service` | systemd unit. `be.handlers.api:app` 을 uvicorn으로 띄움 (`AWS_REGION=us-east-1`, `--host 0.0.0.0 --port 8000`) |
| `setup.sh` | EC2 최초 1회 — venv 생성·`requirements.txt` 설치·`data/{crawl,images}/` 생성·systemd 등록·시작 |

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
export AWS_REGION=us-east-1
python be/main.py                       # be/main.py 가 uvicorn 진입점 (PR #8)
# 또는
uvicorn be.handlers.api:app --host 0.0.0.0 --port 8000
```

## 데이터 적재 순서 (BE 트랙 기준)

> 자기 계정 자원(DDB·S3) 셋업이 끝났다는 전제. 미완료면 [`../docs/setup/aws-onboarding.md`](../docs/setup/aws-onboarding.md) Step 6·7 먼저.

```bash
# 1. 심평원 → DynamoDB (서울 5개 구)
python be/scripts/load_seoul_5gu.py

# 2. 카카오로 홈페이지 URL 보강
python be/scripts/enrich_urls.py

# 3. 전체 크롤링 (S3·로컬 FS, .env 의 STORAGE_BACKEND·CRAWL_DATA_DIR 따름)
python be/scripts/crawl_all.py

# 4. (선택) Vision 시연용 이미지 다운로드 — 시연 10개만
python be/scripts/download_images.py

# 5. (AI 트랙) 분류·설명 + KB ingest
python be/scripts/run_classification.py
```

> AI 트랙은 별도 시나리오로 강남구 4과목 88개 미니 표본을 적재한다 — [`../docs/plans/task-queue.md`](../docs/plans/task-queue.md) §4 AI 워크북 참조.

## SSH 접속

```bash
# 기본 (학교 외 네트워크)
ssh -p 443 -i "키파일.pem" ec2-user@3.95.24.182

# 학교 네트워크에서 API 접속용 터널
ssh -p 443 -i "키파일.pem" -L 8000:localhost:8000 ec2-user@3.95.24.182
# → 로컬 브라우저에서 http://localhost:8000/docs
```

## 환경변수

`be/.env` 에 적재. 최소 필수:

- `AWS_REGION=us-east-1` (지원 계정 자원 — DDB·S3·Titan·KB)
- `TABLE_PREFIX=kmuproj-02-clinic-` (BE 계정) 또는 `kmuproj-10-clinic-` (AI 계정)
- `S3_CRAWL_BUCKET=kmuproj-02-clinic-focus-crawl` (BE) 또는 `kmuproj-10-clinic-focus-crawl` (AI)
- `KB_ID=GTBJ6HLFDK` · `KB_DATA_SOURCE_ID=PLC6QYALDU`
- `HIRA_API_KEY=...` (공공데이터포털 발급)
- `KAKAO_REST_API_KEY=...` (URL 보강용)
- `AI_AWS_*` — 개인 계정 Sonnet 4.6 Vision 호출용 (Marketplace 구독 후 활성)

전체 키 목록·코멘트는 `.env.example` 참조.

## 관련 문서

- [`../docs/setup/aws-onboarding.md`](../docs/setup/aws-onboarding.md) — 신규 팀원 온보딩 단계별 가이드
- [`../docs/plans/task-queue.md`](../docs/plans/task-queue.md) — V2 sprint 큐
- [`../docs/API-FE-BE.md`](../docs/API-FE-BE.md) · [`../docs/API-BE-AI.md`](../docs/API-BE-AI.md) — 인터페이스 명세
