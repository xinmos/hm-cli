from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

from langchain_core.tools import tool as langchain_tool

from hermes.app.ports import InteractionPort, SkillRepository
from hermes.app.settings import Settings
from hermes.core.skill_permissions import SkillToolPermissionChecker
from hermes.security import CommandSafety, SecurityManager


class LangChainToolCatalog:
    def __init__(
        self,
        settings: Settings,
        skill_repository: SkillRepository,
        interaction_port: InteractionPort | None = None,
    ):
        self._settings = settings
        self._skill_repo = skill_repository
        self._interaction_port = interaction_port
        self._security = SecurityManager(
            settings.workdir,
            settings.strict_sandbox,
            allowed_roots=[settings.llm_wiki_path],
        )
        self._tools: list[Any] = []
        self._build_tools()

    def get_tools(self) -> list[Any]:
        return self._tools

    def get_tool(self, name: str) -> Any | None:
        for tool in self._tools:
            if getattr(tool, "name", None) == name:
                return tool
        return None

    def _check_command_safety(self, command: str) -> str | None:
        safety_level, message = self._security.check_command_safety(command)

        if safety_level == CommandSafety.REJECTED:
            return message

        if safety_level == CommandSafety.NEEDS_CONFIRMATION:
            if self._interaction_port:
                display = f"Bash({command[:40]}...)" if len(command) > 40 else f"Bash({command})"
                if not self._interaction_port.confirm("bash", command, display):
                    return "Command rejected by user"
            else:
                return "Command requires confirmation but no interaction port available"

        return None

    def _show_tool(self, display: str) -> None:
        if self._interaction_port:
            self._interaction_port.notify_tool_start("", display)

    def _execute_bash(self, command: str) -> str:
        import subprocess

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self._settings.command_timeout,
                cwd=self._settings.workdir,
            )
            output = result.stdout + result.stderr
            lines = output.splitlines()
            if len(lines) > self._settings.max_output_lines:
                output = "\n".join(lines[: self._settings.max_output_lines]) + "\n... (truncated)"
            if len(output) > self._settings.max_output_size:
                output = output[: self._settings.max_output_size] + "\n... (truncated)"
            return output
        except subprocess.TimeoutExpired:
            return f"Command timed out after {self._settings.command_timeout} seconds"
        except Exception as e:
            return f"Error: {e}"

    def _init_llm_wiki(self) -> str:
        wiki_root = self._settings.llm_wiki_path
        templates_dir = Path(__file__).parent.parent.parent / "skills" / "llm-wiki" / "templates"

        if not self._security.is_path_allowed(wiki_root):
            return f"Access denied: {wiki_root}"
        if not templates_dir.exists():
            return f"Template directory not found: {templates_dir}"

        if self._interaction_port:
            if not self._interaction_port.confirm(
                "init_llm_wiki",
                f"Initialize llm-wiki at {wiki_root}",
                f"InitLLMWiki({wiki_root})",
            ):
                return "Initialization rejected by user"

        directories = [
            ".obsidian",
            "raw/assets",
            "raw/sources",
            "schema",
            "wiki/comparisons",
            "wiki/concepts",
            "wiki/entities",
            "wiki/queries",
            "wiki/sources",
            "wiki/synthesis",
        ]

        created_dirs: list[str] = []
        for relative_dir in directories:
            target_dir = wiki_root / relative_dir
            if not target_dir.exists():
                target_dir.mkdir(parents=True, exist_ok=True)
                created_dirs.append(relative_dir)

        created_files: list[str] = []
        skipped_files: list[str] = []
        for template_path in sorted(templates_dir.rglob("*")):
            if not template_path.is_file():
                continue
            relative_path = template_path.relative_to(templates_dir)
            target_path = wiki_root / relative_path
            if target_path.exists():
                skipped_files.append(str(relative_path))
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(template_path, target_path)
            created_files.append(str(relative_path))

        lines = [f"llm-wiki initialized at: {wiki_root}"]
        if created_dirs:
            lines.append("Created directories:")
            lines.extend(f"- {path}" for path in created_dirs)
        if created_files:
            lines.append("Created files:")
            lines.extend(f"- {path}" for path in created_files)
        if skipped_files:
            lines.append("Skipped existing files:")
            lines.extend(f"- {path}" for path in skipped_files)
        if not created_dirs and not created_files:
            lines.append("No changes needed; workspace already had the expected structure.")
        return "\n".join(lines)

    def _build_tools(self) -> None:
        @langchain_tool
        def bash(command: str) -> str:
            """Execute a bash command safely."""
            display = f"Bash({command[:40]}...)" if len(command) > 40 else f"Bash({command})"

            active_skill = self._skill_repo.get_active_skill() if hasattr(self._skill_repo, 'get_active_skill') else None
            if active_skill:
                checker = SkillToolPermissionChecker(active_skill)
                if checker.is_allowed("Bash", command):
                    self._show_tool(display)
                else:
                    error = self._check_command_safety(command)
                    if error:
                        return error
                    self._show_tool(display)
            else:
                error = self._check_command_safety(command)
                if error:
                    return error
                self._show_tool(display)

            return self._execute_bash(command)

        @langchain_tool
        def read(file_path: str) -> str:
            """Read contents of a file."""
            filename = file_path.split("/")[-1]
            self._show_tool(f"Read({filename})")

            path = self._settings.workdir / file_path
            if not self._security.is_path_allowed(path):
                return f"Access denied: {file_path}"
            try:
                return path.read_text(encoding="utf-8")
            except Exception as e:
                return f"Error reading file: {e}"

        @langchain_tool
        def write(file_path: str, content: str) -> str:
            """Write content to a file."""
            filename = file_path.split("/")[-1]
            display = f"Write({filename})"

            if self._interaction_port:
                preview = f"{content[:100]}..." if len(content) > 100 else content
                if not self._interaction_port.confirm("write", preview, display):
                    return "Write operation rejected by user"
            else:
                return "Write operation requires confirmation but no interaction port available"

            path = self._settings.workdir / file_path
            if not self._security.is_path_allowed(path):
                return f"Access denied: {file_path}"
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                return f"Successfully wrote to {file_path}"
            except Exception as e:
                return f"Error writing file: {e}"

        @langchain_tool
        def edit(file_path: str, old_string: str, new_string: str) -> str:
            """Edit a file by replacing old_string with new_string."""
            filename = file_path.split("/")[-1]
            display = f"Edit({filename})"

            if self._interaction_port:
                preview = f"replace: {old_string[:50]}..." if len(old_string) > 50 else f"replace: {old_string}"
                if not self._interaction_port.confirm("edit", preview, display):
                    return "Edit operation rejected by user"
            else:
                return "Edit operation requires confirmation but no interaction port available"

            path = self._settings.workdir / file_path
            if not self._security.is_path_allowed(path):
                return f"Access denied: {file_path}"
            try:
                content = path.read_text(encoding="utf-8")
                if old_string not in content:
                    return f"String not found in {file_path}"
                content = content.replace(old_string, new_string, 1)
                path.write_text(content, encoding="utf-8")
                return f"Successfully edited {file_path}"
            except Exception as e:
                return f"Error editing file: {e}"

        @langchain_tool
        def init_llm_wiki() -> str:
            """Initialize the configured llm-wiki workspace from bundled templates without overwriting files."""
            self._show_tool(f"InitLLMWiki({self._settings.llm_wiki_path})")
            return self._init_llm_wiki()

        @langchain_tool
        def load_skill(skill_name: str) -> str:
            """Load a skill by name to get its full instructions."""
            skill = self._skill_repo.get(skill_name)
            if skill:
                return skill.instructions
            return f"Skill not found: {skill_name}"

        self._tools = [bash, read, write, edit, init_llm_wiki, load_skill]
