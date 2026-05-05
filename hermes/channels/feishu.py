from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from time import monotonic
from typing import Any
from uuid import uuid4

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
_STREAM_ELEMENT_ID = "hermes_answer"
_STREAM_FLUSH_INTERVAL_SECONDS = 0.8
_STREAM_FLUSH_MIN_CHARS = 48


@dataclass(frozen=True)
class FeishuBotConfig:
    app_id: str
    app_secret: str
    verification_token: str | None = None
    encrypt_key: str | None = None
    domain: str = "https://open.feishu.cn"
    auto_reconnect: bool = True
    enable_markdown: bool = True
    enable_streaming: bool = True

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
            enable_markdown=_env_bool(
                "HERMES_FEISHU_ENABLE_MARKDOWN",
                "FEISHU_ENABLE_MARKDOWN",
                "LARK_ENABLE_MARKDOWN",
                default=_bool_config(saved, "enable_markdown", True),
            ),
            enable_streaming=_env_bool(
                "HERMES_FEISHU_ENABLE_STREAMING",
                "FEISHU_ENABLE_STREAMING",
                "LARK_ENABLE_STREAMING",
                default=_bool_config(saved, "enable_streaming", True),
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
        self._ws_client: Any | None = None

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
        self._ws_client = lark.ws.Client(
            self._config.app_id,
            self._config.app_secret,
            event_handler=event_handler,
            domain=self._config.domain,
            auto_reconnect=self._config.auto_reconnect,
        )
        self._log("Feishu bot websocket starting...")
        try:
            self._ws_client.start()
        except KeyboardInterrupt:
            self._log("Feishu bot stopping...")
            self.stop()

    def stop(self) -> None:
        ws_client = self._ws_client
        if ws_client is None:
            return

        try:
            import lark_oapi.ws.client as ws_module
        except ImportError:
            self._ws_client = None
            return

        loop = getattr(ws_module, "loop", None)
        if loop is None or loop.is_closed():
            self._ws_client = None
            return

        try:
            loop.run_until_complete(ws_client._disconnect())
            _cancel_pending_lark_tasks(loop)
        except Exception as exc:
            self._log(f"Feishu bot stop warning: {exc}")
        finally:
            self._ws_client = None

    def _handle_message_event(self, data: Any) -> None:
        Thread(target=self._process_message_event, args=(data,), daemon=True).start()

    def _process_message_event(self, data: Any) -> None:
        inbound = _event_to_inbound(data)
        if inbound is None:
            self._log("Ignored unsupported Feishu message event")
            return

        if self._config.enable_streaming and self._reply_streaming_markdown(inbound):
            return

        outbound = self._handle_inbound(inbound)
        if self._config.enable_markdown and self._reply_markdown_card(
            inbound.message_id or "", outbound
        ):
            return
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

    def _reply_streaming_markdown(self, inbound: ChannelInboundMessage) -> bool:
        message_id = inbound.message_id or ""
        if not message_id:
            self._log("Cannot stream Feishu reply without message_id")
            return False
        if self._client is None:
            self._log("Cannot stream Feishu reply before client is ready")
            return False

        try:
            card_id = self._create_card(
                _build_markdown_card("正在思考...", streaming=True)
            )
            self._reply_card_id(message_id, card_id)
        except Exception as exc:
            self._log(f"Feishu streaming card startup failed: {exc}")
            return False

        buffer = ""
        sent = ""
        sequence = 1
        last_flush = 0.0
        updates_ok = True
        try:
            for outbound in self._channel_service.stream_inbound(inbound):
                buffer += outbound.text
                now = monotonic()
                should_flush = (
                    now - last_flush >= _STREAM_FLUSH_INTERVAL_SECONDS
                    or len(buffer) - len(sent) >= _STREAM_FLUSH_MIN_CHARS
                )
                if buffer != sent and should_flush and updates_ok:
                    try:
                        self._update_streaming_content(card_id, buffer, sequence)
                        sent = buffer
                        sequence += 1
                        last_flush = now
                    except Exception as exc:
                        updates_ok = False
                        self._log(f"Feishu streaming content update failed: {exc}")

            final_text = _format_reply(buffer)
            if updates_ok:
                if final_text != sent:
                    self._update_streaming_content(card_id, final_text, sequence)
                    sequence += 1
                self._finish_streaming_card(card_id, sequence)
            else:
                outbound = ChannelOutboundMessage(
                    channel=inbound.channel,
                    conversation_id=inbound.conversation_id,
                    text=final_text,
                    chat_id="",
                    reply_to_message_id=inbound.message_id,
                )
                if self._config.enable_markdown and self._reply_markdown_card(
                    message_id, outbound
                ):
                    return True
                self._reply_text(message_id, outbound)
            return True
        except Exception as exc:
            self._log(f"Feishu streaming reply failed: {exc}")
            try:
                self._update_streaming_content(
                    card_id,
                    "处理消息失败，请稍后再试。",
                    sequence,
                )
                self._finish_streaming_card(card_id, sequence + 1)
            except Exception as update_exc:
                self._log(f"Feishu streaming error card update failed: {update_exc}")
            return True

    def _create_card(self, card: dict[str, Any]) -> str:
        if self._client is None:
            raise RuntimeError("Feishu client is not ready")

        from lark_oapi.api.cardkit.v1 import CreateCardRequest, CreateCardRequestBody

        request = (
            CreateCardRequest.builder()
            .request_body(
                CreateCardRequestBody.builder()
                .type("card_json")
                .data(orjson.dumps(card).decode("utf-8"))
                .build()
            )
            .build()
        )
        response = self._client.cardkit.v1.card.create(request)
        _require_feishu_success(response, "create streaming card")
        card_id = getattr(getattr(response, "data", None), "card_id", None)
        if not card_id:
            raise RuntimeError("Feishu create card response did not include card_id")
        return str(card_id)

    def _reply_card_id(self, message_id: str, card_id: str) -> None:
        if self._client is None:
            raise RuntimeError("Feishu client is not ready")

        from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody

        content = orjson.dumps({"type": "card", "data": {"card_id": card_id}}).decode(
            "utf-8"
        )
        request = (
            ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .msg_type("interactive")
                .content(content)
                .build()
            )
            .build()
        )
        response = self._client.im.v1.message.reply(request)
        _require_feishu_success(response, "reply with streaming card")

    def _update_streaming_content(
        self, card_id: str, content: str, sequence: int
    ) -> None:
        if self._client is None:
            raise RuntimeError("Feishu client is not ready")

        from lark_oapi.api.cardkit.v1 import (
            ContentCardElementRequest,
            ContentCardElementRequestBody,
        )

        request = (
            ContentCardElementRequest.builder()
            .card_id(card_id)
            .element_id(_STREAM_ELEMENT_ID)
            .request_body(
                ContentCardElementRequestBody.builder()
                .uuid(uuid4().hex)
                .content(_format_reply(content))
                .sequence(sequence)
                .build()
            )
            .build()
        )
        response = self._client.cardkit.v1.card_element.content(request)
        _require_feishu_success(response, "update streaming card content")

    def _finish_streaming_card(self, card_id: str, sequence: int) -> None:
        if self._client is None:
            raise RuntimeError("Feishu client is not ready")

        from lark_oapi.api.cardkit.v1 import (
            SettingsCardRequest,
            SettingsCardRequestBody,
        )

        settings = orjson.dumps(
            {
                "config": {
                    "streaming_mode": False,
                    "update_multi": True,
                    "width_mode": "fill",
                }
            }
        ).decode("utf-8")
        request = (
            SettingsCardRequest.builder()
            .card_id(card_id)
            .request_body(
                SettingsCardRequestBody.builder()
                .uuid(uuid4().hex)
                .settings(settings)
                .sequence(sequence)
                .build()
            )
            .build()
        )
        response = self._client.cardkit.v1.card.settings(request)
        _require_feishu_success(response, "finish streaming card")

    def _reply_markdown_card(
        self, message_id: str, outbound: ChannelOutboundMessage
    ) -> bool:
        if not message_id:
            self._log("Cannot reply Feishu message without message_id")
            return False
        if self._client is None:
            self._log("Cannot reply Feishu message before client is ready")
            return False

        from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody

        content = orjson.dumps(
            _build_markdown_card(_format_reply(outbound.text), streaming=False)
        ).decode("utf-8")
        request = (
            ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .msg_type("interactive")
                .content(content)
                .build()
            )
            .build()
        )
        response = self._client.im.v1.message.reply(request)
        if not response.success():
            self._log(
                f"Feishu markdown card reply failed: code={response.code}, msg={response.msg}"
            )
            return False
        return True

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
    _set_if_present(
        config,
        "enable_markdown",
        _env(
            "HERMES_FEISHU_ENABLE_MARKDOWN",
            "FEISHU_ENABLE_MARKDOWN",
            "LARK_ENABLE_MARKDOWN",
        ),
    )
    _set_if_present(
        config,
        "enable_streaming",
        _env(
            "HERMES_FEISHU_ENABLE_STREAMING",
            "FEISHU_ENABLE_STREAMING",
            "LARK_ENABLE_STREAMING",
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


def _build_markdown_card(content: str, *, streaming: bool) -> dict[str, Any]:
    return {
        "schema": "2.0",
        "config": {
            "streaming_mode": streaming,
            "update_multi": True,
            "width_mode": "fill",
        },
        "body": {
            "elements": [
                {
                    "tag": "markdown",
                    "element_id": _STREAM_ELEMENT_ID,
                    "content": _format_reply(content),
                }
            ]
        },
    }


def _require_feishu_success(response: Any, action: str) -> None:
    if response.success():
        return
    raise RuntimeError(
        f"{action} failed: code={response.code}, msg={response.msg}, log_id={response.get_log_id()}"
    )


def _cancel_pending_lark_tasks(loop: asyncio.AbstractEventLoop) -> None:
    pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
    if not pending:
        return
    for task in pending:
        task.cancel()
    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))


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
        "enable_markdown",
        "enable_streaming",
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
