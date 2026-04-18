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
│   │       └── projects.py
│   └── core/         # 核心逻辑
│       └── session.py
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
    │   └── ui/       # UI 组件
    ├── hooks/        # 自定义 Hooks
    │   └── useWebSocket.ts
    └── lib/          # 工具函数
        └── utils.ts
```

## 功能特性

- [x] WebSocket 实时通信
- [x] 流式消息显示
- [x] 多模型支持
- [x] 权限控制（默认/完全访问）
- [x] Token 使用量显示
- [x] 聊天历史管理
- [x] 项目列表

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
cd /Users/xinqiangxiong/codes/hm-cli/web/backend
uv run uvicorn main:app --reload --port 8000
```

### 3. 启动前端

```bash
cd /Users/xinqiangxiong/codes/hm-cli/web/frontend
npm run dev
```

### 4. 访问

打开 http://localhost:3000

## API 文档

启动后端后访问 http://localhost:8000/docs 查看完整 API 文档。

### WebSocket API

```javascript
// 连接
ws://localhost:8000/ws/chat/{session_id}

// 发送消息
{
  "type": "chat",
  "message": "...",
  "permissions": "default",
  "model": "doubao-seed-2.0"
}

// 接收流式响应
{ "type": "stream_start" }
{ "type": "stream_delta", "delta": "..." }
{ "type": "stream_end" }
```

## 后续计划

1. **Phase 1**: 基础框架 ✓
2. **Phase 2**: 集成真实 Agent 核心
3. **Phase 3**: 代码编辑器集成
4. **Phase 4**: 多模态支持（图片、文件）
5. **Phase 5**: 部署和优化
