from __future__ import annotations

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
        self._security = SecurityManager(settings.workdir, settings.strict_sandbox)
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
        safety_level = self._security.check_command_safety(command)

        if safety_level == CommandSafety.REJECTED:
            return f"Command not allowed (high risk): {command}"

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
        def load_skill(skill_name: str) -> str:
            """Load a skill by name to get its full instructions."""
            skill = self._skill_repo.get(skill_name)
            if skill:
                return skill.instructions
            return f"Skill not found: {skill_name}"

        self._tools = [bash, read, write, edit, load_skill]
