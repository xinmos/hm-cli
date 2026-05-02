from __future__ import annotations

import os
from pathlib import Path
from threading import Lock
from typing import Any

from langchain_core.messages import HumanMessage
import orjson
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
from hermes.services.llm_wiki_workspace import initialize_llm_wiki, inspect_llm_wiki


class LLMConfigService:
    def __init__(self, settings: Settings):
        self._base_settings = settings
        self._workdir = settings.workdir
        self._lock = Lock()
        self._saved_config = read_persistent_llm_config(self._workdir)
        self._env_config = read_llm_env()
        self._effective_config = merge_llm_configs(self._env_config, self._saved_config)
        self._llm_wiki_path = settings.llm_wiki_path

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
            llm_wiki_path = self._llm_wiki_path
        return self._base_settings.with_llm_config(config).with_llm_wiki_path(llm_wiki_path)

    def get_wiki_config(self) -> dict[str, Any]:
        with self._lock:
            return self._build_wiki_config_no_lock()

    def update_wiki_config(self, path: str) -> dict[str, Any]:
        normalized_path = path.strip()
        if not normalized_path:
            raise ValueError("llm-wiki path cannot be empty")

        with self._lock:
            self._write_saved_wiki_path(normalized_path)
            self._llm_wiki_path = self._resolve_wiki_path(normalized_path)
            return self._build_wiki_config_no_lock()

    def initialize_wiki(self, path: str | None = None) -> dict[str, Any]:
        with self._lock:
            if path is not None:
                normalized_path = path.strip()
                if not normalized_path:
                    raise ValueError("llm-wiki path cannot be empty")
                self._write_saved_wiki_path(normalized_path)
                self._llm_wiki_path = self._resolve_wiki_path(normalized_path)

            result = initialize_llm_wiki(self._llm_wiki_path)
            config = self._build_wiki_config_no_lock()
            config["init_result"] = result.to_dict()
            return config

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

    def _build_wiki_config_no_lock(self) -> dict[str, Any]:
        saved_path = self._read_saved_wiki_path()
        env_path = self._read_env_wiki_path()
        default_path = self._workdir / ".hermes" / "llm-wiki"
        status = inspect_llm_wiki(self._llm_wiki_path)
        return {
            "path": env_path or saved_path or str(default_path),
            "effective_path": str(self._llm_wiki_path),
            "default_path": str(default_path),
            "saved_path": saved_path,
            "env_path": env_path,
            "exists": status.exists,
            "is_directory": status.is_directory,
            "is_initialized": status.is_initialized,
            "missing_items": status.missing_items,
            "status_message": status.message,
        }

    def _read_env_wiki_path(self) -> str | None:
        value = os.getenv("HERMES_LLM_WIKI_PATH") or os.getenv("LLM_WIKI_PATH")
        if isinstance(value, str) and value.strip():
            return value
        return None

    def _read_settings_file(self) -> dict[str, Any]:
        path = self._workdir / ".hermes" / "settings.json"
        if not path.exists():
            return {}
        try:
            parsed = orjson.loads(path.read_bytes())
        except orjson.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed

    def _write_settings_file(self, data: dict[str, Any]) -> None:
        path = self._workdir / ".hermes" / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))

    def _read_saved_wiki_path(self) -> str | None:
        settings = self._read_settings_file()
        llm_wiki = settings.get("llm_wiki")
        if isinstance(llm_wiki, dict):
            path = llm_wiki.get("path")
            if isinstance(path, str) and path.strip():
                return path
        path = settings.get("llm_wiki_path")
        if isinstance(path, str) and path.strip():
            return path
        return None

    def _write_saved_wiki_path(self, path: str) -> None:
        settings = self._read_settings_file()
        llm_wiki = settings.get("llm_wiki")
        if not isinstance(llm_wiki, dict):
            llm_wiki = {}
        llm_wiki["path"] = path
        settings["llm_wiki"] = llm_wiki
        settings.pop("llm_wiki_path", None)
        self._write_settings_file(settings)

    def _resolve_wiki_path(self, path: str) -> Path:
        env_path = self._read_env_wiki_path()
        raw_path = env_path or path
        expanded = Path(os.path.expandvars(os.path.expanduser(raw_path)))
        if expanded.is_absolute():
            return expanded.resolve()
        return (self._workdir / expanded).resolve()


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
