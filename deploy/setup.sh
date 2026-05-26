#!/bin/bash
# EC2 초기 세팅 스크립트 — 한번만 실행

set -e

echo "=== ClinicFocus EC2 세팅 ==="

# 1. 프로젝트 디렉토리 이동
cd ~/clinic-focus

# 2. 가상환경 + 패키지
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt

# 3. 데이터 디렉토리 생성
mkdir -p data/crawl data/images

# 4. systemd 서비스 등록
sudo cp deploy/clinicfocus.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable clinicfocus
sudo systemctl start clinicfocus

echo ""
echo "=== 세팅 완료 ==="
echo "서버 상태: sudo systemctl status clinicfocus"
echo "로그 확인: sudo journalctl -u clinicfocus -f"
echo ""
echo "데이터 적재 순서:"
echo "  1. python be/scripts/load_hospitals.py"
echo "  2. python be/scripts/enrich_urls_naver.py"
echo "  3. python be/scripts/crawl_all.py"
echo "  4. python be/scripts/download_images.py"
echo "  5. python be/scripts/run_classification.py (AI 모듈 완성 후)"
