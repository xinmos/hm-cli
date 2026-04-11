import subprocess

from langchain_core.tools import tool

from hermes.config import Config
from hermes.security import check_command_safety, CommandSafety, truncate_output
from hermes.tools.confirm import ask_confirm


@tool
def bash(command: str, timeout: int = None) -> str:
    """
    Run a shell command (ls, cat, grep, find, etc).

    Args:
        command: Shell command to execute
        timeout: Timeout in seconds (default: 120)
    
    Returns:
        Command output or error message
    """
    safety, reason = check_command_safety(command)
    if safety == CommandSafety.REJECTED:
        return f"Error: {reason}"
    if safety == CommandSafety.NEEDS_CONFIRMATION:
        confirmed = ask_confirm("bash", command)
        if not confirmed:
            return "Operation cancelled by user"
    
    timeout = timeout or Config.COMMAND_TIMEOUT
    
    try:
        r = subprocess.run(
            command,
            shell=True,
            cwd=Config.WORKDIR,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        output = (r.stdout + r.stderr).strip()
        return truncate_output(output)
        
    except subprocess.TimeoutExpired:
        return f"Error: Timeout ({timeout}s)"
    except Exception as e:
        return f"Error: {e}"
