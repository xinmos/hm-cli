from langchain_core.tools import tool

from hermes.skills import Skill


@tool
def hello(name: str = "World") -> str:
    """Say hello to someone"""
    return f"Hello, {name}!"


@tool
def calculate(expression: str) -> str:
    """Calculate a mathematical expression safely"""
    try:
        allowed_names = {
            "abs": abs, "round": round, "max": max, "min": min,
            "sum": sum, "pow": pow, "len": len,
        }
        code = compile(expression, "<string>", "eval")
        for name in code.co_names:
            if name not in allowed_names:
                return f"Error: '{name}' not allowed"
        result = eval(code, {"__builtins__": {}}, allowed_names)
        return str(result)
    except Exception as e:
        return f"Error: {e}"


SKILL = Skill(
    name="example",
    description="Example skill with greeting and calculator tools",
    version="1.0.0",
    tools=[hello, calculate],
    system_prompt="You have access to greeting and calculator tools. Use them when appropriate.",
    triggers=["hello", "calculate", "math"],
)
