from __future__ import annotations

import uuid
from typing import Any, Iterable

from hermes.app.ports import AgentBackend, InteractionPort, Message


class AgentSession:
    def __init__(
        self,
        backend: AgentBackend,
        system_prompt: str = "",
        interaction_port: InteractionPort | None = None,
        context_window: int = 256 * 1024,
    ):
        self._backend = backend
        self._system_prompt = system_prompt
        self._interaction_port = interaction_port
        self._messages: list[Message] = []
        self._tools: list[Any] = []
        self._total_tokens = 0
        self._context_window = context_window
        self._session_id = str(uuid.uuid4())
        self._context_note: str | None = None

        if system_prompt:
            self._messages.append(Message(role="system", content=system_prompt))

    @property
    def session_id(self) -> str:
        return self._session_id

    def set_system_prompt(self, prompt: str) -> None:
        self._system_prompt = prompt
        for i, msg in enumerate(self._messages):
            if msg.role == "system":
                self._messages[i] = Message(role="system", content=prompt)
                return
        self._messages.insert(0, Message(role="system", content=prompt))

    def set_tools(self, tools: list[Any]) -> None:
        self._tools = tools

    def get_tool_count(self) -> int:
        return len(self._tools)

    def set_interaction_port(self, port: InteractionPort) -> None:
        self._interaction_port = port

    def prepend_context(self, note: str) -> None:
        """注入记忆上下文，作为下一条用户消息前的 system 消息。"""
        self._context_note = note

    def run_stream(self, user_input: str) -> Iterable[str]:
        self._auto_compact_if_needed()

        if self._context_note:
            self._messages.append(Message(role="system", content=self._context_note))
            self._context_note = None

        self._messages.append(Message(role="user", content=user_input))
        yield from self._execute_stream(self._messages)

    def _execute_stream(self, messages: list[Message]) -> Iterable[str]:
        events = self._backend.stream(messages, self._tools)

        full_response = ""
        for event in events:
            if event.event_type == "tool_start":
                if self._interaction_port:
                    tool_display = event.data.get("tool_display", "")
                    self._interaction_port.notify_tool_start(
                        event.data.get("tool_name", "unknown"),
                        tool_display
                    )
            elif event.event_type == "tool_complete":
                if self._interaction_port:
                    self._interaction_port.notify_tool_complete(
                        event.data.get("tool_name", "unknown"),
                        event.data.get("result"),
                    )
            elif event.event_type == "tool_error":
                if self._interaction_port:
                    self._interaction_port.notify_tool_error(
                        event.data.get("tool_name", "unknown"),
                        event.data.get("error", "unknown error"),
                    )
            elif event.event_type == "content":
                content = event.data.get("content", "")
                if content:
                    full_response += content
                    yield content
            elif event.event_type == "token_usage":
                tokens = event.data.get("tokens", 0)
                if tokens:
                    self._total_tokens += tokens

        if full_response:
            messages.append(Message(role="assistant", content=full_response))

    def get_messages(self) -> list[Message]:
        """获取当前消息列表的副本"""
        return list(self._messages)

    def load_history(self, history: list[Message]) -> None:
        system_msg: Message | None = None
        for msg in self._messages:
            if msg.role == "system":
                system_msg = msg
                break

        self._messages = []
        if system_msg:
            self._messages.append(system_msg)

        for msg in history:
            if msg.role == "system":
                continue
            self._messages.append(msg)

        self._total_tokens = 0

    def reset(self) -> None:
        system_msg: Message | None = None
        for msg in self._messages:
            if msg.role == "system":
                system_msg = msg
                break
        self._messages.clear()
        if system_msg:
            self._messages.append(system_msg)
        elif self._system_prompt:
            self._messages.append(Message(role="system", content=self._system_prompt))
        self._total_tokens = 0
        self._session_id = str(uuid.uuid4())

    def get_message_count(self) -> int:
        return len(self._messages)

    def get_token_count(self) -> int:
        return self._total_tokens

    def reset_token_count(self) -> None:
        self._total_tokens = 0

    def estimate_total_tokens(self) -> int:
        """估算消息列表的 token 总数"""
        total = 0
        for msg in self._messages:
            total += self._estimate_tokens(msg.content)
        return total

    def compact(self, strategy: str, max_keep: int = 20) -> int:
        """执行压缩，返回移除的消息数"""
        original = len(self._messages)
        if strategy == "prune":
            removed = self._prune(max_keep)
        elif strategy == "summarize":
            removed = self._summarize()
        elif strategy == "segment":
            removed = self._segment()
        else:
            return 0

        if self._interaction_port:
            self._interaction_port.on_context_compressed(original, len(self._messages))
        return removed

    def _prune(self, max_keep: int = 20) -> int:
        system = [m for m in self._messages if m.role == "system"]
        non_system = [m for m in self._messages if m.role != "system"]
        if len(non_system) <= max_keep:
            return 0
        kept = non_system[-max_keep:]
        self._messages = system + kept
        return len(non_system) - max_keep

    def _summarize(self) -> int:
        system = [m for m in self._messages if m.role == "system"]
        non_system = [m for m in self._messages if m.role != "system"]
        if len(non_system) <= 30:
            return 0

        split = len(non_system) // 2
        old = non_system[:split]
        recent = non_system[split:]

        convo = "\n".join(
            f"[{m.role}]: {m.content[:300]}" for m in old
        )
        summary_text = self._call_llm_for_summary(convo)

        summary_msg = Message(
            role="system",
            content=f"[上下文已压缩 — 更早的对话摘要]\n{summary_text}",
        )
        self._messages = system + [summary_msg] + recent
        return split

    def _segment(self) -> int:
        original = len(self._messages)
        self.reset()
        return original - len(self._messages)

    def _auto_compact_if_needed(self) -> None:
        threshold = int(self._context_window * 0.8)
        if self.estimate_total_tokens() > threshold:
            self.compact("prune")
            if self.estimate_total_tokens() > threshold:
                self.compact("summarize")

    def _call_llm_for_summary(self, conversation_text: str) -> str:
        prompt = (
            "Please provide a concise summary (under 500 tokens) of the following conversation. "
            "Capture key decisions, facts, code patterns, and user preferences. "
            "Respond ONLY with the summary, no preamble.\n\n"
            f"{conversation_text}"
        )
        messages = [Message(role="user", content=prompt)]
        full_text = ""
        for event in self._backend.stream(messages, tools=None):
            if event.event_type == "content":
                full_text += event.data.get("content", "")
        return full_text.strip()

    def _estimate_tokens(self, text: str) -> int:
        """Roughly estimate tokens from text length.
        English: ~4 chars per token, Chinese: ~1-2 chars per token.
        """
        if not text:
            return 0
        chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)
