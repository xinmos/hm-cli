from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from web.backend.controllers import chats, health, models, projects, skills, websocket, workspace
from web.backend.services import SessionManager, build_web_services


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
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(skills.router, prefix="/api/skills", tags=["skills"])
app.include_router(workspace.router, prefix="/api/workspace", tags=["workspace"])
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(websocket.router)
app.include_router(health.router)
