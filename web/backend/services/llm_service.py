from __future__ import annotations

from web.backend.models.llm import (
    ConnectionTestResponse,
    EnvTextResponse,
    FeishuBotConfigPayload,
    FeishuBotConfigResponse,
    LLMConfigPayload,
    LLMConfigResponse,
    ModelResponse,
    QQBotConfigPayload,
    QQBotConfigResponse,
    WikiConfigPayload,
    WikiConfigResponse,
)
from hermes.channels.feishu import (
    read_env_feishu_config,
    read_saved_feishu_config,
    write_saved_feishu_config,
)
from hermes.channels.qq import (
    read_env_qq_config,
    read_saved_qq_config,
    write_saved_qq_config,
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

    def get_qq_config(self) -> QQBotConfigResponse:
        return self._build_qq_config_response()

    def get_feishu_config(self) -> FeishuBotConfigResponse:
        return self._build_feishu_config_response()

    def update_config(self, payload: LLMConfigPayload) -> LLMConfigResponse:
        self._services.llm_config.update_config(payload.model_dump())
        return self._build_config_response()

    def update_wiki_config(self, payload: WikiConfigPayload) -> WikiConfigResponse:
        try:
            config = self._services.llm_config.update_wiki_config(payload.path)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return WikiConfigResponse(**config)

    def update_qq_config(self, payload: QQBotConfigPayload) -> QQBotConfigResponse:
        data = payload.model_dump()
        data["app_id"] = (data.get("app_id") or "").strip()
        data["secret"] = (data.get("secret") or "").strip()
        if data["timeout"] < 1:
            raise ValidationError("QQ bot timeout must be at least 1 second")
        write_saved_qq_config(self._services.settings.workdir, data)
        return self._build_qq_config_response()

    def update_feishu_config(
        self, payload: FeishuBotConfigPayload
    ) -> FeishuBotConfigResponse:
        data = payload.model_dump()
        for key in (
            "app_id",
            "app_secret",
            "verification_token",
            "encrypt_key",
            "domain",
        ):
            data[key] = (data.get(key) or "").strip()
        if not data["domain"]:
            raise ValidationError("Feishu domain cannot be empty")
        write_saved_feishu_config(self._services.settings.workdir, data)
        return self._build_feishu_config_response()

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
        display_config["api_key"] = (
            saved.get("api_key") if isinstance(saved.get("api_key"), str) else ""
        )
        return LLMConfigResponse(
            config=LLMConfigPayload(**display_config),
            saved=self._mask_sensitive(saved),
            env=self._mask_sensitive(env),
            env_masked=self._mask_sensitive(env),
        )

    def _build_qq_config_response(self) -> QQBotConfigResponse:
        saved = read_saved_qq_config(self._services.settings.workdir)
        env = read_env_qq_config()
        display = self._merge_qq_config(saved, {})
        return QQBotConfigResponse(
            config=QQBotConfigPayload(**display),
            saved=self._mask_qq_sensitive(saved),
            env=self._mask_qq_sensitive(env),
            env_masked=self._mask_qq_sensitive(env),
        )

    def _build_feishu_config_response(self) -> FeishuBotConfigResponse:
        saved = read_saved_feishu_config(self._services.settings.workdir)
        env = read_env_feishu_config()
        display = self._merge_feishu_config(saved, {})
        return FeishuBotConfigResponse(
            config=FeishuBotConfigPayload(**display),
            saved=self._mask_feishu_sensitive(saved),
            env=self._mask_feishu_sensitive(env),
            env_masked=self._mask_feishu_sensitive(env),
        )

    def _mask_sensitive(self, config: dict) -> dict:
        masked = dict(config)
        value = masked.get("api_key")
        if isinstance(value, str) and value:
            masked["api_key"] = self._mask_secret(value)
        return masked

    def _mask_qq_sensitive(self, config: dict) -> dict:
        masked = dict(config)
        value = masked.get("secret")
        if isinstance(value, str) and value:
            masked["secret"] = self._mask_secret(value)
        return masked

    def _mask_feishu_sensitive(self, config: dict) -> dict:
        masked = dict(config)
        for key in ("app_secret", "verification_token", "encrypt_key"):
            value = masked.get(key)
            if isinstance(value, str) and value:
                masked[key] = self._mask_secret(value)
        return masked

    def _merge_qq_config(self, saved: dict, env: dict) -> dict:
        data = {
            "app_id": "",
            "secret": "",
            "sandbox": False,
            "timeout": 5,
            "enable_guild": True,
            "enable_direct": True,
            "enable_group": True,
            "enable_c2c": True,
            "enable_markdown": True,
        }
        data.update(saved)
        data.update(self._normalize_qq_env(env))
        return data

    def _normalize_qq_env(self, env: dict) -> dict:
        normalized = dict(env)
        for key in (
            "sandbox",
            "enable_guild",
            "enable_direct",
            "enable_group",
            "enable_c2c",
        ):
            value = normalized.get(key)
            if isinstance(value, str):
                normalized[key] = value.strip().lower() in {
                    "1",
                    "true",
                    "yes",
                    "y",
                    "on",
                }
        timeout = normalized.get("timeout")
        if isinstance(timeout, str) and timeout.strip():
            normalized["timeout"] = int(timeout)
        return normalized

    def _merge_feishu_config(self, saved: dict, env: dict) -> dict:
        data = {
            "app_id": "",
            "app_secret": "",
            "verification_token": "",
            "encrypt_key": "",
            "domain": "https://open.feishu.cn",
            "auto_reconnect": True,
        }
        data.update(saved)
        data.update(self._normalize_feishu_env(env))
        return data

    def _normalize_feishu_env(self, env: dict) -> dict:
        normalized = dict(env)
        value = normalized.get("auto_reconnect")
        if isinstance(value, str):
            normalized["auto_reconnect"] = value.strip().lower() in {
                "1",
                "true",
                "yes",
                "y",
                "on",
            }
        return normalized

    def _mask_secret(self, value: str) -> str:
        if len(value) <= 8:
            return "****"
        return f"{value[:6]}...{value[-4:]}"
