"""危险操作确认机制 - 全局回调注册"""
from typing import Callable, Optional

# 全局确认回调函数
_confirm_callback: Optional[Callable[[str, str], bool]] = None


def set_confirm_callback(callback: Optional[Callable[[str, str], bool]]) -> None:
    """注册危险操作确认回调

    Args:
        callback: 接收 (tool_name, description) 返回 bool 的函数
                 True = 确认执行, False = 取消
    """
    global _confirm_callback
    _confirm_callback = callback


def ask_confirm(tool_name: str, description: str) -> bool:
    """询问用户是否执行危险操作

    Args:
        tool_name: 工具名称
        description: 操作描述（如命令内容）

    Returns:
        True - 用户确认执行
        False - 用户取消或未设置回调（默认拒绝）
    """
    if _confirm_callback is None:
        return False
    return _confirm_callback(tool_name, description)
