from __future__ import annotations

from threading import Lock
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from hermes.app.llm_config import (
    LLMConfig,
    format_env_text,
    merge_llm_configs,
    parse_env_text,
    read_llm_env,
    read_persistent_llm_config,
    write_persistent_llm_config,
)
from hermes.app.settings import Settings


class LLMConfigService:
    def __init__(self, settings: Settings):
        self._base_settings = settings
        self._workdir = settings.workdir
        self._lock = Lock()
        self._saved_config = read_persistent_llm_config(self._workdir)
        self._env_config = read_llm_env()
        self._effective_config = merge_llm_configs(self._env_config, self._saved_config)

    def get_effective_config(self) -> LLMConfig:
        with self._lock:
            return self._effective_config

    def get_saved_config(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._saved_config)

    def get_env_config(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._env_config)

    def build_settings(self) -> Settings:
        with self._lock:
            config = self._effective_config
        return self._base_settings.with_llm_config(config)

    def update_config(self, data: dict[str, Any]) -> LLMConfig:
        with self._lock:
            self._saved_config = LLMConfig(**data).normalized().to_dict()
            self._effective_config = merge_llm_configs(self._env_config, self._saved_config)
            write_persistent_llm_config(self._workdir, LLMConfig(**self._saved_config))
            return self._effective_config

    def import_env(self, text: str) -> LLMConfig:
        imported = parse_env_text(text)
        with self._lock:
            self._saved_config = merge_llm_configs(self._saved_config, imported).to_dict()
            self._effective_config = merge_llm_configs(self._env_config, self._saved_config)
            write_persistent_llm_config(self._workdir, LLMConfig(**self._saved_config))
            return self._effective_config

    def export_env(self) -> str:
        return format_env_text(self.get_effective_config())

    def test_connection(self, data: dict[str, Any] | None = None) -> str:
        config = self.get_effective_config()
        if data:
            config = merge_llm_configs(config.to_dict(), data)
        model = _create_chat_model(config)
        response = model.invoke([HumanMessage(content="hi")])
        content = response.content
        if isinstance(content, str):
            return content
        return str(content)


def _create_chat_model(config: LLMConfig) -> ChatOpenAI:
    normalized = config.normalized()
    return ChatOpenAI(
        api_key=normalized.api_key,
        base_url=normalized.base_url,
        model=normalized.model,
        temperature=normalized.temperature,
        max_tokens=normalized.max_tokens,
        request_timeout=normalized.timeout,
        max_retries=normalized.max_retries,
        top_p=normalized.top_p,
        streaming=False,
    )
