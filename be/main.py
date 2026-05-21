"""EC2 uvicorn 진입점.

실행:
    python be/main.py
    python -m uvicorn be.handlers.api:app --host 0.0.0.0 --port 8000 --workers 1
"""

from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "be.handlers.api:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        workers=1,
        reload=False,
    )
