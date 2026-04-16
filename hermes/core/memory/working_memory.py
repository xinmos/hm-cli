import uuid
from datetime import datetime
from typing import Any

from hermes.core.memory.models import Goal, GoalStatus, Message, ToolExecution, WorkingMemory


class WorkingMemoryManager:
    """工作记忆管理器"""

    def __init__(self, working_memory: WorkingMemory | None = None) -> None:
        self._wm = working_memory or WorkingMemory()

    @property
    def working_memory(self) -> WorkingMemory:
        return self._wm

    def update_attention(self, key: str, weight: float) -> None:
        self._wm.update_attention(key, max(0.0, min(1.0, weight)))

    def get_context_window(self, max_tokens: int = 4000) -> list[Message]:
        """获取适合上下文窗口的消息列表

        简单实现：基于消息数量估算
        更精细的实现应该基于tokenizer计算实际token数
        """
        if not self._wm.messages:
            return []

        # 估算每个消息平均100个token
        avg_tokens_per_msg = 100
        max_messages = max(1, max_tokens // avg_tokens_per_msg)

        return self._wm.get_context_window(max_messages)

    def add_goal(self, description: str, priority: int = 5, parent_id: str | None = None) -> str:
        return self._wm.add_goal(description, priority, parent_id)

    def complete_goal(self, goal_id: str) -> bool:
        return self._wm.complete_goal(goal_id)

    def fail_goal(self, goal_id: str) -> bool:
        for goal in self._wm.active_goals:
            if goal.id == goal_id and goal.is_active():
                goal.fail()
                self._wm.touch()
                return True
        return False

    def get_active_goals(self) -> list[Goal]:
        return self._wm.get_active_goals()

    def get_goal_by_id(self, goal_id: str) -> Goal | None:
        for goal in self._wm.active_goals:
            if goal.id == goal_id:
                return goal
        return None

    def start_tool_execution(self, tool_name: str, arguments: dict[str, Any]) -> ToolExecution:
        return self._wm.start_tool_execution(tool_name, arguments)

    def add_message(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        self._wm.add_message(role, content, metadata)

    def get_recent_messages(self, count: int = 10) -> list[Message]:
        if not self._wm.messages:
            return []
        return self._wm.messages[-count:]

    def clear_messages(self) -> None:
        system_msgs = [m for m in self._wm.messages if m.role == "system"]
        self._wm.messages = system_msgs
        self._wm.touch()

    def clear_tool_chain(self) -> None:
        self._wm.clear_tool_chain()

    def reset_goals(self) -> None:
        for goal in self._wm.active_goals:
            if goal.is_active():
                goal.status = GoalStatus.CANCELLED
                goal.completed_at = datetime.now()
        self._wm.touch()

    def get_stats(self) -> dict[str, Any]:
        active_goals = len(self._wm.get_active_goals())
        total_goals = len(self._wm.active_goals)
        message_count = len(self._wm.messages)
        tool_count = len(self._wm.tool_chain)

        session_duration = datetime.now() - self._wm.session_start
        return {
            "session_id": self._wm.session_id,
            "active_goals": active_goals,
            "total_goals": total_goals,
            "message_count": message_count,
            "tool_execution_count": tool_count,
            "session_duration_seconds": session_duration.total_seconds(),
            "attention_keys": len(self._wm.attention_weights),
        }

    def export_state(self) -> dict[str, Any]:
        return self._wm.to_dict()

    def import_state(self, data: dict[str, Any]) -> None:
        self._wm = WorkingMemory.from_dict(data)
