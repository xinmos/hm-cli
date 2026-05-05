from __future__ import annotations

import asyncio
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


_MENTION_PATTERN = re.compile(r"^<@!?\d+>\s*")


@dataclass(frozen=True)
class QQBotConfig:
    app_id: str
    secret: str
    sandbox: bool = False
    timeout: int = 5
    enable_guild: bool = True
    enable_direct: bool = True
    enable_group: bool = True
    enable_c2c: bool = True
    enable_markdown: bool = True

    @property
    def channel(self) -> str:
        return "qq"

    @classmethod
    def from_env(cls, workdir: Path | None = None) -> "QQBotConfig":
        saved = read_saved_qq_config(workdir) if workdir else {}
        app_id = _env("HERMES_QQ_APP_ID", "QQ_BOT_APP_ID", "QQ_APP_ID") or _str_config(
            saved, "app_id"
        )
        secret = _env("HERMES_QQ_SECRET", "QQ_BOT_SECRET", "QQ_SECRET") or _str_config(
            saved, "secret"
        )
        if not app_id or not secret:
            raise ValueError(
                "Missing QQ bot credentials. Set HERMES_QQ_APP_ID and HERMES_QQ_SECRET."
            )

        return cls(
            app_id=app_id,
            secret=secret,
            sandbox=_env_bool(
                "HERMES_QQ_SANDBOX",
                "QQ_BOT_SANDBOX",
                default=_bool_config(saved, "sandbox", False),
            ),
            timeout=int(
                _env("HERMES_QQ_TIMEOUT", "QQ_BOT_TIMEOUT")
                or saved.get("timeout")
                or "5"
            ),
            enable_guild=_env_bool(
                "HERMES_QQ_ENABLE_GUILD",
                default=_bool_config(saved, "enable_guild", True),
            ),
            enable_direct=_env_bool(
                "HERMES_QQ_ENABLE_DIRECT",
                default=_bool_config(saved, "enable_direct", True),
            ),
            enable_group=_env_bool(
                "HERMES_QQ_ENABLE_GROUP",
                default=_bool_config(saved, "enable_group", True),
            ),
            enable_c2c=_env_bool(
                "HERMES_QQ_ENABLE_C2C", default=_bool_config(saved, "enable_c2c", True)
            ),
            enable_markdown=_env_bool(
                "HERMES_QQ_ENABLE_MARKDOWN",
                default=_bool_config(saved, "enable_markdown", True),
            ),
        )


