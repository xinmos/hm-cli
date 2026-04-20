from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from web.backend.app_state import WebServiceContainer

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


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
    tool_calls: list | None = None


def _services(request: Request) -> WebServiceContainer:
    return request.app.state.services


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
