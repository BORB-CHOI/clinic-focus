#!/bin/bash
# 크롤링 진행 현황 확인 스크립트
# 사용법: bash crawl_status.sh

echo "=== 크롤링 진행 현황 ==="
echo ""

# 프로세스 상태
PID=$(ps aux | grep 'crawl_all.py' | grep -v grep | awk '{print $2}')
if [ -n "$PID" ]; then
    echo "🟢 프로세스 실행 중 (PID: $PID)"
else
    echo "🔴 프로세스 중지됨"
fi
echo ""

# 로그 마지막 진행률
echo "--- 최근 로그 ---"
tail -3 crawl_all_log.txt 2>/dev/null
echo ""

# 로컬 데이터 카운트
cd /home/ec2-user/clinic-focus
python3 -c "
import json, glob
all_files = glob.glob('data/crawl/*.json') + glob.glob('data/crawl/*/crawl_data.json')
print(f'📦 로컬 저장: {len(all_files)}개 / 2,590개 ({len(all_files)/2590*100:.1f}%)')
"
echo ""

# 성공/실패 카운트
grep -c "✅\|정적 크롤링 성공\|JS 렌더링 성공" crawl_all_log.txt 2>/dev/null | xargs -I{} echo "✅ 성공: {}건"
grep -c "❌" crawl_all_log.txt 2>/dev/null | xargs -I{} echo "❌ 실패: {}건"
