from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from web.backend.controllers.dependencies import get_services, to_http_error
from web.backend.models.chat import ChatCreate, ChatRename, ChatResponse, ChatStreamRequest, MessageResponse
from web.backend.services.chat_service import ChatApiService
from web.backend.services.exceptions import BackendServiceError

router = APIRouter()


def _chat_service(request: Request) -> ChatApiService:
    return ChatApiService(get_services(request))


@router.get("/chats", response_model=list[ChatResponse])
async def get_chats(request: Request) -> list[ChatResponse]:
    return _chat_service(request).list_chats()


@router.post("/chats", response_model=ChatResponse)
async def create_chat(chat: ChatCreate, request: Request) -> ChatResponse:
    return _chat_service(request).create_chat(chat)


@router.get("/chats/{chat_id}/messages", response_model=list[MessageResponse])
async def get_messages(chat_id: str, request: Request) -> list[MessageResponse]:
    return _chat_service(request).list_messages(chat_id)


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, request: Request) -> dict[str, str]:
    return _chat_service(request).delete_chat(chat_id)


@router.patch("/chats/{chat_id}", response_model=ChatResponse)
async def rename_chat(chat_id: str, chat: ChatRename, request: Request) -> ChatResponse:
    try:
        return _chat_service(request).rename_chat(chat_id, chat.title)
    except BackendServiceError as exc:
        raise to_http_error(exc) from exc


@router.post("/chats/{chat_id}/messages/stream")
async def stream_chat_message(
    chat_id: str,
    payload: ChatStreamRequest,
    request: Request,
) -> StreamingResponse:
    try:
        stream = _chat_service(request).stream_chat_message(chat_id, payload)
    except BackendServiceError as exc:
        raise to_http_error(exc) from exc

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
