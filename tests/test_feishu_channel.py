from hermes.channels.feishu import (
    FeishuBotConfig,
    _clean_feishu_text,
    _extract_message_text,
    read_saved_feishu_config,
    write_saved_feishu_config,
)


class _Object:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_feishu_config_reads_env(monkeypatch):
    monkeypatch.setenv("HERMES_FEISHU_APP_ID", "appid")
    monkeypatch.setenv("HERMES_FEISHU_APP_SECRET", "secret")
    monkeypatch.setenv("HERMES_FEISHU_DOMAIN", "https://open.larksuite.com")
    monkeypatch.setenv("HERMES_FEISHU_AUTO_RECONNECT", "false")

    config = FeishuBotConfig.from_env()

    assert config.app_id == "appid"
    assert config.app_secret == "secret"
    assert config.domain == "https://open.larksuite.com"
    assert config.auto_reconnect is False


def test_feishu_config_reads_saved_web_settings(tmp_path, monkeypatch):
    monkeypatch.delenv("HERMES_FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("HERMES_FEISHU_APP_SECRET", raising=False)
    write_saved_feishu_config(
        tmp_path,
        {
            "app_id": "saved-appid",
            "app_secret": "saved-secret",
            "verification_token": "token",
            "encrypt_key": "key",
            "domain": "https://open.feishu.cn",
            "auto_reconnect": False,
        },
    )

    config = FeishuBotConfig.from_env(tmp_path)

    assert config.app_id == "saved-appid"
    assert config.app_secret == "saved-secret"
    assert config.verification_token == "token"
    assert config.encrypt_key == "key"
    assert config.auto_reconnect is False
    assert read_saved_feishu_config(tmp_path)["app_id"] == "saved-appid"


def test_feishu_text_message_extraction():
    message = _Object(
        message_type="text",
        content='{"text":"<at user_id=\\"all\\">Hermes</at> 你好"}',
        mentions=[],
    )

    assert _extract_message_text(message) == "你好"


def test_feishu_post_message_extraction():
    message = _Object(
        message_type="post",
        content='{"content":[[{"tag":"text","text":"第一段"},{"tag":"at","name":"Bot"}],[{"tag":"text","text":"第二段"}]]}',
        mentions=[],
    )

    assert _extract_message_text(message) == "第一段 Bot 第二段"


def test_feishu_clean_removes_mention_keys():
    message = _Object(mentions=[_Object(key="@_user_1")])

    assert _clean_feishu_text("@_user_1 继续", message) == "继续"
