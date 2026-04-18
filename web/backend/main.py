from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.routes import chats, projects, models
from core.session import SessionManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.session_manager = SessionManager()
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
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chats.router, prefix="/api/chats", tags=["chats"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(models.router, prefix="/api/models", tags=["models"])


@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    session_manager: SessionManager = websocket.app.state.session_manager
    await session_manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await session_manager.handle_message(session_id, data)
    except WebSocketDisconnect:
        await session_manager.disconnect(session_id)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
