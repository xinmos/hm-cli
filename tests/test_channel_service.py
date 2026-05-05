from datetime import datetime

from hermes.app.ports import ChannelInboundMessage
from hermes.infra.persistence.json_channel_store import JsonChannelConversationStore
from hermes.infra.persistence.json_chat_store import JsonChatStore
from hermes.services.channel_service import ChannelConversationService
from hermes.services.chat_service import ChatService


def test_channel_message_creates_chat_and_persists_reply(tmp_path):
    chat_service = ChatService(JsonChatStore(tmp_path / "chats"))
    link_store = JsonChannelConversationStore(tmp_path / "channels")
    captured = {}

    def responder(history, message):
        captured["history"] = history
        captured["message"] = message
        yield "你好，已收到"

    service = ChannelConversationService(
        chat_service,
        link_store,
        responder,
        clock=lambda: datetime(2026, 5, 3, 12, 0, 0),
    )

    reply = service.handle_inbound(
        ChannelInboundMessage(
            channel="QQ",
            conversation_id="group:42",
            sender_id="user-1",
            sender_name="Alice",
            text=" 帮我总结一下 ",
            message_id="m-1",
        )
    )

    assert reply.channel == "qq"
    assert reply.conversation_id == "group:42"
    assert reply.text == "你好，已收到"
    assert reply.reply_to_message_id == "m-1"
    assert captured["history"] == []
    assert "渠道: qq" in captured["message"]
    assert "发送者: Alice" in captured["message"]

    links = link_store.list_links("qq")
    assert len(links) == 1
    assert links[0].chat_id == reply.chat_id

    messages = chat_service.list_messages(reply.chat_id)
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].metadata["channel"] == "qq"
    assert messages[0].metadata["sender_id"] == "user-1"


def test_channel_message_reuses_existing_chat(tmp_path):
    chat_service = ChatService(JsonChatStore(tmp_path / "chats"))
    link_store = JsonChannelConversationStore(tmp_path / "channels")
    calls = []

    def responder(history, message):
        calls.append(history)
        yield "second"

    service = ChannelConversationService(
        chat_service,
        link_store,
        responder,
        clock=lambda: datetime(2026, 5, 3, 12, 0, 0),
    )

    first = service.handle_inbound(
        ChannelInboundMessage(
            channel="feishu",
            conversation_id="user:u1",
            sender_id="u1",
            text="first",
        )
    )
    second = service.handle_inbound(
        ChannelInboundMessage(
            channel="feishu",
            conversation_id="user:u1",
            sender_id="u1",
            text="again",
        )
    )

    assert second.chat_id == first.chat_id
    assert calls[0] == []
    assert len(calls[1]) == 2
    assert "first" in calls[1][0].content
    assert calls[1][1].content == "second"
    assert len(chat_service.list_messages(first.chat_id)) == 4
