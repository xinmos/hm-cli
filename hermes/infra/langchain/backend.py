from __future__ import annotations

from typing import Any, Iterable

from langchain.agents import create_agent
from langchain_core.messages import AIMessageChunk, HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_openai import ChatOpenAI

from hermes.app.ports import AgentEvent, Message, AgentBackend


class LangChainOpenAIBackend(AgentBackend):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        timeout: int | None = None,
        max_retries: int = 2,
        top_p: float = 1.0,
        streaming: bool = True,
    ):
        self._model = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            top_p=top_p,
            streaming=streaming,
            stream_usage=streaming,
        )
        self._last_token_usage = 0

    def stream(self, messages: list[Message], tools: list[Any] | None = None) -> Iterable[AgentEvent]:
        self._last_token_usage = 0
        lc_messages = self._to_langchain_messages(messages)

        if tools:
            agent = create_agent(self._model, tools)
            config = {"configurable": {"thread_id": "default_thread"}}
            inputs = {"messages": lc_messages}

            for msg, metadata in agent.stream(inputs, config=config, stream_mode="messages"):
                if isinstance(msg, ToolMessage):
                    yield AgentEvent(
                        event_type="tool_complete",
                        data={"tool_name": msg.name, "result": msg.content},
                    )

                if isinstance(msg, AIMessageChunk):
                    content = self._coerce_content_to_text(msg.content)
                    if content:
                        yield AgentEvent(event_type="content", data={"content": content})

                    # Track token usage from usage_metadata (stream_usage=True)
                    if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                        if isinstance(msg.usage_metadata, dict):
                            total = msg.usage_metadata.get("total_tokens")
                        else:
                            total = getattr(msg.usage_metadata, "total_tokens", None)
                        if total and total != self._last_token_usage:
                            delta = total - self._last_token_usage
                            self._last_token_usage = total
                            yield AgentEvent(event_type="token_usage", data={"tokens": delta})
        else:
            for chunk in self._model.stream(lc_messages):
                content = self._coerce_content_to_text(chunk.content)
                if content:
                    yield AgentEvent(event_type="content", data={"content": content})

                # Track token usage from response_metadata
                if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                    if isinstance(chunk.usage_metadata, dict):
                        total = chunk.usage_metadata.get("total_tokens")
                    else:
                        total = getattr(chunk.usage_metadata, "total_tokens", None)
                    if total and total != self._last_token_usage:
                        delta = total - self._last_token_usage
                        self._last_token_usage = total
                        yield AgentEvent(event_type="token_usage", data={"tokens": delta})

    def _to_langchain_messages(self, messages: list[Message]) -> list:
        result = []
        for msg in messages:
            if msg.role == "system":
                result.append(SystemMessage(content=msg.content))
            elif msg.role == "user":
                result.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                result.append(AIMessage(content=msg.content))
        return result

    def _coerce_content_to_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if not isinstance(item, dict):
                    continue

                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                    continue

                # Some providers nest text under content fragments.
                if item.get("type") == "text":
                    nested_text = item.get("content")
                    if isinstance(nested_text, str):
                        parts.append(nested_text)
            return "".join(parts)
        return ""

    def _format_tool_display(self, tool_name: str, args: dict) -> str:
        """Format tool call for display in a concise way"""
        if not args:
            return tool_name

        # Handle special tools
        if tool_name == "Bash":
            cmd = args.get("command", "")
            # Truncate long commands
            if len(cmd) > 40:
                cmd = cmd[:37] + "..."
            return f"Bash({cmd})"
        elif tool_name == "Read":
            path = args.get("file_path", "")
            # Get only filename for brevity
            if "/" in path:
                path = path.split("/")[-1]
            return f"Read({path})"
        elif tool_name == "Write":
            path = args.get("file_path", "")
            if "/" in path:
                path = path.split("/")[-1]
            return f"Write({path})"
        elif tool_name == "Edit":
            path = args.get("file_path", "")
            if "/" in path:
                path = path.split("/")[-1]
            return f"Edit({path})"
        elif tool_name == "WebFetch":
            url = args.get("url", "")
            # Shorten URLs
            if len(url) > 30:
                url = url[:27] + "..."
            return f"WebFetch({url})"

        # Generic formatting for other tools
        args_str = ""
        for k, v in args.items():
            if k == "file_path" or k == "path":
                if "/" in str(v):
                    v = str(v).split("/")[-1]
            if args_str:
                args_str += f", {k}={v}"
            else:
                args_str = f"{k}={v}"

            if len(f"{tool_name}({args_str})") > 50:
                args_str += ", ..."
                break

        return f"{tool_name}({args_str})"
