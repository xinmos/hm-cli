# Hermes Web

Hermes CLI 的 Web 界面，提供类似 Trae/Claude Web 的聊天体验。

## 架构

```
web/
├── backend/          # FastAPI 后端
│   ├── main.py       # FastAPI 入口
│   ├── api/          # REST API 路由
│   │   └── routes/
│   │       ├── chats.py
│   │       ├── models.py
│   │       ├── projects.py
│   │       └── workspace.py
│   └── session_manager.py
│
└── frontend/         # Next.js 前端
    ├── app/          # App Router
    │   ├── page.tsx  # 主页面
    │   ├── layout.tsx
    │   └── globals.css
    ├── components/   # 组件
    │   ├── Chat/     # 聊天组件
    │   ├── Header/   # 头部组件
    │   ├── Sidebar/  # 侧边栏组件
    │   ├── Workspace/ # 工作区文件编辑器
    │   └── ui/       # UI 组件
    ├── hooks/        # 自定义 Hooks
    └── lib/          # 工具函数
        ├── api.ts
        └── utils.ts
```

## 功能特性

- [x] SSE 流式消息推送
- [x] 流式消息显示
- [x] 多模型支持
- [x] 权限控制（默认/完全访问）
- [x] Token 使用量显示
- [x] 聊天历史管理
- [x] 项目列表
- [x] 真实 Agent 核心集成
- [x] 工作区文件浏览与编辑
- [x] 图片与文件附件上下文
- [x] Docker Compose 部署配置

## 开发

### 1. 安装依赖

```bash
# 后端依赖已添加到主项目
cd /Users/xinqiangxiong/codes/hm-cli
uv sync --extra web

# 前端依赖
cd web/frontend
npm install
```

### 2. 启动后端

```bash
cd /Users/xinqiangxiong/codes/hm-cli
uv sync --extra web
uv run python -m uvicorn web.backend.main:app --reload --port 8000 --host 0.0.0.0
```

### 3. 启动前端

```bash
cd /Users/xinqiangxiong/codes/hm-cli/web/frontend
npm run dev
```

### 4. 访问

打开 http://localhost:3000

### 5. 日志目录

开发日志统一写入：

```bash
/Users/xinqiangxiong/codes/hm-cli/.hermes/logs/
```

常用文件：

```bash
.hermes/logs/web-backend.log
.hermes/logs/web-frontend.log
```

### 6. Web 数据目录

Web 会话与聊天数据统一写入：

```bash
/Users/xinqiangxiong/codes/hm-cli/.hermes/web/
```

其中包括：

```bash
.hermes/web/chats.json
.hermes/web/messages/*.jsonl
```

## API 文档

启动后端后访问 http://localhost:8000/docs 查看完整 API 文档。

### SSE API

```javascript
// 发送消息并直接接收流式响应
POST /api/chats/{chat_id}/messages/stream
{
  "message": "...",
  "permissions": "default",
  "model": "doubao-seed-2.0"
}

// text/event-stream 事件
event: stream_start
data: { "type": "stream_start" }

event: stream_delta
data: { "type": "stream_delta", "delta": "..." }

event: stream_end
data: { "type": "stream_end" }
```

### Workspace API

```javascript
GET /api/workspace
GET /api/workspace/files?path=web/frontend
GET /api/workspace/file?path=README.md
PUT /api/workspace/file?path=README.md
```

### 部署

```bash
cd /Users/xinqiangxiong/codes/hm-cli/web
docker compose up --build
```

容器启动后：

```bash
前端界面: http://localhost:3000
后端 API: http://localhost:8000
健康检查: http://localhost:8000/health
```

## 后续计划

1. **Phase 1**: 基础框架 ✓
2. **Phase 2**: 集成真实 Agent 核心 ✓
3. **Phase 3**: 代码编辑器集成 ✓
4. **Phase 4**: 多模态支持（图片、文件）✓
5. **Phase 5**: 部署和优化 ✓
