from __future__ import annotations

from web.backend.models.llm import (
    ConnectionTestResponse,
    EnvTextResponse,
    LLMConfigPayload,
    LLMConfigResponse,
    ModelResponse,
    WikiConfigPayload,
    WikiConfigResponse,
)
from web.backend.services.container import WebServiceContainer
from web.backend.services.exceptions import ValidationError


class LLMApiService:
    def __init__(self, services: WebServiceContainer):
        self._services = services

    def list_models(self) -> list[ModelResponse]:
        models = self._services.model_catalog.list_models()
        return [ModelResponse(**model) for model in models]

    def get_config(self) -> LLMConfigResponse:
        return self._build_config_response()

    def get_wiki_config(self) -> WikiConfigResponse:
        return WikiConfigResponse(**self._services.llm_config.get_wiki_config())

    def update_config(self, payload: LLMConfigPayload) -> LLMConfigResponse:
        self._services.llm_config.update_config(payload.model_dump())
        return self._build_config_response()

    def update_wiki_config(self, payload: WikiConfigPayload) -> WikiConfigResponse:
        try:
            config = self._services.llm_config.update_wiki_config(payload.path)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return WikiConfigResponse(**config)

    def initialize_wiki(self, payload: WikiConfigPayload) -> WikiConfigResponse:
        try:
            config = self._services.llm_config.initialize_wiki(payload.path)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return WikiConfigResponse(**config)

    def test_config(self, payload: LLMConfigPayload) -> ConnectionTestResponse:
        try:
            content = self._services.llm_config.test_connection(payload.model_dump())
        except Exception as exc:
            raise ValidationError(str(exc)) from exc
        preview = content.strip()[:200] or "连接成功"
        return ConnectionTestResponse(ok=True, message=preview)

    def export_env(self) -> EnvTextResponse:
        return EnvTextResponse(content=self._services.llm_config.export_env())

    def import_env(self, content: str) -> LLMConfigResponse:
        self._services.llm_config.import_env(content)
        return self._build_config_response()

    def _build_config_response(self) -> LLMConfigResponse:
        saved = self._services.llm_config.get_saved_config()
        env = self._services.llm_config.get_env_config()
        display_config = self._services.llm_config.get_effective_config().to_dict()
        display_config["api_key"] = saved.get("api_key") if isinstance(saved.get("api_key"), str) else ""
        return LLMConfigResponse(
            config=LLMConfigPayload(**display_config),
            saved=self._mask_sensitive(saved),
            env=self._mask_sensitive(env),
            env_masked=self._mask_sensitive(env),
        )

    def _mask_sensitive(self, config: dict) -> dict:
        masked = dict(config)
        value = masked.get("api_key")
        if isinstance(value, str) and value:
            masked["api_key"] = self._mask_secret(value)
        return masked

    def _mask_secret(self, value: str) -> str:
        if len(value) <= 8:
            return "****"
        return f"{value[:6]}...{value[-4:]}"
