from hermes.channels.feishu import (
    FeishuBotConfig,
    _build_markdown_card,
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
    monkeypatch.setenv("HERMES_FEISHU_ENABLE_MARKDOWN", "false")
    monkeypatch.setenv("HERMES_FEISHU_ENABLE_STREAMING", "false")

    config = FeishuBotConfig.from_env()

    assert config.app_id == "appid"
    assert config.app_secret == "secret"
    assert config.domain == "https://open.larksuite.com"
    assert config.auto_reconnect is False
    assert config.enable_markdown is False
    assert config.enable_streaming is False


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
            "enable_markdown": False,
            "enable_streaming": False,
        },
    )

    config = FeishuBotConfig.from_env(tmp_path)

    assert config.app_id == "saved-appid"
    assert config.app_secret == "saved-secret"
    assert config.verification_token == "token"
    assert config.encrypt_key == "key"
    assert config.auto_reconnect is False
    assert config.enable_markdown is False
    assert config.enable_streaming is False
    assert read_saved_feishu_config(tmp_path)["app_id"] == "saved-appid"


def test_feishu_markdown_card_uses_card_json_2():
    card = _build_markdown_card("**你好**", streaming=True)

    assert card["schema"] == "2.0"
    assert card["config"]["streaming_mode"] is True
    assert card["config"]["update_multi"] is True
    assert card["body"]["elements"][0] == {
        "tag": "markdown",
        "element_id": "hermes_answer",
        "content": "**你好**",
    }


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
