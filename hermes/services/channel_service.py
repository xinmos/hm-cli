from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any
from uuid import uuid4

from hermes.app.ports import (
    ChannelConversationKey,
    ChannelConversationLink,
    ChannelConversationStore,
    ChannelInboundMessage,
    ChannelOutboundMessage,
    ChatMessageRecord,
    Message,
)
from hermes.services.chat_service import ChatService

ChannelResponder = Callable[[list[Message], str], Iterable[str]]


class ChannelConversationService:
    def __init__(
        self,
        chat_service: ChatService,
        link_store: ChannelConversationStore,
        responder: ChannelResponder,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self._chat_service = chat_service
        self._link_store = link_store
        self._responder = responder
        self._clock = clock or datetime.now

    def handle_inbound(self, message: ChannelInboundMessage) -> ChannelOutboundMessage:
        chunks = list(self.stream_inbound(message))
        if not chunks:
            raise RuntimeError("Channel response produced no output")

        final = chunks[-1]
        return ChannelOutboundMessage(
            channel=final.channel,
            conversation_id=final.conversation_id,
            text="".join(chunk.text for chunk in chunks),
            chat_id=final.chat_id,
            reply_to_message_id=final.reply_to_message_id,
            metadata=final.metadata,
        )

    def stream_inbound(
        self, message: ChannelInboundMessage
    ) -> Iterable[ChannelOutboundMessage]:
        inbound = self._normalize_message(message)
        if not inbound.channel:
            raise ValueError("Channel name cannot be empty")
        if not inbound.conversation_id:
            raise ValueError("Channel conversation id cannot be empty")
        if not inbound.sender_id:
            raise ValueError("Channel sender id cannot be empty")
        if not inbound.text:
            raise ValueError("Channel message text cannot be empty")

        link = self._ensure_link(inbound)
        history = self._build_agent_history(
            self._chat_service.list_messages(link.chat_id)
        )
        agent_input = self._format_agent_input(inbound)

        self._chat_service.append_message(
            link.chat_id,
            self._build_record(
                role="user",
                content=agent_input,
                metadata=self._message_metadata(inbound),
            ),
        )

        assistant_chunks: list[str] = []
        for chunk in self._responder(history, agent_input):
            if not chunk:
                continue
            assistant_chunks.append(chunk)
            yield ChannelOutboundMessage(
                channel=inbound.channel,
                conversation_id=inbound.conversation_id,
                text=chunk,
                chat_id=link.chat_id,
                reply_to_message_id=inbound.message_id,
                metadata={"sender_id": inbound.sender_id},
            )

        assistant_text = "".join(assistant_chunks)
        if assistant_text:
            self._chat_service.append_message(
                link.chat_id,
                self._build_record(
                    role="assistant",
                    content=assistant_text,
                    metadata={
                        "channel": inbound.channel,
                        "conversation_id": inbound.conversation_id,
                    },
                ),
            )

        self._touch_link(link)

    def list_conversations(
        self, channel: str | None = None
    ) -> list[ChannelConversationLink]:
        return self._link_store.list_links(channel)

    def _ensure_link(self, message: ChannelInboundMessage) -> ChannelConversationLink:
        key = ChannelConversationKey(
            channel=message.channel,
            conversation_id=message.conversation_id,
        )
        existing = self._link_store.get_link(key)
        if existing:
            return existing

        now = self._clock().isoformat()
        chat = self._chat_service.create_chat(
            title=f"{message.channel}:{message.conversation_id}",
            project_id=None,
        )
        link = ChannelConversationLink(
            channel=message.channel,
            conversation_id=message.conversation_id,
            chat_id=chat.id,
            created_at=now,
            updated_at=now,
            metadata={"created_by": "channel"},
        )
        self._link_store.save_link(link)
        return link

    def _touch_link(self, link: ChannelConversationLink) -> None:
        link.updated_at = self._clock().isoformat()
        self._link_store.save_link(link)

    def _build_record(
        self,
        role: str,
        content: str,
        metadata: dict[str, Any],
    ) -> ChatMessageRecord:
        return ChatMessageRecord(
            id=f"msg-{uuid4().hex[:12]}",
            role=role,
            content=content,
            created_at=self._clock().isoformat(),
            metadata=metadata,
        )

    def _build_agent_history(self, messages: list[ChatMessageRecord]) -> list[Message]:
        history: list[Message] = []
        for message in messages:
            if message.role not in {"user", "assistant", "system"}:
                continue
            history.append(Message(role=message.role, content=message.content))
        return history

    def _format_agent_input(self, message: ChannelInboundMessage) -> str:
        sender = message.sender_name or message.sender_id
        return (
            f"[渠道消息]\n"
            f"渠道: {message.channel}\n"
            f"会话: {message.conversation_id}\n"
            f"发送者: {sender}\n\n"
            f"{message.text}"
        )

    def _message_metadata(self, message: ChannelInboundMessage) -> dict[str, Any]:
        metadata = dict(message.metadata)
        metadata.update(
            {
                "channel": message.channel,
                "conversation_id": message.conversation_id,
                "sender_id": message.sender_id,
                "sender_name": message.sender_name,
                "message_id": message.message_id,
            }
        )
        return metadata

    def _normalize_message(
        self, message: ChannelInboundMessage
    ) -> ChannelInboundMessage:
        return ChannelInboundMessage(
            channel=message.channel.strip().lower(),
            conversation_id=str(message.conversation_id).strip(),
            sender_id=str(message.sender_id).strip(),
            text=message.text.strip(),
            message_id=message.message_id,
            sender_name=message.sender_name.strip() if message.sender_name else None,
            metadata=message.metadata,
        )


class ControlPlaneChannelResponder:
    def __init__(self, control_plane_factory: Callable[[], tuple[Any, Any]]):
        self._control_plane_factory = control_plane_factory

    def __call__(self, history: list[Message], message: str) -> Iterable[str]:
        control_plane, runtime = self._control_plane_factory()
        try:
            control_plane.agent.load_history(history)
            result = control_plane.handle(message)
            if result.get("type") == "error":
                raise RuntimeError(result.get("message", "Channel response failed"))
            yield from result.get("response", [])
        finally:
            runtime.stop()
