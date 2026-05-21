# EC2 배포 가이드

## 서버 자동 시작 설정 (systemd)

```bash
# 서비스 파일 복사
sudo cp deploy/clinicfocus.service /etc/systemd/system/

# 서비스 활성화 + 시작
sudo systemctl daemon-reload
sudo systemctl enable clinicfocus
sudo systemctl start clinicfocus

# 상태 확인
sudo systemctl status clinicfocus

# 로그 확인
sudo journalctl -u clinicfocus -f
```

## 수동 실행

```bash
cd ~/clinic-focus
source .venv/bin/activate
export AWS_REGION=us-east-1
uvicorn be.handlers.api:app --host 0.0.0.0 --port 8000
```

## 데이터 적재 순서

```bash
# 1. 심평원 → DynamoDB (서울 5개 구)
python be/scripts/load_seoul_5gu.py

# 2. 카카오로 홈페이지 URL 보강
python be/scripts/enrich_urls.py

# 3. 전체 크롤링
python be/scripts/crawl_all.py
```

## SSH 접속

```bash
ssh -p 443 -i "키파일.pem" ec2-user@3.95.24.182
```

## SSH 터널 (학교 네트워크에서 API 접속)

```bash
ssh -p 443 -i "키파일.pem" -L 8000:localhost:8000 ec2-user@3.95.24.182
# 이후 브라우저에서 http://localhost:8000/docs
```
