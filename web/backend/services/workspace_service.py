from __future__ import annotations

from pathlib import Path

from web.backend.models.workspace import (
    WorkspaceFileItem,
    WorkspaceFileResponse,
    WorkspaceResponse,
)
from web.backend.services.container import WebServiceContainer
from web.backend.services.exceptions import (
    NotFoundError,
    PayloadTooLargeError,
    UnsupportedMediaError,
    ValidationError,
)


class WorkspaceApiService:
    def __init__(self, services: WebServiceContainer):
        self._services = services

    def get_workspace(self) -> WorkspaceResponse:
        project = self._services.project_service.get_project(self._services.settings.workdir.name)
        return WorkspaceResponse(
            project_name=project["name"],
            project_path=project["path"],
            branch=project.get("branch", "main"),
            model=self._services.llm_config.get_effective_config().model,
            context_window=self._services.settings.context_window,
        )

    def list_files(self, path: str = "") -> list[WorkspaceFileItem]:
        root = self._services.settings.workdir
        target = self._resolve_workspace_path(root, path)
        if not target.exists() or not target.is_dir():
            raise NotFoundError("Directory not found")

        items: list[WorkspaceFileItem] = []
        for child in sorted(target.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
            if self._is_hidden_or_heavy(child, root):
                continue
            items.append(
                WorkspaceFileItem(
                    name=child.name,
                    path=self._to_relative(root, child),
                    type="directory" if child.is_dir() else "file",
                    size=child.stat().st_size if child.is_file() else None,
                )
            )
        return items

    def read_file(self, path: str) -> WorkspaceFileResponse:
        root = self._services.settings.workdir
        target = self._resolve_workspace_path(root, path)
        self._ensure_editable_file(target, root)

        size = target.stat().st_size
        if size > 1024 * 1024:
            raise PayloadTooLargeError("File is too large to edit")

        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise UnsupportedMediaError("Only UTF-8 text files can be edited") from exc

        return WorkspaceFileResponse(
            path=self._to_relative(root, target),
            content=content,
            size=size,
        )

    def update_file(self, path: str, content: str) -> WorkspaceFileResponse:
        root = self._services.settings.workdir
        target = self._resolve_workspace_path(root, path)
        self._ensure_editable_file(target, root)

        target.write_text(content, encoding="utf-8")
        return WorkspaceFileResponse(
            path=self._to_relative(root, target),
            content=content,
            size=target.stat().st_size,
        )

    def _ensure_editable_file(self, target: Path, root: Path) -> None:
        if not target.exists() or not target.is_file() or self._is_hidden_or_heavy(target, root):
            raise NotFoundError("File not found")

    def _resolve_workspace_path(self, root: Path, relative_path: str = "") -> Path:
        candidate = (root / relative_path.lstrip("/")).resolve()
        root = root.resolve()
        if candidate != root and root not in candidate.parents:
            raise ValidationError("Path escapes workspace")
        return candidate

    def _to_relative(self, root: Path, path: Path) -> str:
        return path.resolve().relative_to(root.resolve()).as_posix()

    def _is_hidden_or_heavy(self, path: Path, root: Path) -> bool:
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
