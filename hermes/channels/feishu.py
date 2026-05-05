from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import orjson

from hermes.app.ports import (
    ChannelInboundMessage,
    ChannelOutboundMessage,
    InteractionPort,
)
from hermes.infra.persistence.json_channel_store import JsonChannelConversationStore
from hermes.infra.persistence.json_chat_store import JsonChatStore
from hermes.services.channel_service import (
    ChannelConversationService,
    ControlPlaneChannelResponder,
)
from hermes.services.chat_service import ChatService


_AT_TAG_PATTERN = re.compile(r"<at\b[^>]*>.*?</at>")


@dataclass(frozen=True)
class FeishuBotConfig:
    app_id: str
    app_secret: str
    verification_token: str | None = None
    encrypt_key: str | None = None
    domain: str = "https://open.feishu.cn"
    auto_reconnect: bool = True

    @property
    def channel(self) -> str:
        return "feishu"

    @classmethod
    def from_env(cls, workdir: Path | None = None) -> "FeishuBotConfig":
        saved = read_saved_feishu_config(workdir) if workdir else {}
        app_id = _env(
            "HERMES_FEISHU_APP_ID", "FEISHU_APP_ID", "LARK_APP_ID"
        ) or _str_config(saved, "app_id")
        app_secret = _env(
            "HERMES_FEISHU_APP_SECRET", "FEISHU_APP_SECRET", "LARK_APP_SECRET"
        ) or _str_config(saved, "app_secret")
        if not app_id or not app_secret:
            raise ValueError(
                "Missing Feishu credentials. Set HERMES_FEISHU_APP_ID and HERMES_FEISHU_APP_SECRET."
            )

        return cls(
            app_id=app_id,
            app_secret=app_secret,
            verification_token=(
                _env(
                    "HERMES_FEISHU_VERIFICATION_TOKEN",
                    "FEISHU_VERIFICATION_TOKEN",
                    "LARK_VERIFICATION_TOKEN",
                )
                or _str_config(saved, "verification_token")
            ),
            encrypt_key=_env(
                "HERMES_FEISHU_ENCRYPT_KEY", "FEISHU_ENCRYPT_KEY", "LARK_ENCRYPT_KEY"
            )
            or _str_config(saved, "encrypt_key"),
            domain=_env("HERMES_FEISHU_DOMAIN", "FEISHU_DOMAIN", "LARK_DOMAIN")
            or _str_config(saved, "domain")
            or "https://open.feishu.cn",
            auto_reconnect=_env_bool(
                "HERMES_FEISHU_AUTO_RECONNECT",
                "FEISHU_AUTO_RECONNECT",
                "LARK_AUTO_RECONNECT",
                default=_bool_config(saved, "auto_reconnect", True),
            ),
        )


