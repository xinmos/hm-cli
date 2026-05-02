from __future__ import annotations

from fastapi import APIRouter, Request

from web.backend.controllers.dependencies import get_services
from web.backend.models.project import ProjectResponse
from web.backend.services.project_service import ProjectApiService

router = APIRouter()


def _project_service(request: Request) -> ProjectApiService:
    return ProjectApiService(get_services(request))


@router.get("", response_model=list[ProjectResponse])
async def list_projects(request: Request) -> list[ProjectResponse]:
    return _project_service(request).list_projects()


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, request: Request) -> ProjectResponse:
    return _project_service(request).get_project(project_id)
