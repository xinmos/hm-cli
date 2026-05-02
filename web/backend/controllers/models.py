from __future__ import annotations

from fastapi import APIRouter, Request

from web.backend.controllers.dependencies import get_services, to_http_error
from web.backend.models.llm import (
    ConnectionTestResponse,
    EnvTextPayload,
    EnvTextResponse,
    LLMConfigPayload,
    LLMConfigResponse,
    ModelResponse,
    WikiConfigPayload,
    WikiConfigResponse,
)
from web.backend.services.exceptions import BackendServiceError
from web.backend.services.llm_service import LLMApiService

router = APIRouter()


def _llm_service(request: Request) -> LLMApiService:
    return LLMApiService(get_services(request))


@router.get("", response_model=list[ModelResponse])
async def list_models(request: Request) -> list[ModelResponse]:
    return _llm_service(request).list_models()


@router.get("/config", response_model=LLMConfigResponse)
async def get_model_config(request: Request) -> LLMConfigResponse:
    return _llm_service(request).get_config()


@router.get("/wiki-config", response_model=WikiConfigResponse)
async def get_wiki_config(request: Request) -> WikiConfigResponse:
    return _llm_service(request).get_wiki_config()


@router.put("/config", response_model=LLMConfigResponse)
async def update_model_config(payload: LLMConfigPayload, request: Request) -> LLMConfigResponse:
    return _llm_service(request).update_config(payload)


@router.put("/wiki-config", response_model=WikiConfigResponse)
async def update_wiki_config(payload: WikiConfigPayload, request: Request) -> WikiConfigResponse:
    try:
        return _llm_service(request).update_wiki_config(payload)
    except BackendServiceError as exc:
        raise to_http_error(exc) from exc


@router.post("/wiki-config/init", response_model=WikiConfigResponse)
async def initialize_wiki(payload: WikiConfigPayload, request: Request) -> WikiConfigResponse:
    try:
        return _llm_service(request).initialize_wiki(payload)
    except BackendServiceError as exc:
        raise to_http_error(exc) from exc


@router.post("/config/test", response_model=ConnectionTestResponse)
async def test_model_config(payload: LLMConfigPayload, request: Request) -> ConnectionTestResponse:
    try:
        return _llm_service(request).test_config(payload)
    except BackendServiceError as exc:
        raise to_http_error(exc) from exc


@router.get("/config/export-env", response_model=EnvTextResponse)
async def export_model_env(request: Request) -> EnvTextResponse:
    return _llm_service(request).export_env()


@router.post("/config/import-env", response_model=LLMConfigResponse)
async def import_model_env(payload: EnvTextPayload, request: Request) -> LLMConfigResponse:
    return _llm_service(request).import_env(payload.content)
