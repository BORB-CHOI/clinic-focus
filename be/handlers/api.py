"""FastAPI 앱 — EC2 uvicorn 으로 실행."""

from __future__ import annotations

import os

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
