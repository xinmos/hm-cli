from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from web.backend.app_state import WebServiceContainer

router = APIRouter()


class WorkspaceResponse(BaseModel):
    project_name: str
    project_path: str
    branch: str
    model: str
    context_window: int


class WorkspaceFileItem(BaseModel):
    name: str
    path: str
    type: str
    size: int | None = None


class WorkspaceFileResponse(BaseModel):
    path: str
    content: str
    size: int


class WorkspaceFileUpdate(BaseModel):
    content: str


def _services(request: Request) -> WebServiceContainer:
    return request.app.state.services


def _resolve_workspace_path(root: Path, relative_path: str = "") -> Path:
    candidate = (root / relative_path.lstrip("/")).resolve()
    root = root.resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(status_code=400, detail="Path escapes workspace")
    return candidate


def _to_relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _is_hidden_or_heavy(path: Path, root: Path) -> bool:
    ignored_names = {
        ".git",
        ".hermes",
        ".next",
        ".venv",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
    }
    try:
        relative_parts = path.resolve().relative_to(root.resolve()).parts
    except ValueError:
        return True
    return any(part in ignored_names for part in relative_parts)


@router.get("", response_model=WorkspaceResponse)
async def get_workspace(request: Request) -> WorkspaceResponse:
    services = _services(request)
    project = services.project_service.get_project(services.settings.workdir.name)
    return WorkspaceResponse(
        project_name=project["name"],
        project_path=project["path"],
        branch=project.get("branch", "main"),
        model=services.settings.model_name,
        context_window=services.settings.context_window,
    )


@router.get("/files", response_model=list[WorkspaceFileItem])
async def list_workspace_files(
    request: Request,
    path: str = Query(default=""),
) -> list[WorkspaceFileItem]:
    root = _services(request).settings.workdir
    target = _resolve_workspace_path(root, path)
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")

    items: list[WorkspaceFileItem] = []
    for child in sorted(target.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
        if _is_hidden_or_heavy(child, root):
            continue
        items.append(
            WorkspaceFileItem(
                name=child.name,
                path=_to_relative(root, child),
                type="directory" if child.is_dir() else "file",
                size=child.stat().st_size if child.is_file() else None,
            )
        )
    return items


@router.get("/file", response_model=WorkspaceFileResponse)
async def read_workspace_file(
    request: Request,
    path: str = Query(..., min_length=1),
) -> WorkspaceFileResponse:
    root = _services(request).settings.workdir
    target = _resolve_workspace_path(root, path)
    if not target.exists() or not target.is_file() or _is_hidden_or_heavy(target, root):
        raise HTTPException(status_code=404, detail="File not found")

    size = target.stat().st_size
    if size > 1024 * 1024:
        raise HTTPException(status_code=413, detail="File is too large to edit")

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=415, detail="Only UTF-8 text files can be edited") from exc

    return WorkspaceFileResponse(
        path=_to_relative(root, target),
        content=content,
        size=size,
    )


@router.put("/file", response_model=WorkspaceFileResponse)
async def update_workspace_file(
    payload: WorkspaceFileUpdate,
    request: Request,
    path: str = Query(..., min_length=1),
) -> WorkspaceFileResponse:
    root = _services(request).settings.workdir
    target = _resolve_workspace_path(root, path)
    if not target.exists() or not target.is_file() or _is_hidden_or_heavy(target, root):
        raise HTTPException(status_code=404, detail="File not found")

    target.write_text(payload.content, encoding="utf-8")
    return WorkspaceFileResponse(
        path=_to_relative(root, target),
        content=payload.content,
        size=target.stat().st_size,
    )
