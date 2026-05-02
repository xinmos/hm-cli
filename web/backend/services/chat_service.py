from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from uuid import uuid4

import orjson

from hermes.app.ports import ChatMessageRecord, Message

from web.backend.models.chat import (
    ChatAttachment,
    ChatCreate,
    ChatResponse,
    ChatStreamRequest,
    MessageResponse,
)
from web.backend.services.container import WebServiceContainer
from web.backend.services.exceptions import NotFoundError, ValidationError
from web.backend.services.session_service import WebInteractionPort


class ChatApiService:
    def __init__(self, services: WebServiceContainer):
        self._services = services

    def list_chats(self) -> list[ChatResponse]:
        chats = self._services.chat_service.list_chats()
        return [ChatResponse(**chat.__dict__) for chat in chats]

    def create_chat(self, payload: ChatCreate) -> ChatResponse:
        created = self._services.chat_service.create_chat(payload.title, payload.project_id)
        return ChatResponse(**created.__dict__)

    def list_messages(self, chat_id: str) -> list[MessageResponse]:
        messages = self._services.chat_service.list_messages(chat_id)
        return [MessageResponse(**message.__dict__) for message in messages]

    def delete_chat(self, chat_id: str) -> dict[str, str]:
        self._services.chat_service.delete_chat(chat_id)
        return {"status": "ok"}

    def rename_chat(self, chat_id: str, title: str) -> ChatResponse:
        updated = self._services.chat_service.rename_chat(chat_id, title)
        if updated is None:
            raise NotFoundError("Chat not found")
        return ChatResponse(**updated.__dict__)

    def stream_chat_message(self, chat_id: str, payload: ChatStreamRequest) -> AsyncIterator[bytes]:
        message = payload.message.strip()
        if not message:
            raise ValidationError("Empty message")

        history = self._build_agent_history(self._services.chat_service.list_messages(chat_id))
        self._services.chat_service.append_message(chat_id, self._build_message("user", message))
        agent_message = self._message_with_attachments(message, payload.attachments)
        return self._event_stream(chat_id, agent_message, history, payload)

    async def _event_stream(
        self,
        chat_id: str,
        agent_message: str,
        history: list[Message],
        payload: ChatStreamRequest,
    ) -> AsyncIterator[bytes]:
        interaction = WebInteractionPort()
        control_plane, runtime = self._services.create_control_plane(
            interaction_port=interaction,
            model_name=payload.model,
        )
        control_plane.agent.load_history(history)

        loop = asyncio.get_running_loop()
        event_queue: asyncio.Queue[dict | None] = asyncio.Queue()

        def emit_from_worker(event: dict | None) -> None:
            loop.call_soon_threadsafe(event_queue.put_nowait, event)

        interaction.bind(emit_from_worker)
        worker = asyncio.create_task(
            asyncio.to_thread(self._stream_response, agent_message, control_plane, emit_from_worker)
        )
        assistant_chunks: list[str] = []

        try:
            yield self._encode_sse("ack", {
                "type": "ack",
                "message_id": payload.message_id,
            })
            yield self._encode_sse("stream_start", {"type": "stream_start"})

            while True:
                event = await event_queue.get()
                if event is None:
                    break

                if event.get("type") == "stream_delta":
                    assistant_chunks.append(event.get("delta", ""))
                yield self._encode_sse(event.get("type", "message"), event)

            assistant_text = "".join(assistant_chunks)
            if assistant_text:
                self._services.chat_service.append_message(
                    chat_id,
                    self._build_message("assistant", assistant_text),
                )

            yield self._encode_sse("stream_end", {"type": "stream_end"})
            yield self._encode_sse("status", {
                "type": "status",
                "tokens_used": control_plane.agent.get_token_count(),
                "tokens_total": self._services.settings.context_window,
                "model": control_plane.settings.model_name,
            })
        except asyncio.CancelledError:
            worker.cancel()
            raise
        finally:
            interaction.unbind()
            await asyncio.gather(worker, return_exceptions=True)
            runtime.stop()

    def _build_message(self, role: str, content: str) -> ChatMessageRecord:
        return ChatMessageRecord(
            id=f"msg-{uuid4().hex[:12]}",
            role=role,
            content=content,
            created_at=datetime.now().isoformat(),
        )

    def _build_agent_history(self, messages: list[ChatMessageRecord]) -> list[Message]:
        history: list[Message] = []
        for message in messages:
            if message.role not in {"user", "assistant", "system"}:
                continue
            history.append(Message(role=message.role, content=message.content))
        return history

    def _message_with_attachments(self, message: str, attachments: list[ChatAttachment]) -> str:
        if not attachments:
            return message

        parts = [message, "\n\n[附件上下文]"]
        for attachment in attachments:
            label = "图片" if attachment.type == "image" else "文件"
            content = attachment.content
            if attachment.type == "image":
                content = content[:4000]
            elif len(content) > 20000:
                content = f"{content[:20000]}\n\n[内容过长，已截断]"
            parts.append(f"\n\n## {label}: {attachment.name}\n\n{content}")
        return "".join(parts)

    def _encode_sse(self, event_type: str, payload: dict) -> bytes:
        data = orjson.dumps(payload).decode("utf-8")
        return f"event: {event_type}\ndata: {data}\n\n".encode("utf-8")

    def _stream_response(
        self,
        message: str,
        control_plane,
        emit: Callable[[dict | None], None],
    ) -> None:
        try:
            result = control_plane.handle(message)
            if result.get("type") == "error":
                emit({"type": "error", "error": result.get("message", "Unknown error")})
                return

            for chunk in result.get("response", []):
                emit({
                    "type": "stream_delta",
                    "delta": chunk,
                })
        except Exception as exc:
            emit({"type": "error", "error": str(exc)})
        finally:
            emit(None)
