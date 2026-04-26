from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from uuid import uuid4

import orjson
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from hermes.app.ports import ChatMessageRecord, Message

from web.backend.app_state import WebServiceContainer
from web.backend.session_manager import WebInteractionPort

router = APIRouter()


class ChatCreate(BaseModel):
    title: str | None = None
    project_id: str | None = None


class ChatResponse(BaseModel):
    id: str
    title: str
    project_id: str | None
    created_at: str
    updated_at: str
    message_count: int


class ChatRename(BaseModel):
    title: str


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
    tool_calls: list | None = None


class ChatAttachment(BaseModel):
    name: str
    type: str
    content: str
    mime_type: str | None = None


class ChatStreamRequest(BaseModel):
    message: str
    permissions: str | None = None
    model: str | None = None
    message_id: str | None = None
    attachments: list[ChatAttachment] = Field(default_factory=list)


def _services(request: Request) -> WebServiceContainer:
    return request.app.state.services


def _build_message(role: str, content: str) -> ChatMessageRecord:
    return ChatMessageRecord(
        id=f"msg-{uuid4().hex[:12]}",
        role=role,
        content=content,
        created_at=datetime.now().isoformat(),
    )


def _build_agent_history(messages: list[ChatMessageRecord]) -> list[Message]:
    history: list[Message] = []
    for message in messages:
        if message.role not in {"user", "assistant", "system"}:
            continue
        history.append(Message(role=message.role, content=message.content))
    return history


def _message_with_attachments(message: str, attachments: list[ChatAttachment]) -> str:
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


def _encode_sse(event_type: str, payload: dict) -> bytes:
    return f"event: {event_type}\ndata: {orjson.dumps(payload).decode('utf-8')}\n\n".encode("utf-8")


def _stream_response(
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


@router.get("/chats", response_model=list[ChatResponse])
async def get_chats(request: Request) -> list[ChatResponse]:
    chats = _services(request).chat_service.list_chats()
    return [ChatResponse(**chat.__dict__) for chat in chats]


@router.post("/chats", response_model=ChatResponse)
async def create_chat(chat: ChatCreate, request: Request) -> ChatResponse:
    created = _services(request).chat_service.create_chat(chat.title, chat.project_id)
    return ChatResponse(**created.__dict__)


@router.get("/chats/{chat_id}/messages", response_model=list[MessageResponse])
async def get_messages(chat_id: str, request: Request) -> list[MessageResponse]:
    messages = _services(request).chat_service.list_messages(chat_id)
    return [MessageResponse(**message.__dict__) for message in messages]


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, request: Request) -> dict[str, str]:
    _services(request).chat_service.delete_chat(chat_id)
    return {"status": "ok"}


@router.patch("/chats/{chat_id}", response_model=ChatResponse)
async def rename_chat(chat_id: str, chat: ChatRename, request: Request) -> ChatResponse:
    updated = _services(request).chat_service.rename_chat(chat_id, chat.title)
    if updated is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return ChatResponse(**updated.__dict__)


@router.post("/chats/{chat_id}/messages/stream")
async def stream_chat_message(
    chat_id: str,
    payload: ChatStreamRequest,
    request: Request,
) -> StreamingResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Empty message")

    services = _services(request)
    history = _build_agent_history(services.chat_service.list_messages(chat_id))
    services.chat_service.append_message(chat_id, _build_message("user", message))
    agent_message = _message_with_attachments(message, payload.attachments)

    async def event_stream() -> AsyncIterator[bytes]:
        interaction = WebInteractionPort()
        control_plane, runtime = services.create_control_plane(
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
            asyncio.to_thread(_stream_response, agent_message, control_plane, emit_from_worker)
        )
        assistant_chunks: list[str] = []

        try:
            yield _encode_sse("ack", {
                "type": "ack",
                "message_id": payload.message_id,
            })
            yield _encode_sse("stream_start", {"type": "stream_start"})

            while True:
                event = await event_queue.get()
                if event is None:
                    break

                if event.get("type") == "stream_delta":
                    assistant_chunks.append(event.get("delta", ""))
                yield _encode_sse(event.get("type", "message"), event)

            assistant_text = "".join(assistant_chunks)
            if assistant_text:
                services.chat_service.append_message(chat_id, _build_message("assistant", assistant_text))

            yield _encode_sse("stream_end", {"type": "stream_end"})
            yield _encode_sse("status", {
                "type": "status",
                "tokens_used": control_plane.agent.get_token_count(),
                "tokens_total": services.settings.context_window,
                "model": control_plane.settings.model_name,
            })
        except asyncio.CancelledError:
            worker.cancel()
            raise
        finally:
            interaction.unbind()
            await asyncio.gather(worker, return_exceptions=True)
            runtime.stop()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
