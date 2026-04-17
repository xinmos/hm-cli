import fnmatch
import re
from dataclasses import dataclass

from hermes.app.ports import SkillInfo


@dataclass(frozen=True)
class ToolPermission:
    tool_name: str
    pattern: str | None = None

    @staticmethod
    def parse(permission_str: str) -> "ToolPermission":
        permission_str = permission_str.strip()
        match = re.match(r"(\w+)\((.+)\)", permission_str)
        if match:
            tool_name = match.group(1)
            pattern = match.group(2).strip()
            return ToolPermission(tool_name=tool_name, pattern=pattern)
        return ToolPermission(tool_name=permission_str, pattern=None)

    def matches(self, tool_name: str, command: str | None = None) -> bool:
        if self.tool_name != tool_name:
            return False
        if self.pattern is None:
            return True
        if tool_name == "Bash" and command is not None:
            return self._command_matches_pattern(command)
        return True

    def _command_matches_pattern(self, command: str) -> bool:
        if self.pattern is None:
            return True
        pattern = self.pattern
        if pattern.endswith(":*"):
            prefix = pattern[:-2]
            escaped_prefix = re.escape(prefix)
            regex = rf"^{escaped_prefix}([:\s].*)?$"
            return bool(re.match(regex, command))
        return fnmatch.fnmatch(command, pattern)


class SkillToolPermissionChecker:
    def __init__(self, skill: SkillInfo | None = None):
        self._skill = skill
        self._permissions: list[ToolPermission] = []
        if skill:
            self._parse_permissions()

    def _parse_permissions(self) -> None:
        if not self._skill:
            return
        allowed_tools = self._skill.metadata.get("allowed-tools", "")
        if not allowed_tools:
            return
        for tool_str in allowed_tools.split(","):
            tool_str = tool_str.strip()
            if tool_str:
                try:
                    permission = ToolPermission.parse(tool_str)
                    self._permissions.append(permission)
                except ValueError:
                    pass

    def is_allowed(self, tool_name: str, command: str | None = None) -> bool:
        if not self._skill:
            return False
        for permission in self._permissions:
            if permission.matches(tool_name, command):
                return True
        return False

    @property
    def skill_name(self) -> str | None:
        return self._skill.name if self._skill else None
