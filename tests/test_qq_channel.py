import os

from hermes.channels.qq import (
    QQBotConfig,
    _configure_botpy_logging,
    read_saved_qq_config,
    write_saved_qq_config,
)
from hermes.channels.qq import (
    _clean_qq_text,
    _direct_conversation_id,
    _guild_conversation_id,
)


class _Object:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_qq_config_reads_env(monkeypatch):
    monkeypatch.setenv("HERMES_QQ_APP_ID", "appid")
    monkeypatch.setenv("HERMES_QQ_SECRET", "secret")
    monkeypatch.setenv("HERMES_QQ_SANDBOX", "true")
    monkeypatch.setenv("HERMES_QQ_ENABLE_GROUP", "false")
    monkeypatch.setenv("HERMES_QQ_ENABLE_MARKDOWN", "false")

    config = QQBotConfig.from_env()

    assert config.app_id == "appid"
    assert config.secret == "secret"
    assert config.sandbox is True
    assert config.enable_group is False
    assert config.enable_c2c is True
    assert config.enable_markdown is False


def test_qq_config_reports_missing_credentials(monkeypatch):
    for key in ("HERMES_QQ_APP_ID", "QQ_BOT_APP_ID", "QQ_APP_ID"):
        monkeypatch.delenv(key, raising=False)
    for key in ("HERMES_QQ_SECRET", "QQ_BOT_SECRET", "QQ_SECRET"):
        monkeypatch.delenv(key, raising=False)

    try:
        QQBotConfig.from_env()
    except ValueError as exc:
        assert "HERMES_QQ_APP_ID" in str(exc)
    else:
        raise AssertionError("expected missing credential error")


def test_qq_message_helpers():
    assert _clean_qq_text("<@!123456>  你好") == "你好"
    assert _clean_qq_text("<@123456>  你好") == "你好"

    guild_message = _Object(guild_id="g1", channel_id="c1")
    assert _guild_conversation_id(guild_message) == "guild:g1:channel:c1"

    direct_message = _Object(guild_id="d1", author=_Object(id="u1"))
    assert _direct_conversation_id(direct_message) == "guild-dm:d1:user:u1"


def test_qq_config_supports_legacy_env_names(monkeypatch):
    monkeypatch.delenv("HERMES_QQ_APP_ID", raising=False)
    monkeypatch.delenv("HERMES_QQ_SECRET", raising=False)
    monkeypatch.setenv("QQ_BOT_APP_ID", "legacy-appid")
    monkeypatch.setenv("QQ_BOT_SECRET", "legacy-secret")

    config = QQBotConfig.from_env()

    assert config.app_id == "legacy-appid"
    assert config.secret == "legacy-secret"

    os.environ.pop("QQ_BOT_APP_ID", None)
    os.environ.pop("QQ_BOT_SECRET", None)


def test_qq_config_reads_saved_web_settings(tmp_path, monkeypatch):
    monkeypatch.delenv("HERMES_QQ_APP_ID", raising=False)
    monkeypatch.delenv("HERMES_QQ_SECRET", raising=False)
    write_saved_qq_config(
        tmp_path,
        {
            "app_id": "saved-appid",
            "secret": "saved-secret",
            "sandbox": True,
            "timeout": 9,
            "enable_group": False,
            "enable_markdown": False,
        },
    )

    config = QQBotConfig.from_env(tmp_path)

    assert config.app_id == "saved-appid"
    assert config.secret == "saved-secret"
    assert config.sandbox is True
    assert config.timeout == 9
    assert config.enable_group is False
    assert config.enable_markdown is False
    assert read_saved_qq_config(tmp_path)["app_id"] == "saved-appid"


def test_botpy_log_path_is_under_hermes_logs(tmp_path):
    path = _configure_botpy_logging(tmp_path / ".hermes" / "logs")

    assert path == tmp_path / ".hermes" / "logs" / "botpy.log"