class FeishuBotRunner:
    def __init__(
        self,
        config: FeishuBotConfig,
        channel_service: ChannelConversationService,
        *,
        log: Callable[[str], None] | None = None,
    ):
        self._config = config
        self._channel_service = channel_service
        self._log = log or (lambda message: None)
        self._client: Any | None = None

    def run(self) -> None:
        try:
            import lark_oapi as lark
        except ImportError as exc:
            raise RuntimeError(
                "lark-oapi is not installed. Run `uv sync` first."
            ) from exc

        self._client = (
            lark.Client.builder()
            .app_id(self._config.app_id)
            .app_secret(self._config.app_secret)
            .domain(self._config.domain)
            .build()
        )

        event_handler = (
            lark.EventDispatcherHandler.builder(
                self._config.encrypt_key or "",
                self._config.verification_token or "",
            )
            .register_p2_im_message_receive_v1(self._handle_message_event)
            .build()
        )
        ws_client = lark.ws.Client(
            self._config.app_id,
            self._config.app_secret,
            event_handler=event_handler,
            domain=self._config.domain,
            auto_reconnect=self._config.auto_reconnect,
        )
        self._log("Feishu bot websocket starting...")
        ws_client.start()

    def _handle_message_event(self, data: Any) -> None:
        inbound = _event_to_inbound(data)
        if inbound is None:
            self._log("Ignored unsupported Feishu message event")
            return

        outbound = self._handle_inbound(inbound)
        self._reply_text(inbound.message_id or "", outbound)

    def _handle_inbound(self, message: ChannelInboundMessage) -> ChannelOutboundMessage:
        try:
            return self._channel_service.handle_inbound(message)
        except Exception as exc:
            self._log(f"Feishu message handling failed: {exc}")
            return ChannelOutboundMessage(
                channel=message.channel,
                conversation_id=message.conversation_id,
                text="处理消息失败，请稍后再试。",
                chat_id="",
                reply_to_message_id=message.message_id,
                metadata={"error": str(exc)},
            )

    def _reply_text(self, message_id: str, outbound: ChannelOutboundMessage) -> None:
        if not message_id:
            self._log("Cannot reply Feishu message without message_id")
            return
        if self._client is None:
            self._log("Cannot reply Feishu message before client is ready")
            return

        from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody

        content = orjson.dumps({"text": _format_reply(outbound.text)}).decode("utf-8")
        request = (
            ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .msg_type("text")
                .content(content)
                .build()
            )
            .build()
        )
        response = self._client.im.v1.message.reply(request)
        if not response.success():
            self._log(f"Feishu reply failed: code={response.code}, msg={response.msg}")


def build_feishu_channel_service(
    settings: Any,
    control_plane_factory: Callable[[], tuple[Any, Any]],
) -> ChannelConversationService:
    chat_service = ChatService(JsonChatStore(settings.workdir / ".hermes" / "feishu"))
    link_store = JsonChannelConversationStore(settings.workdir / ".hermes" / "feishu")
    responder = ControlPlaneChannelResponder(control_plane_factory)
    return ChannelConversationService(chat_service, link_store, responder)


def read_saved_feishu_config(workdir: Path) -> dict[str, Any]:
    settings = _read_settings_file(workdir)
    feishu_bot = settings.get("feishu_bot")
    return dict(feishu_bot) if isinstance(feishu_bot, dict) else {}


def write_saved_feishu_config(workdir: Path, config: dict[str, Any]) -> None:
    settings = _read_settings_file(workdir)
    settings["feishu_bot"] = _filter_feishu_config(config)
    _write_settings_file(workdir, settings)


def read_env_feishu_config() -> dict[str, Any]:
    config: dict[str, Any] = {}
    _set_if_present(
        config, "app_id", _env("HERMES_FEISHU_APP_ID", "FEISHU_APP_ID", "LARK_APP_ID")
    )
    _set_if_present(
        config,
        "app_secret",
        _env("HERMES_FEISHU_APP_SECRET", "FEISHU_APP_SECRET", "LARK_APP_SECRET"),
    )
    _set_if_present(
        config,
        "verification_token",
        _env(
            "HERMES_FEISHU_VERIFICATION_TOKEN",
            "FEISHU_VERIFICATION_TOKEN",
            "LARK_VERIFICATION_TOKEN",
        ),
    )
    _set_if_present(
        config,
        "encrypt_key",
        _env("HERMES_FEISHU_ENCRYPT_KEY", "FEISHU_ENCRYPT_KEY", "LARK_ENCRYPT_KEY"),
    )
    _set_if_present(
        config, "domain", _env("HERMES_FEISHU_DOMAIN", "FEISHU_DOMAIN", "LARK_DOMAIN")
    )
    _set_if_present(
        config,
        "auto_reconnect",
        _env(
            "HERMES_FEISHU_AUTO_RECONNECT",
            "FEISHU_AUTO_RECONNECT",
            "LARK_AUTO_RECONNECT",
        ),
    )
    return config


