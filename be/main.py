"""EC2 uvicorn 진입점.

실행:
    python -m uvicorn be.main:app --host 0.0.0.0 --port 8000 --workers 1

또는:
    python be/main.py
"""
import os

import uvicorn

from be.handlers.api import app  # noqa: F401

if __name__ == "__main__":
    uvicorn.run(
        "be.handlers.api:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        workers=1,
        reload=False,
    )
