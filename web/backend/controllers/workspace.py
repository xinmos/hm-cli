from __future__ import annotations

from fastapi import APIRouter, Query, Request

from web.backend.controllers.dependencies import get_services, to_http_error
from web.backend.models.workspace import (
    WorkspaceFileItem,
    WorkspaceFileResponse,
    WorkspaceFileUpdate,
    WorkspaceResponse,
)
from web.backend.services.exceptions import BackendServiceError
from web.backend.services.workspace_service import WorkspaceApiService

router = APIRouter()


def _workspace_service(request: Request) -> WorkspaceApiService:
    return WorkspaceApiService(get_services(request))


@router.get("", response_model=WorkspaceResponse)
async def get_workspace(request: Request) -> WorkspaceResponse:
    return _workspace_service(request).get_workspace()


@router.get("/files", response_model=list[WorkspaceFileItem])
async def list_workspace_files(
    request: Request,
    path: str = Query(default=""),
) -> list[WorkspaceFileItem]:
    try:
        return _workspace_service(request).list_files(path)
    except BackendServiceError as exc:
        raise to_http_error(exc) from exc


@router.get("/file", response_model=WorkspaceFileResponse)
async def read_workspace_file(
    request: Request,
    path: str = Query(..., min_length=1),
) -> WorkspaceFileResponse:
    try:
        return _workspace_service(request).read_file(path)
    except BackendServiceError as exc:
        raise to_http_error(exc) from exc


@router.put("/file", response_model=WorkspaceFileResponse)
async def update_workspace_file(
    payload: WorkspaceFileUpdate,
    request: Request,
    path: str = Query(..., min_length=1),
) -> WorkspaceFileResponse:
    try:
        return _workspace_service(request).update_file(path, payload.content)
    except BackendServiceError as exc:
        raise to_http_error(exc) from exc