class FeishuInteractionPort(InteractionPort):
    def __init__(self, log: Callable[[str], None] | None = None):
        self._log = log or (lambda message: None)

    def confirm(self, tool_name: str, description: str, tool_display: str = "") -> bool:
        display = tool_display or f"{tool_name}: {description}"
        self._log(f"Feishu channel denied interactive confirmation: {display}")
        return False

    def notify_tool_start(self, tool_name: str, tool_display: str = "") -> None:
        display = tool_display or tool_name
        if display:
            self._log(f"Feishu channel tool start: {display}")

    def notify_tool_complete(self, tool_name: str, result: Any = None) -> None:
        return None

    def notify_tool_error(self, tool_name: str, error: str) -> None:
        self._log(f"Feishu channel tool error: {tool_name}: {error}")

    def on_context_compressed(self, original: int, compressed: int) -> None:
        self._log(f"Feishu channel context compressed: {original} -> {compressed}")


def _event_to_inbound(data: Any) -> ChannelInboundMessage | None:
    event = getattr(data, "event", None)
    message = getattr(event, "message", None)
    sender = getattr(event, "sender", None)
    if message is None or sender is None:
        return None

    text = _extract_message_text(message)
    sender_id = _sender_id(sender)
    conversation_id = f"chat:{getattr(message, 'chat_id', '') or sender_id}"
    return ChannelInboundMessage(
        channel="feishu",
        conversation_id=conversation_id,
        sender_id=sender_id,
        sender_name=None,
        text=text,
        message_id=getattr(message, "message_id", None),
        metadata={
            "message_type": getattr(message, "message_type", None),
            "chat_id": getattr(message, "chat_id", None),
            "chat_type": getattr(message, "chat_type", None),
            "thread_id": getattr(message, "thread_id", None),
            "tenant_key": getattr(sender, "tenant_key", None),
        },
    )


def _extract_message_text(message: Any) -> str:
    content = getattr(message, "content", "") or ""
    message_type = getattr(message, "message_type", "") or ""
    try:
        parsed = orjson.loads(content)
    except orjson.JSONDecodeError:
        return _clean_feishu_text(content, message)

    if message_type == "text" and isinstance(parsed, dict):
        return _clean_feishu_text(str(parsed.get("text") or ""), message)
    if message_type == "post" and isinstance(parsed, dict):
        return _clean_feishu_text(_extract_post_text(parsed), message)
    return _clean_feishu_text(content, message)


def _extract_post_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            tag = value.get("tag")
            if tag in {"text", "a", "at"}:
                text = value.get("text") or value.get("name")
                if isinstance(text, str):
                    parts.append(text)
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return " ".join(part for part in parts if part).strip()


def _clean_feishu_text(text: str, message: Any) -> str:
    cleaned = _AT_TAG_PATTERN.sub("", text)
    for mention in getattr(message, "mentions", []) or []:
        key = getattr(mention, "key", None)
        if key:
            cleaned = cleaned.replace(str(key), "")
    return cleaned.strip()


def _sender_id(sender: Any) -> str:
    sender_id = getattr(sender, "sender_id", None)
    for key in ("open_id", "user_id", "union_id"):
        value = getattr(sender_id, key, None)
        if value:
            return str(value)
    return "unknown-sender"


def _format_reply(text: str) -> str:
    return text.strip() or "我收到了，但暂时没有生成回复。"


def _env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _env_bool(*names: str, default: bool) -> bool:
    raw = _env(*names)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _str_config(config: dict[str, Any], key: str) -> str | None:
    value = config.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _bool_config(config: dict[str, Any], key: str, default: bool) -> bool:
    value = config.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip():
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return default


def _set_if_present(config: dict[str, Any], key: str, value: str | None) -> None:
    if value is not None:
        config[key] = value


def _filter_feishu_config(config: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "app_id",
        "app_secret",
        "verification_token",
        "encrypt_key",
        "domain",
        "auto_reconnect",
    }
    return {key: value for key, value in config.items() if key in allowed}


def _read_settings_file(workdir: Path) -> dict[str, Any]:
    path = workdir / ".hermes" / "settings.json"
    if not path.exists():
        return {}
    try:
        parsed = orjson.loads(path.read_bytes())
    except orjson.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _write_settings_file(workdir: Path, data: dict[str, Any]) -> None:
    path = workdir / ".hermes" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))
