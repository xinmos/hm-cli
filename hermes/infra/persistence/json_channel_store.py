from __future__ import annotations

from pathlib import Path

import orjson

from hermes.app.ports import ChannelConversationKey, ChannelConversationLink


class JsonChannelConversationStore:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._links_file = data_dir / "channel_conversations.json"
        self._data_dir.mkdir(parents=True, exist_ok=True)

    def get_link(self, key: ChannelConversationKey) -> ChannelConversationLink | None:
        normalized_key = _normalize_key(key)
        for link in self.list_links():
            if (
                link.channel == normalized_key.channel
                and link.conversation_id == normalized_key.conversation_id
            ):
                return link
        return None

    def save_link(self, link: ChannelConversationLink) -> None:
        normalized_link = _normalize_link(link)
        links = [
            item
            for item in self.list_links()
            if not (
                item.channel == normalized_link.channel
                and item.conversation_id == normalized_link.conversation_id
            )
        ]
        links.insert(0, normalized_link)
        self._write_links(links)

    def list_links(self, channel: str | None = None) -> list[ChannelConversationLink]:
        links = [self._to_link(item) for item in self._load_links()]
        if channel:
            normalized_channel = _normalize_channel(channel)
            links = [link for link in links if link.channel == normalized_channel]
        return sorted(links, key=lambda item: item.updated_at, reverse=True)

    def _load_links(self) -> list[dict]:
        if not self._links_file.exists():
            return []
        try:
            payload = orjson.loads(self._links_file.read_bytes())
        except Exception:
            return []
        return payload if isinstance(payload, list) else []

    def _write_links(self, links: list[ChannelConversationLink]) -> None:
        payload = [self._link_to_dict(link) for link in links]
        self._links_file.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))

    def _to_link(self, item: dict) -> ChannelConversationLink:
        return ChannelConversationLink(
            channel=_normalize_channel(item["channel"]),
            conversation_id=str(item["conversation_id"]),
            chat_id=item["chat_id"],
            created_at=item["created_at"],
            updated_at=item["updated_at"],
            metadata=item.get("metadata") or {},
        )

    def _link_to_dict(self, link: ChannelConversationLink) -> dict:
        return {
            "channel": link.channel,
            "conversation_id": link.conversation_id,
            "chat_id": link.chat_id,
            "created_at": link.created_at,
            "updated_at": link.updated_at,
            "metadata": link.metadata,
        }


def _normalize_key(key: ChannelConversationKey) -> ChannelConversationKey:
    return ChannelConversationKey(
        channel=_normalize_channel(key.channel),
        conversation_id=str(key.conversation_id),
    )


def _normalize_link(link: ChannelConversationLink) -> ChannelConversationLink:
    return ChannelConversationLink(
        channel=_normalize_channel(link.channel),
        conversation_id=str(link.conversation_id),
        chat_id=link.chat_id,
        created_at=link.created_at,
        updated_at=link.updated_at,
        metadata=link.metadata,
    )


def _normalize_channel(channel: str) -> str:
    return channel.strip().lower()
