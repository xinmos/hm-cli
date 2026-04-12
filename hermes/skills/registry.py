from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, Optional

import yaml


@dataclass
class Skill:
    name: str
    description: str
    version: str = "1.0.0"
    instructions: str = ""
    slash_command: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    file_path: Path | None = None

    def __post_init__(self):
        if not self.slash_command:
            self.slash_command = f"/{self.name}"


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._slash_commands: dict[str, str] = {}

    def register(self, skill: Skill) -> None:
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' already registered")
        self._skills[skill.name] = skill
        self._slash_commands[skill.slash_command] = skill.name

    def unregister(self, name: str) -> bool:
        if name in self._skills:
            skill = self._skills[name]
            del self._skills[name]
            if skill.slash_command in self._slash_commands:
                del self._slash_commands[skill.slash_command]
            return True
        return False

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def get_by_slash_command(self, cmd: str) -> Skill | None:
        name = self._slash_commands.get(cmd)
        if name:
            return self._skills.get(name)
        return self._skills.get(cmd.lstrip("/"))

    def list_skills(self) -> list[Skill]:
        return list(self._skills.values())

    def is_slash_command(self, cmd: str) -> bool:
        if cmd in self._slash_commands:
            return True
        return cmd.lstrip("/") in self._skills

    def load_from_file(self, path: str) -> Skill:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Skill file not found: {path}")

        content = path.read_text(encoding="utf-8")
        skill = self._parse_skill(content, path.stem)
        self.register(skill)
        return skill

    def _parse_skill(self, content: str, default_name: str) -> Skill:
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)

        if frontmatter_match:
            meta = yaml.safe_load(frontmatter_match.group(1)) or {}
            instructions = frontmatter_match.group(2).strip()
        else:
            meta = {}
            instructions = content.strip()

        name = meta.get("name", default_name)
        description = meta.get("description", "")
        version = meta.get("version", "1.0.0")
        slash_command = meta.get("slash_command", "")
        metadata = {k: v for k, v in meta.items() if k not in ["name", "description", "version", "slash_command"]}

        return Skill(
            name=name,
            description=description,
            version=version,
            instructions=instructions,
            slash_command=slash_command or f"/{name}",
            metadata=metadata,
            file_path=Path(default_name) if not isinstance(default_name, Path) else default_name,
        )

    def load_from_directory(self, directory: str) -> List[Skill]:
        directory = Path(directory)
        if not directory.exists():
            return []

        loaded = []
        for ext in ["*.md"]:
            for file_path in directory.glob(ext):
                if file_path.name.startswith("_"):
                    continue
                try:
                    skill = self.load_from_file(str(file_path))
                    loaded.append(skill)
                except Exception as e:
                    print(f"Failed to load skill {file_path}: {e}")

        return loaded

    def get_instructions(self) -> List[str]:
        instructions = []
        for skill in self._skills.values():
            if skill.instructions:
                instructions.append(f"## {skill.name}\n\n{skill.instructions}")
        return instructions

    def clear(self) -> None:
        self._skills.clear()
