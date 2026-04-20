from __future__ import annotations

from hermes.app.ports import SkillInfo, SkillRepository


class SkillService:
    def __init__(self, repository: SkillRepository):
        self._repo = repository

    def get(self, name: str) -> SkillInfo | None:
        return self._repo.get(name)

    def get_by_slash_command(self, cmd: str) -> SkillInfo | None:
        return self._repo.get_by_slash_command(cmd)

    def list_skills(self) -> list[SkillInfo]:
        return self._repo.list_skills()