class QQBotRunner:
    def __init__(
        self,
        config: QQBotConfig,
        channel_service: ChannelConversationService,
        *,
        log: Callable[[str], None] | None = None,
        log_dir: Path | None = None,
    ):
        self._config = config
        self._channel_service = channel_service
        self._log = log or (lambda message: None)
        self._log_dir = log_dir

    def run(self) -> None:
        try:
            import botpy
        except ImportError as exc:
            raise RuntimeError(
                "qq-botpy is not installed. Run `uv sync` first."
            ) from exc

        if self._log_dir:
            _configure_botpy_logging(self._log_dir)

        intents = botpy.Intents.none()
        if self._config.enable_guild:
            intents.public_guild_messages = True
        if self._config.enable_direct:
            intents.direct_message = True
        if self._config.enable_group or self._config.enable_c2c:
            intents.public_messages = True

        runner = self

        class HermesQQClient(botpy.Client):
            async def on_ready(self):
                name = getattr(self.robot, "name", "unknown")
                runner._log(f"QQ bot ready: {name}")

            async def on_at_message_create(self, message):
                if not runner._config.enable_guild:
                    return
                inbound = ChannelInboundMessage(
                    channel="qq",
                    conversation_id=_guild_conversation_id(message),
                    sender_id=str(getattr(message.author, "id", "")),
                    sender_name=_guild_sender_name(message),
                    text=_clean_qq_text(getattr(message, "content", "")),
                    message_id=getattr(message, "id", None),
                    metadata=_message_metadata(message, "guild_at"),
                )
                outbound = await runner._handle_message(inbound)
                await runner._reply_guild_message(message, outbound)

            async def on_direct_message_create(self, message):
                if not runner._config.enable_direct:
                    return
                inbound = ChannelInboundMessage(
                    channel="qq",
                    conversation_id=_direct_conversation_id(message),
                    sender_id=str(getattr(message.author, "id", "")),
                    sender_name=getattr(message.author, "username", None),
                    text=_clean_qq_text(getattr(message, "content", "")),
                    message_id=getattr(message, "id", None),
                    metadata=_message_metadata(message, "guild_direct"),
                )
                outbound = await runner._handle_message(inbound)
                await runner._reply_direct_message(message, outbound)

            async def on_group_at_message_create(self, message):
                if not runner._config.enable_group:
                    return
                group_openid = getattr(message, "group_openid", "")
                inbound = ChannelInboundMessage(
                    channel="qq",
                    conversation_id=f"group:{group_openid}",
                    sender_id=str(getattr(message.author, "member_openid", "")),
                    text=_clean_qq_text(getattr(message, "content", "")),
                    message_id=getattr(message, "id", None),
                    metadata=_message_metadata(message, "group_at"),
                )
                outbound = await runner._handle_message(inbound)
                await runner._reply_group_message(message, outbound)

            async def on_c2c_message_create(self, message):
                if not runner._config.enable_c2c:
                    return
                user_openid = getattr(message.author, "user_openid", "")
                inbound = ChannelInboundMessage(
                    channel="qq",
                    conversation_id=f"c2c:{user_openid}",
                    sender_id=str(user_openid),
                    text=_clean_qq_text(getattr(message, "content", "")),
                    message_id=getattr(message, "id", None),
                    metadata=_message_metadata(message, "c2c"),
                )
                outbound = await runner._handle_message(inbound)
                await runner._reply_c2c_message(message, outbound)

            async def on_error(
                self, event_method: str, *args: Any, **kwargs: Any
            ) -> None:
                runner._log(f"QQ event error in {event_method}")
                await super().on_error(event_method, *args, **kwargs)

        client = HermesQQClient(
            intents=intents,
            timeout=self._config.timeout,
            is_sandbox=self._config.sandbox,
        )
        client.run(appid=self._config.app_id, secret=self._config.secret)

    async def _handle_message(
        self, message: ChannelInboundMessage
    ) -> ChannelOutboundMessage:
        try:
            return await asyncio.to_thread(
                self._channel_service.handle_inbound, message
            )
        except Exception as exc:
            self._log(f"QQ message handling failed: {exc}")
            return ChannelOutboundMessage(
                channel=message.channel,
                conversation_id=message.conversation_id,
                text="处理消息失败，请稍后再试。",
                chat_id="",
                reply_to_message_id=message.message_id,
                metadata={"error": str(exc)},
            )

    async def _reply_guild_message(
        self, message: Any, outbound: ChannelOutboundMessage
    ) -> None:
        if self._config.enable_markdown and await self._try_reply_markdown(
            message, outbound
        ):
            return
        await message.reply(content=_format_reply(outbound.text))

    async def _reply_direct_message(
        self, message: Any, outbound: ChannelOutboundMessage
    ) -> None:
        if self._config.enable_markdown and await self._try_reply_markdown(
            message, outbound
        ):
            return
        await message.reply(content=_format_reply(outbound.text))

    async def _reply_group_message(
        self, message: Any, outbound: ChannelOutboundMessage
    ) -> None:
        if self._config.enable_markdown and await self._try_reply_markdown(
            message, outbound, msg_type=2
        ):
            return
        await message.reply(msg_type=0, content=_format_reply(outbound.text))

    async def _reply_c2c_message(
        self, message: Any, outbound: ChannelOutboundMessage
    ) -> None:
        if self._config.enable_markdown and await self._try_reply_markdown(
            message, outbound, msg_type=2
        ):
            return
        await message.reply(msg_type=0, content=_format_reply(outbound.text))

    async def _try_reply_markdown(
        self,
        message: Any,
        outbound: ChannelOutboundMessage,
        *,
        msg_type: int | None = None,
    ) -> bool:
        try:
            from botpy.types.message import MarkdownPayload
        except ImportError:
            return False

        try:
            markdown = MarkdownPayload(content=_format_reply(outbound.text))
            kwargs: dict[str, Any] = {"markdown": markdown}
            if msg_type is not None:
                kwargs["msg_type"] = msg_type
            await message.reply(**kwargs)
            return True
        except Exception as exc:
            self._log(f"QQ markdown reply failed, fallback to text: {exc}")
            return False


def build_qq_channel_service(
    settings: Any,
    control_plane_factory: Callable[[], tuple[Any, Any]],
) -> ChannelConversationService:
    chat_service = ChatService(JsonChatStore(settings.workdir / ".hermes" / "qq"))
    link_store = JsonChannelConversationStore(settings.workdir / ".hermes" / "qq")
    responder = ControlPlaneChannelResponder(control_plane_factory)
    return ChannelConversationService(chat_service, link_store, responder)


