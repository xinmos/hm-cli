from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from threading import Lock
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect

from hermes.app import InteractionPort
from hermes.app.bootstrap import ControlPlaneApp, ControlPlaneRuntime
from hermes.app.ports import ChatMessageRecord

from web.backend.app_state import WebServiceContainer


class WebInteractionPort(InteractionPort):
    def __init__(self):
        self._emit: Callable[[dict], None] | None = None
        self._lock = Lock()

    def bind(self, emit: Callable[[dict], None]) -> None:
        with self._lock:
            self._emit = emit

    def unbind(self) -> None:
        with self._lock:
            self._emit = None

    def confirm(self, tool_name: str, description: str, tool_display: str = "") -> bool:
        self._emit_event({
            "type": "tool_start",
            "tool_display": tool_display or tool_name or "Tool",
        })
        return False

    def notify_tool_start(self, tool_name: str, tool_display: str = "") -> None:
        self._emit_event({
            "type": "tool_start",
            "tool_display": tool_display or tool_name or "Tool",
        })

    def notify_tool_complete(self, tool_name: str, result: object = None) -> None:
        return None

    def notify_tool_error(self, tool_name: str, error: str) -> None:
        return None

    def on_context_compressed(self, original: int, compressed: int) -> None:
        return None

    def _emit_event(self, event: dict) -> None:
        with self._lock:
            emit = self._emit
        if emit is None:
            return
        emit(event)


class WebChatSession:
    def __init__(
        self,
        session_id: str,
        websocket: WebSocket,
        services: WebServiceContainer,
        control_plane: ControlPlaneApp,
        runtime: ControlPlaneRuntime,
        interaction: WebInteractionPort,
    ):
        self.session_id = session_id
        self.websocket = websocket
        self._services = services
        self._control_plane = control_plane
        self._runtime = runtime
        self._interaction = interaction
        self._closed = False

    async def send_message(self, data: dict) -> bool:
        if self._closed:
            return False
        try:
            await self.websocket.send_json(data)
            return True
        except WebSocketDisconnect:
            self._closed = True
            return False
        except RuntimeError:
            self._closed = True
            return False

    async def handle_chat_message(self, data: dict) -> None:
        message = data.get("message", "").strip()
        chat_id = data.get("chat_id", self.session_id)
        if not message:
            await self.send_message({"type": "error", "error": "Empty message"})
            return

        user_record = self._build_message("user", message)
        self._services.chat_service.append_message(chat_id, user_record)

        if not await self.send_message({
            "type": "ack",
            "message_id": data.get("message_id"),
        }):
            return
        if not await self.send_message({"type": "stream_start"}):
            return

        loop = asyncio.get_running_loop()
        event_queue: asyncio.Queue[dict | None] = asyncio.Queue()

        def emit_from_worker(event: dict | None) -> None:
            loop.call_soon_threadsafe(event_queue.put_nowait, event)

        self._interaction.bind(emit_from_worker)
        worker = asyncio.create_task(asyncio.to_thread(self._stream_response, message, emit_from_worker))
        assistant_chunks: list[str] = []

        try:
            while True:
                event = await event_queue.get()
                if event is None:
                    break

                if event.get("type") == "stream_delta":
                    assistant_chunks.append(event.get("delta", ""))
                if not await self.send_message(event):
                    worker.cancel()
                    return
        finally:
            self._interaction.unbind()
            await asyncio.gather(worker, return_exceptions=True)

        if not await self.send_message({"type": "stream_end"}):
            return

        assistant_text = "".join(assistant_chunks)
        assistant_record = self._build_message("assistant", assistant_text)
        self._services.chat_service.append_message(chat_id, assistant_record)

        await self.send_message({
            "type": "status",
            "tokens_used": self._control_plane.agent.get_token_count(),
            "tokens_total": self._services.settings.context_window,
            "model": self._services.settings.model_name,
        })

    async def close(self) -> None:
        self._closed = True
        self._runtime.stop()

    def _build_message(self, role: str, content: str) -> ChatMessageRecord:
        return ChatMessageRecord(
            id=f"msg-{uuid4().hex[:12]}",
            role=role,
            content=content,
            created_at=datetime.now().isoformat(),
        )

    def _stream_response(
        self,
        message: str,
        emit: Callable[[dict | None], None],
    ) -> None:
        try:
            result = self._control_plane.handle(message)
            if result.get("type") == "error":
                emit({"type": "error", "error": result.get("message", "Unknown error")})
                return

            for chunk in result.get("response", []):
                emit({
                    "type": "stream_delta",
                    "delta": chunk,
                })
        except Exception as exc:
            emit({"type": "error", "error": str(exc)})
        finally:
            emit(None)


class SessionManager:
    def __init__(self, services: WebServiceContainer):
        self._services = services
        self._sessions: dict[str, WebChatSession] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        existing = self._sessions.pop(session_id, None)
        if existing is not None:
            await existing.close()

        interaction = WebInteractionPort()
        control_plane, runtime = self._services.create_control_plane(interaction_port=interaction)
        session = WebChatSession(
            session_id=session_id,
            websocket=websocket,
            services=self._services,
            control_plane=control_plane,
            runtime=runtime,
            interaction=interaction,
        )
        self._sessions[session_id] = session

        await session.send_message({
            "type": "connected",
            "session_id": session_id,
        })

    async def disconnect(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is not None:
            await session.close()

    async def handle_message(self, session_id: str, data: dict) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return

        msg_type = data.get("type", "chat")
        if msg_type == "chat":
            await session.handle_chat_message(data)
            return
        if msg_type == "ping":
            await session.send_message({"type": "pong"})
            return
        await session.send_message({"type": "error", "error": f"Unknown message type: {msg_type}"})

    async def close(self) -> None:
        for session in list(self._sessions.values()):
            await session.close()
        self._sessions.clear()
