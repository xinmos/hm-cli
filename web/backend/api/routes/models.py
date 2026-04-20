from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from web.backend.app_state import WebServiceContainer

router = APIRouter()


class ModelResponse(BaseModel):
    id: str
    name: str
    provider: str
    context_size: int
    is_available: bool


def _services(request: Request) -> WebServiceContainer:
    return request.app.state.services


@router.get("", response_model=list[ModelResponse])
async def list_models(request: Request) -> list[ModelResponse]:
    models = _services(request).model_catalog.list_models()
    return [ModelResponse(**model) for model in models]
