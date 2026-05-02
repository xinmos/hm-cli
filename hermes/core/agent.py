from __future__ import annotations

from typing import Any, Iterable

from hermes.app.ports import AgentBackend, InteractionPort, Message


class AgentSession:
    def __init__(
        self,
        backend: AgentBackend,
        system_prompt: str = "",
        interaction_port: InteractionPort | None = None,
    ):
        self._backend = backend
        self._system_prompt = system_prompt
        self._interaction_port = interaction_port
        self._messages: list[Message] = []
        self._tools: list[Any] = []
        self._total_tokens = 0

        if system_prompt:
            self._messages.append(Message(role="system", content=system_prompt))

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

    def run_stream(self, user_input: str) -> Iterable[str]:
        self._messages.append(Message(role="user", content=user_input))
        yield from self._execute_stream(self._messages)

    def run_stream_with_messages(self, user_input: str, messages: list[Message]) -> Iterable[str]:
        msgs = list(messages)
        msgs.append(Message(role="user", content=user_input))

        yield from self._execute_stream(msgs)

        self._messages = list(msgs)

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

    def get_message_count(self) -> int:
        return len(self._messages)

    def get_token_count(self) -> int:
        # Return actual tracked token usage from backend
        return self._total_tokens

    def reset_token_count(self) -> None:
        self._total_tokens = 0

    def _estimate_tokens(self, text: str) -> int:
        """Roughly estimate tokens from text length.
        English: ~4 chars per token, Chinese: ~1-2 chars per token.
        We use a weighted average.
        """
        if not text:
            return 0

        # Count Chinese characters
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        # Count non-Chinese characters
        other_chars = len(text) - chinese_chars

        # Chinese: ~1.5 chars per token, Other: ~4 chars per token
        return int(chinese_chars / 1.5 + other_chars / 4)
