from __future__ import annotations

from pydantic import BaseModel, Field


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


class WikiConfigPayload(BaseModel):
    path: str = Field(min_length=1)


class WikiConfigResponse(BaseModel):
    path: str
    effective_path: str
    default_path: str
    saved_path: str | None = None
    env_path: str | None = None
