"""FastAPI 앱 — EC2 uvicorn 으로 실행."""

from __future__ import annotations

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router)
app.include_router(hospital_router)
app.include_router(history_router)
app.include_router(feedback_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
