from langchain_core.tools import tool

from hermes.security import safe_path, SecurityError, truncate_output


@tool
def read(path: str, limit: int = None) -> str:
    """
    Read file contents with optional line limit.

    Args:
        path: File path (relative or absolute, must be within WORKDIR)
        limit: Maximum number of lines to read (optional)

    Returns:
        File content or error message
    """
    try:
        fp = safe_path(path)
        text = fp.read_text(encoding='utf-8')

        lines = text.splitlines()
        if limit and len(lines) > limit:
            lines = lines[:limit]
            lines.append(f"... ({len(text.splitlines()) - limit} more lines)")

        return truncate_output("\n".join(lines))

    except SecurityError as e:
        return f"Security Error: {e}"
    except Exception as e:
        return f"Error: {e}"


@tool
def write(path: str, content: str) -> str:
    """
    Write content to file (creates directories if needed).

    Args:
        path: File path (relative or absolute, must be within WORKDIR)
        content: Content to write

    Returns:
        Success message or error
    """
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding='utf-8')
        return f"Wrote {len(content)} bytes to {path}"
    except SecurityError as e:
        return f"Security Error: {e}"
    except Exception as e:
        return f"Error: {e}"


@tool
def edit(path: str, old_text: str, new_text: str) -> str:
    """
    Replace exact text in file (old_text must match exactly).

    Args:
        path: File path (relative or absolute, must be within WORKDIR)
        old_text: Text to replace (must match exactly including whitespace)
        new_text: Replacement text

    Returns:
        Success message or error
    """
    try:
        fp = safe_path(path)
        content = fp.read_text(encoding='utf-8')

        if old_text not in content:
            return "Error: Text not found (must match exactly, including whitespace)"

        new_content = content.replace(old_text, new_text, 1)

        if path.endswith('.py'):
            import ast
            try:
                ast.parse(new_content)
            except SyntaxError as e:
                return f"Syntax Error: {e}"

        fp.write_text(new_content, encoding='utf-8')
        return f"Edited {path}"

    except SecurityError as e:
        return f"Security Error: {e}"
    except Exception as e:
        return f"Error: {e}"
