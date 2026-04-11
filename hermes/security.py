import os
import re
from enum import Enum
from pathlib import Path

from hermes.config import Config

WORKDIR = Config.WORKDIR


class SecurityError(Exception):
    pass


class CommandSafety(Enum):
    """命令安全级别"""
    REJECTED = "rejected"
    NEEDS_CONFIRMATION = "needs_confirmation"
    APPROVED = "approved"


def safe_path(p: str) -> Path:
    """
    路径沙箱 - 确保所有文件操作都在 WORKDIR 内
    
    Args:
        p: 文件路径（相对或绝对）
        
    Returns:
        解析后的绝对路径
        
    Raises:
        SecurityError: 路径逃出工作目录
    """
    expanded = os.path.expanduser(p)
    
    if os.path.isabs(expanded):
        path = Path(expanded).resolve()
    else:
        path = (WORKDIR / expanded).resolve()
    
    if Config.STRICT_SANDBOX:
        try:
            path.relative_to(WORKDIR)
        except ValueError:
            raise SecurityError(f"路径逃出工作目录: {p} (WORKDIR: {WORKDIR})")
    
    return path


def truncate_output(text: str) -> str:
    """
    统一输出截断
    
    Args:
        text: 原始输出文本
        
    Returns:
        截断后的文本
    """
    if not text:
        return "(no output)"
    
    lines = text.splitlines()
    
    if len(lines) > Config.MAX_OUTPUT_LINES:
        lines = lines[:Config.MAX_OUTPUT_LINES]
        lines.append(f"... ({len(text.splitlines()) - Config.MAX_OUTPUT_LINES} more lines)")
    
    result = "\n".join(lines)
    
    if len(result) > Config.MAX_OUTPUT_SIZE:
        result = result[:Config.MAX_OUTPUT_SIZE] + f"\n... ({len(text) - Config.MAX_OUTPUT_SIZE} more chars)"
    
    return result


# 高危命令模式（必须拦截）
DANGEROUS_PATTERNS = [
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

# 需要二次确认的危险命令模式
CONFIRMATION_PATTERNS = [
    r"rm\s+-[rf]",
    r"rm\s+.*\b-r\b",
    r"\brm\b(?!\s+-[rf])",  # rm 命令但不含 -r 或 -f
    r"\brmdir\b",
    r"\bmv\b.*\s+\S+\s+/dev/null",
    r"\bmv\b.*\s+\S+\s+\S*\.bak",
    r">\s*\S+",  # 重定向覆盖文件
    r">>\s*\S+",  # 重定向追加（虽然安全但记录）
]

# 自动批准的命令（无需确认）
AUTO_APPROVED_COMMANDS = [
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


def check_command_safety(cmd: str) -> tuple[CommandSafety, str]:
    """
    检查命令安全性
    
    Args:
        cmd: 命令字符串
        
    Returns:
        (安全级别, 原因/提示信息)
    """
    if not cmd or not cmd.strip():
        return CommandSafety.REJECTED, "命令为空"
    
    # 首先检查高危命令（直接拒绝）
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return CommandSafety.REJECTED, f"高危命令，已阻止: {pattern}"
    
    # 检查需要二次确认的命令
    for pattern in CONFIRMATION_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return CommandSafety.NEEDS_CONFIRMATION, f"此操作可能危险，请确认是否执行: {cmd}"
    
    # 检查自动批准的命令
    for pattern in AUTO_APPROVED_COMMANDS:
        if re.search(pattern, cmd):
            return CommandSafety.APPROVED, "auto-approved"
    
    return CommandSafety.APPROVED, "approved"
