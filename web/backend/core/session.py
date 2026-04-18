import json
from typing import Dict, Optional
from fastapi import WebSocket


class ChatSession:
    def __init__(self, session_id: str, websocket: WebSocket):
        self.session_id = session_id
        self.websocket = websocket
        self.chat_history = []
        self.current_model = "doubao-seed-2.0"
        self.permissions = "default"

    async def send_message(self, data: dict):
        await self.websocket.send_json(data)

    async def handle_chat_message(self, data: dict):
        message = data.get("message", "")
        self.permissions = data.get("permissions", "default")

        # 添加用户消息到历史
        self.chat_history.append({"role": "user", "content": message})

        # 发送确认
        await self.send_message({
            "type": "ack",
            "message_id": data.get("message_id"),
        })

        # 模拟流式响应（后续替换为真实 Agent 调用）
        await self.send_message({
            "type": "stream_start",
        })

        # 模拟 AI 响应（后续使用真实 AgentSession）
        response_content = f"收到消息: {message}\n\n这是一个模拟响应。后续将接入真实的 Agent 逻辑。"

        for chunk in response_content:
            await self.send_message({
                "type": "stream_delta",
                "delta": chunk,
            })

        await self.send_message({
            "type": "stream_end",
        })

        # 添加 AI 响应到历史
        self.chat_history.append({"role": "assistant", "content": response_content})

        # 发送状态更新
        await self.send_message({
            "type": "status",
            "tokens_used": len("".join([m["content"] for m in self.chat_history])),
            "tokens_total": 128000,
            "model": self.current_model,
        })


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, ChatSession] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        session = ChatSession(session_id, websocket)
        self.sessions[session_id] = session
        await session.send_message({
            "type": "connected",
            "session_id": session_id,
        })

    async def disconnect(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]

    async def handle_message(self, session_id: str, data: dict):
        if session_id not in self.sessions:
            return

        session = self.sessions[session_id]
        msg_type = data.get("type", "chat")

        if msg_type == "chat":
            await session.handle_chat_message(data)
        elif msg_type == "ping":
            await session.send_message({"type": "pong"})

    async def close(self):
        for session in list(self.sessions.values()):
            await session.websocket.close()
        self.sessions.clear()
