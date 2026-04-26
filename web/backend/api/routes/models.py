from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from web.backend.app_state import WebServiceContainer

router = APIRouter()


class ModelResponse(BaseModel):
    id: str
    name: str
    provider: str
    context_size: int
    is_available: bool


class LLMConfigPayload(BaseModel):
    provider: str = "openai-compatible"
    api_key: str | None = None
    base_url: str | None = None
    model: str = Field(min_length=1)
    temperature: float = Field(ge=0, le=2)
    max_tokens: int = Field(ge=1)
    timeout: int = Field(ge=1)
    max_retries: int = Field(ge=0)
    top_p: float = Field(ge=0, le=1)
    streaming: bool
    custom_models: list[str] = Field(default_factory=list)


class LLMConfigResponse(BaseModel):
    config: LLMConfigPayload
    saved: dict
    env: dict
    env_masked: dict


class EnvTextPayload(BaseModel):
    content: str


class EnvTextResponse(BaseModel):
    content: str


class ConnectionTestResponse(BaseModel):
    ok: bool
    message: str


def _services(request: Request) -> WebServiceContainer:
    return request.app.state.services


@router.get("", response_model=list[ModelResponse])
async def list_models(request: Request) -> list[ModelResponse]:
    models = _services(request).model_catalog.list_models()
    return [ModelResponse(**model) for model in models]


@router.get("/config", response_model=LLMConfigResponse)
async def get_model_config(request: Request) -> LLMConfigResponse:
    return _build_config_response(_services(request).llm_config)


@router.put("/config", response_model=LLMConfigResponse)
async def update_model_config(payload: LLMConfigPayload, request: Request) -> LLMConfigResponse:
    service = _services(request).llm_config
    service.update_config(payload.model_dump())
    return _build_config_response(service)


@router.post("/config/test", response_model=ConnectionTestResponse)
async def test_model_config(payload: LLMConfigPayload, request: Request) -> ConnectionTestResponse:
    service = _services(request).llm_config
    try:
        content = service.test_connection(payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    preview = content.strip()[:200] or "连接成功"
    return ConnectionTestResponse(ok=True, message=preview)


@router.get("/config/export-env", response_model=EnvTextResponse)
async def export_model_env(request: Request) -> EnvTextResponse:
    return EnvTextResponse(content=_services(request).llm_config.export_env())


@router.post("/config/import-env", response_model=LLMConfigResponse)
async def import_model_env(payload: EnvTextPayload, request: Request) -> LLMConfigResponse:
    service = _services(request).llm_config
    service.import_env(payload.content)
    return _build_config_response(service)


def _build_config_response(service) -> LLMConfigResponse:
    saved = service.get_saved_config()
    env = service.get_env_config()
    display_config = service.get_effective_config().to_dict()
    display_config["api_key"] = saved.get("api_key") if isinstance(saved.get("api_key"), str) else ""
    return LLMConfigResponse(
        config=LLMConfigPayload(**display_config),
        saved=_mask_sensitive(saved),
        env=_mask_sensitive(env),
        env_masked=_mask_sensitive(env),
    )


def _mask_sensitive(config: dict) -> dict:
    masked = dict(config)
    value = masked.get("api_key")
    if isinstance(value, str) and value:
        masked["api_key"] = _mask_secret(value)
    return masked


def _mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return f"{value[:6]}...{value[-4:]}"
