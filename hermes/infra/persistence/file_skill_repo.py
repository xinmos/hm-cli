import re
from pathlib import Path

import yaml

from hermes.app.ports import SkillInfo


class FileSkillRepository:
    def __init__(self, workdir: Path):
        self._workdir = workdir
        self._skills: dict[str, SkillInfo] = {}
        self._slash_commands: dict[str, str] = {}
        self._active_skill: SkillInfo | None = None
        self._load_default_skills()

    def get(self, name: str) -> SkillInfo | None:
        return self._skills.get(name)

    def get_by_slash_command(self, cmd: str) -> SkillInfo | None:
        name = self._slash_commands.get(cmd)
        if name:
            return self._skills.get(name)
        return self._skills.get(cmd.lstrip("/"))

    def list_skills(self) -> list[SkillInfo]:
        return list(self._skills.values())

    def is_slash_command(self, cmd: str) -> bool:
        if cmd in self._slash_commands:
            return True
        return cmd.lstrip("/") in self._skills

    def _load_default_skills(self) -> None:
        builtin_dirs = [
            self._workdir / ".hermes" / "skills",
            Path(__file__).parent.parent.parent / "skills",
        ]
        for skills_dir in builtin_dirs:
            if skills_dir.exists():
                self._load_from_directory(skills_dir)

        user_skills_dir = self._workdir / "skills"
        if user_skills_dir.exists():
            self._load_from_directory(user_skills_dir)

    def _load_from_directory(self, directory: Path) -> None:
        for file_path in directory.glob("*.md"):
            if file_path.name.startswith("_"):
                continue
            try:
                skill = self._parse_skill_file(file_path)
                self._register(skill)
            except Exception as e:
                print(f"Failed to load skill {file_path}: {e}")

        for subdir in directory.iterdir():
            if subdir.is_dir():
                skill_md = subdir / "SKILL.md"
                if skill_md.exists():
                    try:
                        skill = self._parse_skill_file(skill_md)
                        self._register(skill)
                    except Exception as e:
                        print(f"Failed to load skill {skill_md}: {e}")

    def _parse_skill_file(self, path: Path) -> SkillInfo:
        content = path.read_text(encoding="utf-8")
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
        slash_command = meta.get("slash_command", f"/{name}")
        metadata = {k: v for k, v in meta.items() if k not in ["name", "description", "version", "slash_command"]}

        return SkillInfo(
            name=name,
            description=description,
            version=version,
            slash_command=slash_command,
            instructions=instructions,
            metadata=metadata,
        )

    def _register(self, skill: SkillInfo) -> None:
        self._skills[skill.name] = skill
        self._slash_commands[skill.slash_command] = skill.name

    def get_active_skill(self) -> SkillInfo | None:
        """Get the currently active skill."""
        return self._active_skill

    def set_active_skill(self, skill_name: str | None) -> bool:
        """Set the active skill by name.

        Args:
            skill_name: Name of the skill to activate, or None to clear

        Returns:
            True if successful, False if skill not found
        """
        if skill_name is None:
            self._active_skill = None
            return True

        skill = self._skills.get(skill_name)
        if skill:
            self._active_skill = skill
            return True
        return False
