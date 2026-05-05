# 多渠道对话

Hermes 的外部渠道入口复用同一条主链路：

1. 渠道适配器把 QQ、飞书等平台事件转换成 `ChannelInboundMessage`。
2. `ChannelConversationService` 用 `channel + conversation_id` 找到或创建 Hermes chat。
3. 历史消息从 `ChatService` 读取，交给 `ControlPlaneApp` 生成回复。
4. 回复以 `ChannelOutboundMessage` 返回给渠道适配器，由适配器调用平台 API 发送。

这样 QQ 群、QQ 私聊、飞书群聊、飞书单聊都只需要提供不同的 `conversation_id`，不会污染 agent 核心。

## 当前模块

- `hermes.app.ports`: 渠道消息、渠道会话映射和发送网关协议。
- `hermes.infra.persistence.json_channel_store.JsonChannelConversationStore`: JSON 文件映射存储。
- `hermes.services.channel_service.ChannelConversationService`: 多渠道消息编排。
- `hermes.channels.qq`: 基于官方 `qq-botpy` 的 QQ 运行器，支持频道 @、频道私信、QQ群 @、好友私聊。
- `hermes.channels.feishu`: 基于官方 `lark-oapi` 的飞书运行器，通过 WebSocket 长连接接收消息事件并回复文本消息。

## QQ 官方机器人

依赖使用腾讯官方 SDK `qq-botpy`。运行前配置环境变量：

```bash
HERMES_QQ_APP_ID=你的 BotAppID
HERMES_QQ_SECRET=你的 AppSecret
HERMES_QQ_SANDBOX=false
HERMES_QQ_ENABLE_MARKDOWN=true
```

也可以在 Web 页面打开“设置 -> 渠道配置”，填写 BotAppID、AppSecret、沙箱环境和监听入口。页面配置会保存到 `.hermes/settings.json` 的 `qq_bot` 节点；如果同时设置环境变量，环境变量优先。

启动：

```bash
uv run python cli.py qq
```

默认监听：

- 频道内 @ 机器人消息：`on_at_message_create`
- 频道私信消息：`on_direct_message_create`
- QQ 群 @ 机器人消息：`on_group_at_message_create`
- QQ 好友私聊消息：`on_c2c_message_create`

可以用环境变量关闭某类入口：

```bash
HERMES_QQ_ENABLE_GUILD=false
HERMES_QQ_ENABLE_DIRECT=false
HERMES_QQ_ENABLE_GROUP=false
HERMES_QQ_ENABLE_C2C=false
```

会话映射规则：

- 频道子频道：`guild:<guild_id>:channel:<channel_id>`
- 频道私信：`guild-dm:<guild_id>:user:<user_id>`
- QQ 群：`group:<group_openid>`
- QQ 好友：`c2c:<user_openid>`

QQ 渠道的聊天数据存储在 `.hermes/qq/`，不会和 Web UI 的 `.hermes/web/` 对话混在一起。
QQ SDK 日志统一写入 `.hermes/logs/botpy.log`。QQ 官方机器人不支持同一条消息逐字流式更新，因此 QQ 适配器会等完整回复生成后发送；核心 `ChannelConversationService.stream_inbound()` 仍保留给后续真正支持流式或消息编辑的平台复用。

## 飞书机器人

依赖使用飞书官方 SDK `lark-oapi`。运行前配置环境变量：

```bash
HERMES_FEISHU_APP_ID=你的 App ID
HERMES_FEISHU_APP_SECRET=你的 App Secret
HERMES_FEISHU_DOMAIN=https://open.feishu.cn
HERMES_FEISHU_AUTO_RECONNECT=true
```

也可以在 Web 页面打开“设置 -> 渠道配置”，填写 App ID、App Secret、事件订阅 Token、Encrypt Key 和 OpenAPI 域名。页面配置会保存到 `.hermes/settings.json` 的 `feishu_bot` 节点；如果同时设置环境变量，环境变量优先。

启动：

```bash
uv run python cli.py feishu
```

飞书渠道使用官方 SDK 的 WebSocket 长连接接收 `im.message.receive_v1` 事件，不需要额外暴露 HTTP webhook。需要在飞书开放平台启用机器人能力，并订阅“接收消息”事件。

默认支持文本消息和富文本 `post` 消息解析，会自动去掉 @ 机器人标记。会话映射规则：

- 群聊：`chat:<chat_id>`
- 单聊：`chat:<chat_id>`，如果事件没有 `chat_id` 则回退到 `chat:<sender_id>`

飞书渠道的聊天数据存储在 `.hermes/feishu/`，不会和 Web UI、QQ 渠道的数据混在一起。飞书消息回复使用平台文本消息格式；如果后续平台开放流式或消息编辑能力，可以复用核心 `ChannelConversationService.stream_inbound()` 做平台侧增量更新。

## 适配器接入要点

新渠道适配器需要做三件事：

1. 校验平台签名、解密或 challenge。
2. 解析平台事件为 `ChannelInboundMessage`，其中 `channel` 分别使用 `qq` 或 `feishu`。
3. 调用 `ChannelConversationService.handle_inbound()`，再把 `ChannelOutboundMessage.text` 发回平台。

如果平台支持群聊和私聊，建议 conversation id 使用稳定前缀，例如 `group:<group_open_id>` 或 `user:<user_open_id>`。
