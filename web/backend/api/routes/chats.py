from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

router = APIRouter()


class ChatCreate(BaseModel):
    title: Optional[str] = "New Chat"
    project_id: Optional[str] = None


class ChatResponse(BaseModel):
    id: str
    title: str
    project_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime
    tool_calls: Optional[list] = None


chats_db = {}
messages_db = {}


@router.get("", response_model=List[ChatResponse])
async def list_chats():
    return list(chats_db.values())


@router.post("", response_model=ChatResponse)
async def create_chat(chat: ChatCreate):
    chat_id = str(uuid.uuid4())
    now = datetime.now()
    new_chat = {
        "id": chat_id,
        "title": chat.title,
        "project_id": chat.project_id,
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
    }
    chats_db[chat_id] = new_chat
    messages_db[chat_id] = []
    return new_chat


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(chat_id: str):
    if chat_id not in chats_db:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chats_db[chat_id]


@router.delete("/{chat_id}")
async def delete_chat(chat_id: str):
    if chat_id not in chats_db:
        raise HTTPException(status_code=404, detail="Chat not found")
    del chats_db[chat_id]
    if chat_id in messages_db:
        del messages_db[chat_id]
    return {"status": "deleted"}


@router.get("/{chat_id}/messages", response_model=List[MessageResponse])
async def get_messages(chat_id: str):
    if chat_id not in messages_db:
        raise HTTPException(status_code=404, detail="Chat not found")
    return messages_db.get(chat_id, [])
