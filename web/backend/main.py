from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from web.backend.api.routes import chats, models, projects, workspace
from web.backend.app_state import build_web_services
from web.backend.session_manager import SessionManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    services = build_web_services()
    app.state.services = services
    app.state.session_manager = SessionManager(services)
    yield
    await app.state.session_manager.close()


app = FastAPI(
    title="Hermes Web API",
    description="Web interface for Hermes CLI",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chats.router, prefix="/api", tags=["chats"])
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(models.router, prefix="/api", tags=["models"])
app.include_router(workspace.router, prefix="/api/workspace", tags=["workspace"])


@app.websocket("/ws/chat/{session_id}")
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


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "api": "Hermes Web API",
        "streaming": "sse",
        "workspace": "ready",
    }
