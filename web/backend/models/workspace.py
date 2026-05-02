from __future__ import annotations

from pydantic import BaseModel


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
