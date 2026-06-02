"""EC2 uvicorn 진입점.

실행 (둘 다 동작, repo 루트에서):
    python be/main.py
    python -m uvicorn be.handlers.api:app --host 0.0.0.0 --port 8000 --workers 1
"""

from __future__ import annotations

import os
import sys

import uvicorn

# `python be/main.py` 로 직접 실행하면 sys.path[0] 가 be/ 디렉터리라 'be' 패키지를
# 못 찾아 uvicorn 의 import-string("be.handlers.api:app") 이 ModuleNotFoundError 로 깨진다.
# repo 루트를 경로에 추가해 어느 실행 방식이든 import 되게 한다 (reload=False·workers=1 이라
# 단일 프로세스 → 이 sys.path 주입이 그대로 유효).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    uvicorn.run(
        "be.handlers.api:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        workers=1,
        reload=False,
    )
