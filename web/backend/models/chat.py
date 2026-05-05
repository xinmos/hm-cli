from __future__ import annotations

from pydantic import BaseModel, Field


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
    metadata: dict | None = None


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
