from dataclasses import dataclass
from typing import List, Optional

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI

from hermes.config import Config


@dataclass
class CompressionResult:
    original_count: int
    compressed_count: int
    summary: str
    preserved_messages: List[BaseMessage]


class ContextCompressor:
    def __init__(
        self,
        model: Optional[ChatOpenAI] = None,
        max_messages: int = 50,
        compression_threshold: int = 30,
    ):
        self.model = model or ChatOpenAI(
            api_key=Config.OPENAI_API_KEY,
            base_url=Config.OPENAI_BASE_URL,
            model=Config.MODEL_NAME,
            temperature=0.3,
        )
        self.max_messages = max_messages
        self.compression_threshold = compression_threshold

    def should_compress(self, messages: List[BaseMessage]) -> bool:
        return len(messages) > self.compression_threshold

    def compress(self, messages: List[BaseMessage]) -> CompressionResult:
        if len(messages) <= 10:
            return CompressionResult(
                original_count=len(messages),
                compressed_count=len(messages),
                summary="",
                preserved_messages=messages,
            )

        # Keep first system message and recent messages
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        recent_msgs = messages[-10:]  # Keep last 10 messages

        # Middle section to compress
        middle_start = len(system_msgs)
        middle_end = len(messages) - 10

        if middle_end <= middle_start:
            return CompressionResult(
                original_count=len(messages),
                compressed_count=len(messages),
                summary="",
                preserved_messages=messages,
            )

        middle_msgs = messages[middle_start:middle_end]

        # Generate summary
        summary = self._summarize_messages(middle_msgs)

        # Build compressed message list
        compressed = []
        if system_msgs:
            compressed.extend(system_msgs[:1])  # Keep first system message

        compressed.append(SystemMessage(content=f"[Conversation Summary] {summary}"))
        compressed.extend(recent_msgs)

        return CompressionResult(
            original_count=len(messages),
            compressed_count=len(compressed),
            summary=summary,
            preserved_messages=compressed,
        )

    def _summarize_messages(self, messages: List[BaseMessage]) -> str:
        conversation_text = ""
        for msg in messages:
            if isinstance(msg, HumanMessage):
                conversation_text += f"User: {msg.content}\n"
            elif isinstance(msg, AIMessage):
                conversation_text += f"Assistant: {msg.content}\n"
            elif isinstance(msg, ToolMessage):
                conversation_text += f"Tool ({msg.name}): {msg.content[:200]}...\n"

        prompt = f"""Summarize this conversation history concisely, preserving key facts, decisions, and context:

{conversation_text}

Provide a brief summary (2-3 sentences max) of what was discussed and any important conclusions."""

        try:
            response = self.model.invoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as e:
            return f"[Failed to generate summary: {e}]"

    def smart_compress(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        if not self.should_compress(messages):
            return messages

        result = self.compress(messages)
        return result.preserved_messages


class ContextManager:
    def __init__(
        self,
        compressor: Optional[ContextCompressor] = None,
        max_tokens: int = 8000,
    ):
        self.compressor = compressor or ContextCompressor()
        self.max_tokens = max_tokens
        self._messages: List[BaseMessage] = []

    def add_message(self, message: BaseMessage) -> None:
        self._messages.append(message)

        # Auto-compress if needed
        if self.compressor.should_compress(self._messages):
            self._messages = self.compressor.smart_compress(self._messages)

    def get_messages(self) -> List[BaseMessage]:
        return self._messages.copy()

    def clear(self) -> None:
        self._messages.clear()

    def compress_now(self) -> CompressionResult:
        result = self.compressor.compress(self._messages)
        self._messages = result.preserved_messages
        return result
