import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

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

    def load_from_file(self, path: str, lazy: bool = True) -> Skill:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Skill file not found: {path}")

        if lazy:
            skill = self._parse_skill_metadata(path)
        else:
            content = path.read_text(encoding="utf-8")
            skill = self._parse_skill(content, path)
        self.register(skill)
        return skill

    def _parse_skill_metadata(self, path: Path) -> Skill:
        content = path.read_text(encoding="utf-8")
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)

        if frontmatter_match:
            meta = yaml.safe_load(frontmatter_match.group(1)) or {}
        else:
            meta = {}

        name = meta.get("name", path.stem)
        description = meta.get("description", "")
        version = meta.get("version", "1.0.0")
        slash_command = meta.get("slash_command", "")
        metadata = {k: v for k, v in meta.items() if k not in ["name", "description", "version", "slash_command"]}

        return Skill(
            name=name,
            description=description,
            version=version,
            instructions="",
            slash_command=slash_command or f"/{name}",
            metadata=metadata,
            file_path=path,
        )

    def _parse_skill(self, content: str, path: Path) -> Skill:
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)

        if frontmatter_match:
            meta = yaml.safe_load(frontmatter_match.group(1)) or {}
            instructions = frontmatter_match.group(2).strip()
        else:
            meta = {}
            instructions = content.strip()

        name = meta.get("name", path.stem)
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
            file_path=path,
        )

    def load_skill_instructions(self, name: str) -> str | None:
        skill = self._skills.get(name)
        if not skill or not skill.file_path:
            return None
        if skill.instructions:
            return skill.instructions

        try:
            content = skill.file_path.read_text(encoding="utf-8")
            frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
            if frontmatter_match:
                skill.instructions = frontmatter_match.group(2).strip()
            else:
                skill.instructions = content.strip()
            return skill.instructions
        except Exception:
            return None

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
