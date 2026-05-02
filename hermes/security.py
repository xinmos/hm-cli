import os
import re
from enum import Enum
from pathlib import Path


class SecurityError(Exception):
    pass


class CommandSafety(Enum):
    REJECTED = "rejected"
    NEEDS_CONFIRMATION = "needs_confirmation"
    APPROVED = "approved"


class SecurityManager:
    def __init__(
        self,
        workdir: Path,
        strict_sandbox: bool = True,
        allowed_roots: list[Path] | None = None,
    ):
        self._workdir = workdir.resolve()
        self._strict_sandbox = strict_sandbox
        roots = [self._workdir]
        if allowed_roots:
            roots.extend(root.resolve() for root in allowed_roots)
        self._allowed_roots = roots

    def safe_path(self, p: str) -> Path:
        expanded = os.path.expanduser(p)

        if os.path.isabs(expanded):
            path = Path(expanded).resolve()
        else:
            path = (self._workdir / expanded).resolve()

        if self._strict_sandbox:
            if not self._is_within_allowed_roots(path):
                raise SecurityError(f"路径逃出工作目录: {p} (WORKDIR: {self._workdir})")

        return path

    def is_path_allowed(self, path: Path) -> bool:
        if not self._strict_sandbox:
            return True
        return self._is_within_allowed_roots(path)

    def _is_within_allowed_roots(self, path: Path) -> bool:
        resolved = path.resolve()
        for root in self._allowed_roots:
            try:
                resolved.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def is_command_allowed(self, cmd: str) -> bool:
        if not cmd or not cmd.strip():
            return False

        for pattern in self._dangerous_patterns:
            if re.search(pattern, cmd, re.IGNORECASE):
                return False
        return True

    @staticmethod
    def check_command_safety(cmd: str) -> tuple[CommandSafety, str]:
        if not cmd or not cmd.strip():
            return CommandSafety.REJECTED, "命令为空"

        for pattern in SecurityManager._dangerous_patterns:
            if re.search(pattern, cmd, re.IGNORECASE):
                return CommandSafety.REJECTED, f"高危命令，已阻止: {pattern}"

        for pattern in SecurityManager._confirmation_patterns:
            if re.search(pattern, cmd, re.IGNORECASE):
                return CommandSafety.NEEDS_CONFIRMATION, f"此操作可能危险，请确认是否执行: {cmd}"

        for pattern in SecurityManager._auto_approved_commands:
            if re.search(pattern, cmd):
                return CommandSafety.APPROVED, "auto-approved"

        return CommandSafety.APPROVED, "approved"

    _dangerous_patterns = [
        r"rm\s+-rf\s+/",
        r"rm\s+-rf\s+~",
        r"rm\s+.*\*\s+-rf",
        r"sudo\b",
        r"su\b",
        r"shutdown\b",
        r"reboot\b",
        r"poweroff\b",
        r"halt\b",
        r">\s*/dev/[sh]da",
        r"curl.*\|.*bash",
        r"curl.*\|.*sh",
        r"wget.*\|.*bash",
        r"wget.*\|.*sh",
        r"mkfs\b",
        r"fdisk\b",
        r"dd\b",
        r"format\b",
    ]

    _confirmation_patterns = [
        r"rm\s+-[rf]",
        r"rm\s+.*\b-r\b",
        r"\brm\b(?!\s+-[rf])",
        r"\brmdir\b",
        r"\bmv\b.*\s+\S+\s+/dev/null",
        r"\bmv\b.*\s+\S+\s+\S*\.bak",
        r">\s*\S+",
        r">>\s*\S+",
    ]

    _auto_approved_commands = [
        r"^ls\b",
        r"^cat\b",
        r"^grep\b",
        r"^find\b",
        r"^head\b",
        r"^tail\b",
        r"^wc\b",
        r"^pwd\b",
        r"^echo\b",
        r"^cd\s+",
        r"^test\s+",
        r"^\[\s+-",
        r"^rg\b",
        r"^sort\b",
        r"^uniq\b",
    ]
