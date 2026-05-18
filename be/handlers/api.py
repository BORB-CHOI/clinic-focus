"""FastAPI 앱 — Mangum으로 Lambda에 배포."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from be.api.feedback import router as feedback_router
from be.api.history import router as history_router
from be.api.hospital import router as hospital_router
from be.api.search import router as search_router

app = FastAPI(
    title="ClinicFocus API",
    description="병원 실제 주력 분야 검색 서비스",
    version="0.1.0",
)

# CORS — 프론트엔드 (CloudFront) 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # PoC에서는 전체 허용, 프로덕션에서 제한
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(search_router)
app.include_router(hospital_router)
app.include_router(history_router)
app.include_router(feedback_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


# Lambda 핸들러 (Mangum 어댑터)
handler = Mangum(app, lifespan="off")
