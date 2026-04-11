import os
import re
from pathlib import Path
from hermes.config import Config

WORKDIR = Config.WORKDIR


class SecurityError(Exception):
    pass


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


# 危险命令模式（必须拦截）
DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"sudo\b",
    r"shutdown\b",
    r"reboot\b",
    r">\s*/dev/",
    r"curl.*\|.*bash",
    r"wget.*\|.*bash",
    r"mkfs\b",
    r"fdisk\b",
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


def check_command_safety(cmd: str) -> tuple[bool, str]:
    """
    检查命令安全性
    
    Args:
        cmd: 命令字符串
        
    Returns:
        (是否安全, 原因)
    """
    if not cmd or not cmd.strip():
        return False, "命令为空"
    
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return False, f"危险命令: {pattern}"
    
    for pattern in AUTO_APPROVED_COMMANDS:
        if re.search(pattern, cmd):
            return True, "auto-approved"
    
    return True, "approved"
