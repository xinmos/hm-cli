import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_base_url: str
    model_name: str
    temperature: float
    max_tokens: int
    workdir: Path
    max_output_size: int
    max_output_lines: int
    command_timeout: int
    strict_sandbox: bool
    context_threshold: int
    context_max_messages: int
    tasks_path: Path
    context_window: int

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

        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", "sk-no-key-required"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "http://192.168.1.7:8081/v1"),
            model_name=os.getenv("MODEL_NAME", "llama-model"),
            temperature=float(os.getenv("TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("MAX_TOKENS", "2048")),
            workdir=workdir,
            max_output_size=int(os.getenv("HERMES_MAX_OUTPUT", "50000")),
            max_output_lines=int(os.getenv("HERMES_MAX_LINES", "500")),
            command_timeout=int(os.getenv("HERMES_TIMEOUT", "120")),
            strict_sandbox=os.getenv("HERMES_STRICT", "true").lower() == "true",
            context_threshold=int(os.getenv("HERMES_CONTEXT_THRESHOLD", "30")),
            context_max_messages=int(os.getenv("HERMES_CONTEXT_MAX", "50")),
            tasks_path=Path(os.getenv("HERMES_TASKS_PATH", workdir / ".hermes" / "tasks.json")),
            context_window=int(os.getenv("CONTEXT_WINDOW", "256")) * 1024,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "openai_api_key": self.openai_api_key,
            "openai_base_url": self.openai_base_url,
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "workdir": str(self.workdir),
            "max_output_size": self.max_output_size,
            "max_output_lines": self.max_output_lines,
            "command_timeout": self.command_timeout,
            "strict_sandbox": self.strict_sandbox,
            "context_threshold": self.context_threshold,
            "context_max_messages": self.context_max_messages,
            "tasks_path": str(self.tasks_path),
            "context_window": self.context_window,
        }