def read_saved_qq_config(workdir: Path) -> dict[str, Any]:
    settings = _read_settings_file(workdir)
    qq_bot = settings.get("qq_bot")
    return dict(qq_bot) if isinstance(qq_bot, dict) else {}


def write_saved_qq_config(workdir: Path, config: dict[str, Any]) -> None:
    settings = _read_settings_file(workdir)
    settings["qq_bot"] = _filter_qq_config(config)
    _write_settings_file(workdir, settings)


def read_env_qq_config() -> dict[str, Any]:
    config: dict[str, Any] = {}
    _set_if_present(
        config, "app_id", _env("HERMES_QQ_APP_ID", "QQ_BOT_APP_ID", "QQ_APP_ID")
    )
    _set_if_present(
        config, "secret", _env("HERMES_QQ_SECRET", "QQ_BOT_SECRET", "QQ_SECRET")
    )
    _set_if_present(config, "sandbox", _env("HERMES_QQ_SANDBOX", "QQ_BOT_SANDBOX"))
    _set_if_present(config, "timeout", _env("HERMES_QQ_TIMEOUT", "QQ_BOT_TIMEOUT"))
    _set_if_present(config, "enable_guild", _env("HERMES_QQ_ENABLE_GUILD"))
    _set_if_present(config, "enable_direct", _env("HERMES_QQ_ENABLE_DIRECT"))
    _set_if_present(config, "enable_group", _env("HERMES_QQ_ENABLE_GROUP"))
    _set_if_present(config, "enable_c2c", _env("HERMES_QQ_ENABLE_C2C"))
    _set_if_present(config, "enable_markdown", _env("HERMES_QQ_ENABLE_MARKDOWN"))
    return config


class QQInteractionPort(InteractionPort):
    def __init__(self, log: Callable[[str], None] | None = None):
        self._log = log or (lambda message: None)

    def confirm(self, tool_name: str, description: str, tool_display: str = "") -> bool:
        display = tool_display or f"{tool_name}: {description}"
        self._log(f"QQ channel denied interactive confirmation: {display}")
        return False

    def notify_tool_start(self, tool_name: str, tool_display: str = "") -> None:
        display = tool_display or tool_name
        if display:
            self._log(f"QQ channel tool start: {display}")

    def notify_tool_complete(self, tool_name: str, result: Any = None) -> None:
        return None

    def notify_tool_error(self, tool_name: str, error: str) -> None:
        self._log(f"QQ channel tool error: {tool_name}: {error}")

    def on_context_compressed(self, original: int, compressed: int) -> None:
        self._log(f"QQ channel context compressed: {original} -> {compressed}")


def _guild_conversation_id(message: Any) -> str:
    guild_id = getattr(message, "guild_id", "") or "unknown-guild"
    channel_id = getattr(message, "channel_id", "") or "unknown-channel"
    return f"guild:{guild_id}:channel:{channel_id}"


def _direct_conversation_id(message: Any) -> str:
    guild_id = getattr(message, "guild_id", "") or "unknown-dms"
    author_id = getattr(message.author, "id", "") or "unknown-user"
    return f"guild-dm:{guild_id}:user:{author_id}"


def _guild_sender_name(message: Any) -> str | None:
    nick = getattr(getattr(message, "member", None), "nick", None)
    return nick or getattr(message.author, "username", None)


def _clean_qq_text(text: str | None) -> str:
    if not text:
        return ""
    return _MENTION_PATTERN.sub("", text).strip()


def _format_reply(text: str) -> str:
    return text.strip() or "我收到了，但暂时没有生成回复。"


def _configure_botpy_logging(log_dir: Path) -> Path:
    import botpy.logging as botpy_logging

    log_dir.mkdir(parents=True, exist_ok=True)
    handler = dict(botpy_logging.DEFAULT_FILE_HANDLER)
    handler["filename"] = str(log_dir / "%(name)s.log")

    botpy_logging._ext_handlers = []
    botpy_logging.configure_logging(bot_log=None, ext_handlers=[handler], force=True)
    return log_dir / "botpy.log"


def _message_metadata(message: Any, event_type: str) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "event_id": getattr(message, "event_id", None),
        "guild_id": getattr(message, "guild_id", None),
        "channel_id": getattr(message, "channel_id", None),
        "group_openid": getattr(message, "group_openid", None),
        "timestamp": getattr(message, "timestamp", None),
        "attachments": [repr(item) for item in getattr(message, "attachments", [])],
    }


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


def _filter_qq_config(config: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "app_id",
        "secret",
        "sandbox",
        "timeout",
        "enable_guild",
        "enable_direct",
        "enable_group",
        "enable_c2c",
        "enable_markdown",
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
