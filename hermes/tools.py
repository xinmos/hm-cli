from langchain_core.tools import tool

@tool
def run_python(code: str) -> str:
    """执行 Python 代码并返回结果。代码中必须将最终结果存入变量 `result`。"""
    try:
        exec_globals = {}
        exec(code, exec_globals)
        return str(exec_globals.get('result', '代码执行成功，但未定义 result 变量'))
    except Exception as e:
        return f"执行错误: {e}"

TOOLS = [run_python]