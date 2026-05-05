from __future__ import annotations

from datetime import datetime
from pathlib import Path

import orjson

from hermes.app.ports import ChatMessageRecord, ChatSummary


class JsonChatStore:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._messages_dir = data_dir / "messages"
        self._chats_file = data_dir / "chats.json"
        self._ensure_dirs()

    def list_chats(self) -> list[ChatSummary]:
        chats = [
            self._to_chat_summary(item)
            for item in self._load_json(self._chats_file, default=[])
        ]
        return sorted(chats, key=lambda item: item.updated_at, reverse=True)

    def create_chat(self, title: str, project_id: str | None = None) -> ChatSummary:
        now = datetime.now().isoformat()
        chat_id = f"chat-{now.replace(':', '-')}"
        chat = ChatSummary(
            id=chat_id,
            title=title or "New Chat",
            project_id=project_id,
            created_at=now,
            updated_at=now,
            message_count=0,
        )

        chats = self.list_chats()
        chats.insert(0, chat)
        self._write_chats(chats)
        self._messages_path(chat_id).touch()
        return chat

    def list_messages(self, chat_id: str) -> list[ChatMessageRecord]:
        path = self._messages_path(chat_id)
        if path.exists():
            return self._load_messages_jsonl(path)

        legacy_path = self._legacy_messages_path(chat_id)
        if legacy_path.exists():
            raw_messages = self._load_json(legacy_path, default=[])
            return [self._to_message(item) for item in raw_messages]

        return []

    def append_message(self, chat_id: str, message: ChatMessageRecord) -> None:
        chats = self.list_chats()
        for chat in chats:
            if chat.id == chat_id:
                chat.message_count += 1
                chat.updated_at = datetime.now().isoformat()
                break
        else:
            return

        self._append_message_jsonl(chat_id, message)
        self._write_chats(chats)

    def delete_chat(self, chat_id: str) -> None:
        chats = [chat for chat in self.list_chats() if chat.id != chat_id]
        self._write_chats(chats)

        messages_path = self._messages_path(chat_id)
        if messages_path.exists():
            messages_path.unlink()
        legacy_messages_path = self._legacy_messages_path(chat_id)
        if legacy_messages_path.exists():
            legacy_messages_path.unlink()

    def rename_chat(self, chat_id: str, title: str) -> ChatSummary | None:
        chats = self.list_chats()
        updated_chat: ChatSummary | None = None

        for chat in chats:
            if chat.id != chat_id:
                continue
            chat.title = title
            chat.updated_at = datetime.now().isoformat()
            updated_chat = chat
            break

        if updated_chat is None:
            return None

        self._write_chats(chats)
        return updated_chat

    def _ensure_dirs(self) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._messages_dir.mkdir(parents=True, exist_ok=True)

    def _messages_path(self, chat_id: str) -> Path:
        return self._messages_dir / f"{chat_id}.jsonl"

    def _legacy_messages_path(self, chat_id: str) -> Path:
        return self._messages_dir / f"{chat_id}.json"

    def _load_json(self, path: Path, default: list[dict]) -> list[dict]:
        if not path.exists():
            return list(default)
        try:
            payload = orjson.loads(path.read_bytes())
        except Exception:
            return list(default)
        return payload if isinstance(payload, list) else list(default)

    def _write_chats(self, chats: list[ChatSummary]) -> None:
        payload = [self._chat_to_dict(chat) for chat in chats]
        self._chats_file.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))

    def _append_message_jsonl(self, chat_id: str, message: ChatMessageRecord) -> None:
        payload = orjson.dumps(self._message_to_dict(message))
        with self._messages_path(chat_id).open("ab") as handle:
            handle.write(payload + b"\n")

    def _load_messages_jsonl(self, path: Path) -> list[ChatMessageRecord]:
        messages: list[ChatMessageRecord] = []
        for line in path.read_bytes().splitlines():
            if not line:
                continue
            try:
                item = orjson.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                messages.append(self._to_message(item))
        return messages

    def _to_chat_summary(self, item: dict) -> ChatSummary:
        return ChatSummary(
            id=item["id"],
            title=item["title"],
            project_id=item.get("project_id"),
            created_at=item["created_at"],
            updated_at=item["updated_at"],
            message_count=item.get("message_count", 0),
        )

    def _chat_to_dict(self, chat: ChatSummary) -> dict:
        return {
            "id": chat.id,
            "title": chat.title,
            "project_id": chat.project_id,
            "created_at": chat.created_at,
            "updated_at": chat.updated_at,
            "message_count": chat.message_count,
        }

    def _to_message(self, item: dict) -> ChatMessageRecord:
        return ChatMessageRecord(
            id=item["id"],
            role=item["role"],
            content=item["content"],
            created_at=item["created_at"],
            tool_calls=item.get("tool_calls"),
            metadata=item.get("metadata") or {},
        )

    def _message_to_dict(self, message: ChatMessageRecord) -> dict:
        return {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at,
            "tool_calls": message.tool_calls,
            "metadata": message.metadata,
        }
