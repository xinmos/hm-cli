from typing import Any, Iterable

from langchain.agents import create_agent
from langchain_core.messages import AIMessageChunk, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from hermes.app.ports import AgentEvent, Message, AgentBackend


class LangChainOpenAIBackend(AgentBackend):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        temperature: float = 0.7,
    ):
        self._model = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            temperature=temperature,
            streaming=True,
        )

    def stream(self, messages: list[Message], tools: list[Any] | None = None) -> Iterable[AgentEvent]:
        lc_messages = self._to_langchain_messages(messages)

        if tools:
            agent = create_agent(self._model, tools)
            config = {"configurable": {"thread_id": "default_thread"}}
            inputs = {"messages": lc_messages}

            for msg, metadata in agent.stream(inputs, config=config, stream_mode="messages"):
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        tool_name = tool_call.get("name", "unknown")
                        yield AgentEvent(event_type="tool_start", data={"tool_name": tool_name})

                if isinstance(msg, ToolMessage):
                    yield AgentEvent(
                        event_type="tool_complete",
                        data={"tool_name": msg.name, "result": msg.content},
                    )

                if isinstance(msg, AIMessageChunk):
                    content = msg.content
                    if content:
                        yield AgentEvent(event_type="content", data={"content": content})
        else:
            for chunk in self._model.stream(lc_messages):
                content = chunk.content
                if content:
                    yield AgentEvent(event_type="content", data={"content": content})

    def _to_langchain_messages(self, messages: list[Message]) -> list:
        from langchain_core.messages import AIMessage

        result = []
        for msg in messages:
            if msg.role == "system":
                result.append(SystemMessage(content=msg.content))
            elif msg.role == "user":
                result.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                result.append(AIMessage(content=msg.content))
        return result
