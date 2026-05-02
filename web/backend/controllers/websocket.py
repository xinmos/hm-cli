from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from web.backend.services.session_service import SessionManager

router = APIRouter()


@router.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    session_manager: SessionManager = websocket.app.state.session_manager
    await websocket.accept()
    await session_manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await session_manager.handle_message(session_id, data)
    except WebSocketDisconnect:
        await session_manager.disconnect(session_id)
    except RuntimeError:
        await session_manager.disconnect(session_id)
