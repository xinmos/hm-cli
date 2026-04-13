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

    def set_interaction_port(self, port: InteractionPort) -> None:
        self._interaction_port = port

    def run_stream(self, user_input: str) -> Iterable[str]:
        self._messages.append(Message(role="user", content=user_input))

        events = self._backend.stream(self._messages, self._tools)

        full_response = ""
        for event in events:
            if event.event_type == "tool_start":
                if self._interaction_port:
                    self._interaction_port.notify_tool_start(event.data.get("tool_name", "unknown"))
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

        if full_response:
            self._messages.append(Message(role="assistant", content=full_response))

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

    def get_message_count(self) -> int:
        return len(self._messages)

    def get_messages(self) -> list[Message]:
        return list(self._messages)

    def set_messages(self, messages: list[Message]) -> None:
        self._messages = list(messages)
