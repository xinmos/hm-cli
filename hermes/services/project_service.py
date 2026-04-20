from datetime import datetime

from hermes.app.settings import Settings


class ProjectService:
    def __init__(self, settings: Settings):
        self._settings = settings

    def list_projects(self) -> list[dict]:
        project_name = self._settings.workdir.name
        return [
            {
                "id": project_name,
                "name": project_name,
                "path": str(self._settings.workdir),
                "created_at": datetime.now(),
                "chat_count": 0,
            }
        ]

    def get_project(self, project_id: str) -> dict:
        for project in self.list_projects():
            if project["id"] == project_id:
                return project
        return {
            "id": project_id,
            "name": project_id,
            "path": str(self._settings.workdir),
            "created_at": datetime.now(),
            "chat_count": 0,
        }
