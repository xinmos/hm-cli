from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Protocol


@dataclass
class Message:
    role: str
    content: str


@dataclass
class AgentEvent:
    event_type: str
    data: dict[str, Any]


class AgentBackend(Protocol):
    def stream(self, messages: list[Message], tools: list[Any] | None = None) -> Iterable[AgentEvent]:
        """Stream agent events given messages and optional tools"""
        ...


class LLMClient(Protocol):
    def invoke(self, messages: list[Message]) -> str:
        """Invoke LLM and return response text"""
        ...


@dataclass
class SkillInfo:
    name: str
    description: str
    version: str
    slash_command: str
    instructions: str
    metadata: dict[str, Any]


class SkillRepository(Protocol):
    def get(self, name: str) -> SkillInfo | None:
        """Get skill by name"""
        ...

    def get_by_slash_command(self, cmd: str) -> SkillInfo | None:
        """Get skill by slash command"""
        ...

    def list_skills(self) -> list[SkillInfo]:
        """List all available skills"""
        ...

    def is_slash_command(self, cmd: str) -> bool:
        """Check if command is a registered slash command"""
        ...

    def get_active_skill(self) -> SkillInfo | None:
        """Get the currently active skill, if any.

        Returns the skill that is currently controlling the agent's behavior,
        or None if no skill is active.
        """
        ...


@dataclass
class TaskInfo:
    id: str
    name: str
    trigger_type: str
    trigger_expr: str
    action: str
    enabled: bool


@dataclass
class ChatSummary:
    id: str
    title: str
    project_id: str | None
    created_at: str
    updated_at: str
    message_count: int


@dataclass
class ChatMessageRecord:
    id: str
    role: str
    content: str
    created_at: str
    tool_calls: list[Any] | None = None


class TaskStore(Protocol):
    def load_all(self) -> list[TaskInfo]:
        """Load all tasks from storage"""
        ...

    def save_all(self, tasks: list[TaskInfo]) -> None:
        """Save all tasks to storage"""
        ...


class ChatStore(Protocol):
    def list_chats(self) -> list[ChatSummary]:
        """Return chat summaries sorted by most recent first."""
        ...

    def create_chat(self, title: str, project_id: str | None = None) -> ChatSummary:
        """Create and persist a new chat."""
        ...

    def list_messages(self, chat_id: str) -> list[ChatMessageRecord]:
        """Return all messages for a chat."""
        ...

    def append_message(self, chat_id: str, message: ChatMessageRecord) -> None:
        """Append a single message to a chat."""
        ...

    def delete_chat(self, chat_id: str) -> None:
        """Delete a chat and all of its messages."""
        ...

    def rename_chat(self, chat_id: str, title: str) -> ChatSummary | None:
        """Rename a chat and return the updated summary."""
        ...


class ToolCatalog(Protocol):
    def get_tools(self) -> list[Any]:
        """Get all available tools"""
        ...

    def get_tool(self, name: str) -> Any | None:
        """Get tool by name"""
        ...


class InteractionPort(Protocol):
    def confirm(self, tool_name: str, description: str, tool_display: str = "") -> bool:
        """Ask user to confirm dangerous operation"""
        ...

    def notify_tool_start(self, tool_name: str, tool_display: str = "") -> None:
        """Notify that tool execution started"""
        ...

    def notify_tool_complete(self, tool_name: str, result: Any = None) -> None:
        """Notify that tool execution completed"""
        ...

    def notify_tool_error(self, tool_name: str, error: str) -> None:
        """Notify that tool execution failed"""
        ...

    def on_context_compressed(self, original: int, compressed: int) -> None:
        """Notify that context was compressed"""
        ...


class SchedulerDriver(Protocol):
    def start(self) -> None:
        """Start the scheduler"""
        ...

    def shutdown(self) -> None:
        """Shutdown the scheduler"""
        ...

    def add_job(
        self,
        job_id: str,
        trigger_type: str,
        trigger_expr: str,
        callback: Callable[[], None],
    ) -> None:
        """Add a scheduled job"""
        ...

    def remove_job(self, job_id: str) -> None:
        """Remove a scheduled job"""
        ...

    def pause_job(self, job_id: str) -> None:
        """Pause a scheduled job"""
        ...

    def resume_job(self, job_id: str) -> None:
        """Resume a scheduled job"""
        ...
