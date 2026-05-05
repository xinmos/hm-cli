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
    exists: bool = False
    is_directory: bool = True
    is_initialized: bool = False
    missing_items: list[str] = Field(default_factory=list)
    status_message: str = ""
    init_result: dict | None = None


class QQBotConfigPayload(BaseModel):
    app_id: str | None = None
    secret: str | None = None
    sandbox: bool = False
    timeout: int = Field(default=5, ge=1)
    enable_guild: bool = True
    enable_direct: bool = True
    enable_group: bool = True
    enable_c2c: bool = True
    enable_markdown: bool = True


class QQBotConfigResponse(BaseModel):
    config: QQBotConfigPayload
    saved: dict
    env: dict
    env_masked: dict


class FeishuBotConfigPayload(BaseModel):
    app_id: str | None = None
    app_secret: str | None = None
    verification_token: str | None = None
    encrypt_key: str | None = None
    domain: str = Field(default="https://open.feishu.cn", min_length=1)
    auto_reconnect: bool = True


class FeishuBotConfigResponse(BaseModel):
    config: FeishuBotConfigPayload
    saved: dict
    env: dict
    env_masked: dict
