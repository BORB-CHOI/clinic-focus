"""FastAPI 앱 — EC2 uvicorn 으로 실행."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# .env 로드 — uvicorn · `python -m uvicorn` 등 어떤 진입점으로 떠도 KB_ID·AWS_REGION 등
# 환경변수를 확보한다(자연어 검색 retrieve_hospital 이 KB_ID 필요). 스크립트는 각자 load 하지만
# API 서버는 진입점이 외부(uvicorn)라 앱 모듈에서 직접 로드해야 self-sufficient.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from be.api.feedback import router as feedback_router
from be.api.history import router as history_router
from be.api.hospital import router as hospital_router
from be.api.search import router as search_router

app = FastAPI(
    title="ClinicFocus API",
    description="병원 실제 주력 분야 검색 서비스",
    version="0.1.0",
)

# 허용 오리진 — env CORS_ALLOW_ORIGINS(쉼표 구분) 우선, 기본은 FE 로컬 dev 서버.
# CloudFront 도메인은 Phase G 배포 시 env 로 주입 (예: "https://dxxxx.cloudfront.net").
_default_origins = "http://localhost:5173"
_allow_origins = [
    o.strip()
    for o in os.environ.get("CORS_ALLOW_ORIGINS", _default_origins).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(search_router)
app.include_router(hospital_router)
app.include_router(history_router)
app.include_router(feedback_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
