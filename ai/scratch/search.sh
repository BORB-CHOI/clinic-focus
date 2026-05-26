#!/usr/bin/env bash
# 자연어 쿼리로 14개 KB 인덱스 검색.
#
# 사용법:
#   ./ai/scratch/search.sh "여드름 잘 보는 피부과"
#   ./ai/scratch/search.sh "코골이 수술"
#
# 인자 없으면 쿼리 입력 받음.

set -e

cd "$(dirname "$0")/../.."

if [ $# -eq 0 ]; then
  read -p "검색어: " QUERY
else
  QUERY="$*"
fi

.venv/bin/python ai/scratch/search_one.py "$QUERY"
