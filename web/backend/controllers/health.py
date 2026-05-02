from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "api": "Hermes Web API",
        "streaming": "sse",
        "workspace": "ready",
    }
