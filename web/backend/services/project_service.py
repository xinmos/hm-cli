from __future__ import annotations

from web.backend.models.project import ProjectResponse
from web.backend.services.container import WebServiceContainer


class ProjectApiService:
    def __init__(self, services: WebServiceContainer):
        self._services = services

    def list_projects(self) -> list[ProjectResponse]:
        projects = self._services.project_service.list_projects()
        return [ProjectResponse(**project) for project in projects]

    def get_project(self, project_id: str) -> ProjectResponse:
        project = self._services.project_service.get_project(project_id)
        return ProjectResponse(**project)
