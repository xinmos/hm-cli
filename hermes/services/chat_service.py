from __future__ import annotations

from hermes.app.ports import ChatMessageRecord, ChatStore, ChatSummary


class ChatService:
    def __init__(self, store: ChatStore):
        self._store = store

    def list_chats(self) -> list[ChatSummary]:
        return self._store.list_chats()

    def create_chat(self, title: str | None = None, project_id: str | None = None) -> ChatSummary:
        return self._store.create_chat(title or "New Chat", project_id)

    def list_messages(self, chat_id: str) -> list[ChatMessageRecord]:
        return self._store.list_messages(chat_id)

    def append_message(self, chat_id: str, message: ChatMessageRecord) -> None:
        self._store.append_message(chat_id, message)

    def delete_chat(self, chat_id: str) -> None:
        self._store.delete_chat(chat_id)
