from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel

from web.backend.app_state import WebServiceContainer

router = APIRouter()


class ProjectResponse(BaseModel):
    id: str
    name: str
    path: str
    created_at: datetime
    chat_count: int


def _services(request: Request) -> WebServiceContainer:
    return request.app.state.services


@router.get("", response_model=list[ProjectResponse])
async def list_projects(request: Request) -> list[ProjectResponse]:
    projects = _services(request).project_service.list_projects()
    return [ProjectResponse(**project) for project in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, request: Request) -> ProjectResponse:
    project = _services(request).project_service.get_project(project_id)
    return ProjectResponse(**project)
