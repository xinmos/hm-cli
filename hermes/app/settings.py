from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import orjson
from dotenv import load_dotenv

from hermes.app.llm_config import LLMConfig, load_effective_llm_config


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_base_url: str
    model_name: str
    temperature: float
    max_tokens: int
    timeout: int
    max_retries: int
    top_p: float
    streaming: bool
    custom_models: list[str]
    workdir: Path
    max_output_size: int
    max_output_lines: int
    command_timeout: int
    strict_sandbox: bool
    context_threshold: int
    context_max_messages: int
    tasks_path: Path
    context_window: int
    llm_wiki_path: Path

    @classmethod
    def from_env_and_args(
        cls,
        env_file: Path | None = None,
        cli_args: dict[str, Any] | None = None,
    ) -> "Settings":
        if env_file and env_file.exists():
            load_dotenv(env_file)
        else:
            load_dotenv()

        workdir = Path(os.getenv("HERMES_WORKDIR", ".")).resolve()
        llm_config = load_effective_llm_config(workdir)
        app_config = _read_persistent_app_config(workdir)

        return cls(
            openai_api_key=llm_config.api_key or "",
            openai_base_url=llm_config.base_url or "",
            model_name=llm_config.model,
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens,
            timeout=llm_config.timeout,
            max_retries=llm_config.max_retries,
            top_p=llm_config.top_p,
            streaming=llm_config.streaming,
            custom_models=llm_config.custom_models or [],
            workdir=workdir,
            max_output_size=int(os.getenv("HERMES_MAX_OUTPUT", "50000")),
            max_output_lines=int(os.getenv("HERMES_MAX_LINES", "500")),
            command_timeout=int(os.getenv("HERMES_TIMEOUT", "120")),
            strict_sandbox=os.getenv("HERMES_STRICT", "true").lower() == "true",
            context_threshold=int(os.getenv("HERMES_CONTEXT_THRESHOLD", "30")),
            context_max_messages=int(os.getenv("HERMES_CONTEXT_MAX", "50")),
            tasks_path=Path(os.getenv("HERMES_TASKS_PATH", workdir / ".hermes" / "tasks.json")),
            context_window=int(os.getenv("CONTEXT_WINDOW", "256")) * 1024,
            llm_wiki_path=_resolve_llm_wiki_path(workdir, app_config),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "openai_api_key": self.openai_api_key,
            "openai_base_url": self.openai_base_url,
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "top_p": self.top_p,
            "streaming": self.streaming,
            "custom_models": self.custom_models,
            "workdir": str(self.workdir),
            "max_output_size": self.max_output_size,
            "max_output_lines": self.max_output_lines,
            "command_timeout": self.command_timeout,
            "strict_sandbox": self.strict_sandbox,
            "context_threshold": self.context_threshold,
            "context_max_messages": self.context_max_messages,
            "tasks_path": str(self.tasks_path),
            "context_window": self.context_window,
            "llm_wiki_path": str(self.llm_wiki_path),
        }

    def with_llm_config(self, config: LLMConfig) -> "Settings":
        normalized = config.normalized()
        return replace(
            self,
            openai_api_key=normalized.api_key or "",
            openai_base_url=normalized.base_url or "",
            model_name=normalized.model,
            temperature=normalized.temperature,
            max_tokens=normalized.max_tokens,
            timeout=normalized.timeout,
            max_retries=normalized.max_retries,
            top_p=normalized.top_p,
            streaming=normalized.streaming,
            custom_models=normalized.custom_models or [],
        )

    def with_llm_wiki_path(self, path: Path) -> "Settings":
        return replace(self, llm_wiki_path=path.resolve())


def _read_persistent_app_config(workdir: Path) -> dict[str, Any]:
    path = workdir / ".hermes" / "settings.json"
    if not path.exists():
        return {}
    try:
        raw = orjson.loads(path.read_bytes())
    except orjson.JSONDecodeError:
        return {}
    if not isinstance(raw, dict):
        return {}
    return raw


def _resolve_llm_wiki_path(workdir: Path, app_config: dict[str, Any]) -> Path:
    configured_path = os.getenv("HERMES_LLM_WIKI_PATH") or os.getenv("LLM_WIKI_PATH")

    if configured_path is None:
        llm_wiki_config = app_config.get("llm_wiki")
        if isinstance(llm_wiki_config, dict):
            raw_path = llm_wiki_config.get("path")
            if isinstance(raw_path, str) and raw_path.strip():
                configured_path = raw_path

    if configured_path is None:
        raw_path = app_config.get("llm_wiki_path")
        if isinstance(raw_path, str) and raw_path.strip():
            configured_path = raw_path

    if configured_path is None:
        return (workdir / ".hermes" / "llm-wiki").resolve()

    expanded = Path(os.path.expandvars(os.path.expanduser(configured_path)))
    if expanded.is_absolute():
        return expanded.resolve()
    return (workdir / expanded).resolve()
