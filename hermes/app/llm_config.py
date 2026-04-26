from __future__ import annotations

import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import orjson


DEFAULT_CUSTOM_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "deepseek-chat",
    "qwen-max",
    "doubao-seed-2.0",
    "llama-model",
]


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "openai-compatible"
    api_key: str | None = "sk-no-key-required"
    base_url: str | None = "http://192.168.1.7:8081/v1"
    model: str = "llama-model"
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout: int = 60
    max_retries: int = 2
    top_p: float = 1.0
    streaming: bool = True
    custom_models: list[str] | None = None

    def normalized(self) -> "LLMConfig":
        custom_models = normalize_model_list(self.custom_models or [])
        if self.model and self.model not in custom_models:
            custom_models = [self.model, *custom_models]
        return replace(
            self,
            temperature=min(2.0, max(0.0, float(self.temperature))),
            max_tokens=max(1, int(self.max_tokens)),
            timeout=max(1, int(self.timeout)),
            max_retries=max(0, int(self.max_retries)),
            top_p=min(1.0, max(0.0, float(self.top_p))),
            streaming=bool(self.streaming),
            custom_models=custom_models,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())


def default_llm_config() -> LLMConfig:
    return LLMConfig(custom_models=DEFAULT_CUSTOM_MODELS).normalized()


def llm_settings_path(workdir: Path) -> Path:
    return workdir / ".hermes" / "settings.json"


def normalize_model_list(models: list[str] | tuple[str, ...]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for model in models:
        value = str(model).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def merge_llm_configs(*configs: dict[str, Any]) -> LLMConfig:
    data = default_llm_config().to_dict()
    for config in configs:
        for key, value in config.items():
            if key not in data or value is None:
                continue
            if isinstance(value, str) and value == "":
                continue
            data[key] = value
    return LLMConfig(**data).normalized()


def read_llm_env() -> dict[str, Any]:
    data: dict[str, Any] = {}
    mappings = {
        "api_key": ("OPENAI_API_KEY",),
        "base_url": ("OPENAI_BASE_URL", "OPENAI_API_BASE"),
        "model": ("MODEL_NAME", "OPENAI_MODEL"),
        "temperature": ("TEMPERATURE",),
        "max_tokens": ("MAX_TOKENS",),
        "timeout": ("OPENAI_TIMEOUT", "REQUEST_TIMEOUT"),
        "max_retries": ("OPENAI_MAX_RETRIES", "MAX_RETRIES"),
        "top_p": ("TOP_P",),
        "streaming": ("OPENAI_STREAMING", "STREAMING"),
        "custom_models": ("HERMES_CUSTOM_MODELS", "CUSTOM_MODELS"),
    }
    for field, names in mappings.items():
        raw = next((os.getenv(name) for name in names if os.getenv(name) is not None), None)
        if raw is None:
            continue
        data[field] = _coerce_env_value(field, raw)
    return data


def read_persistent_llm_config(workdir: Path) -> dict[str, Any]:
    path = llm_settings_path(workdir)
    if not path.exists():
        return {}
    try:
        raw = orjson.loads(path.read_bytes())
    except orjson.JSONDecodeError:
        return {}
    if not isinstance(raw, dict):
        return {}
    llm = raw.get("llm", raw)
    if not isinstance(llm, dict):
        return {}
    return _filter_config_dict(llm)


def write_persistent_llm_config(workdir: Path, config: LLMConfig) -> None:
    path = llm_settings_path(workdir)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            parsed = orjson.loads(path.read_bytes())
            if isinstance(parsed, dict):
                existing = parsed
        except orjson.JSONDecodeError:
            existing = {}
    existing["llm"] = config.to_dict()
    path.write_bytes(orjson.dumps(existing, option=orjson.OPT_INDENT_2))


def load_effective_llm_config(workdir: Path) -> LLMConfig:
    return merge_llm_configs(read_llm_env(), read_persistent_llm_config(workdir))


def parse_env_text(text: str) -> dict[str, Any]:
    env_values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        value = raw_value.strip().strip("'\"")
        env_values[key.strip()] = value

    data: dict[str, Any] = {}
    reverse = {
        "OPENAI_API_KEY": "api_key",
        "OPENAI_BASE_URL": "base_url",
        "OPENAI_API_BASE": "base_url",
        "MODEL_NAME": "model",
        "OPENAI_MODEL": "model",
        "TEMPERATURE": "temperature",
        "MAX_TOKENS": "max_tokens",
        "OPENAI_TIMEOUT": "timeout",
        "REQUEST_TIMEOUT": "timeout",
        "OPENAI_MAX_RETRIES": "max_retries",
        "MAX_RETRIES": "max_retries",
        "TOP_P": "top_p",
        "OPENAI_STREAMING": "streaming",
        "STREAMING": "streaming",
        "HERMES_CUSTOM_MODELS": "custom_models",
        "CUSTOM_MODELS": "custom_models",
    }
    for env_key, value in env_values.items():
        field = reverse.get(env_key)
        if field:
            data[field] = _coerce_env_value(field, value)
    return data


def format_env_text(config: LLMConfig) -> str:
    data = config.normalized()
    lines = [
        ("OPENAI_API_KEY", data.api_key or ""),
        ("OPENAI_BASE_URL", data.base_url or ""),
        ("MODEL_NAME", data.model),
        ("TEMPERATURE", data.temperature),
        ("MAX_TOKENS", data.max_tokens),
        ("OPENAI_TIMEOUT", data.timeout),
        ("OPENAI_MAX_RETRIES", data.max_retries),
        ("TOP_P", data.top_p),
        ("OPENAI_STREAMING", str(data.streaming).lower()),
        ("HERMES_CUSTOM_MODELS", ",".join(data.custom_models or [])),
    ]
    return "\n".join(f"{key}={_format_env_value(value)}" for key, value in lines) + "\n"


def _filter_config_dict(config: dict[str, Any]) -> dict[str, Any]:
    allowed = set(default_llm_config().to_dict())
    return {key: value for key, value in config.items() if key in allowed}


def _coerce_env_value(field: str, raw: str) -> Any:
    value = raw.strip()
    if field in {"temperature", "top_p"}:
        return float(value)
    if field in {"max_tokens", "timeout", "max_retries"}:
        return int(value)
    if field == "streaming":
        return value.lower() in {"1", "true", "yes", "on"}
    if field == "custom_models":
        return normalize_model_list(value.split(","))
    return value


def _format_env_value(value: object) -> str:
    text = str(value)
    if not text or any(char.isspace() for char in text):
        return f'"{text}"'
    return text
