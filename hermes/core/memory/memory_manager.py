from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from hermes.core.memory.episode_store import EpisodeStore
from hermes.core.memory.models import (
    EntityRef,
    Episode,
    EventType,
    MemoryConfig,
    ToolExecution,
)


class MemoryManager:
    """记忆管理器 - 情景记录与检索"""

    def __init__(
        self,
        episodes_path: Path,
        config: MemoryConfig | None = None,
    ) -> None:
        self._config = config or MemoryConfig(episodes_path=str(episodes_path))
        self._store = EpisodeStore(Path(self._config.episodes_path))

    def record_interaction(
        self,
        session_id: str,
        user_input: str,
        agent_response: str,
        tool_executions: list[ToolExecution] | None = None,
    ) -> Episode | None:
        """记录一次交互，返回存储的 Episode 或 None"""
        tools = tool_executions or []

        episode = Episode(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            event_type=EventType.USER_MESSAGE,
            session_id=session_id,
            summary=self._generate_summary(user_input),
            raw_data={
                "user_input": user_input,
                "agent_response": agent_response,
                "tool_executions": [t.to_dict() for t in tools],
            },
            entities=self._extract_entities(user_input, agent_response),
            importance=self._calculate_importance(user_input, agent_response, tools),
            retention_score=1.0,
            tags=self._extract_tags(user_input),
        )

        if episode.importance >= self._config.importance_threshold:
            self._store.append(episode)
            return episode
        return None

    def retrieve_context(
        self,
        query: str,
        max_episodes: int = 5,
        recent_days: int = 30,
    ) -> str:
        """检索相关上下文，返回格式化文本"""
        episodes = self._store.query_by_time(
            datetime.now() - timedelta(days=recent_days),
            datetime.now(),
        )

        keywords = self._extract_keywords(query)
        if not keywords:
            return ""

        matched: list[Episode] = []
        for ep in episodes:
            summary_lower = ep.summary.lower()
            for kw in keywords:
                if kw in summary_lower:
                    matched.append(ep)
                    break

        if not matched:
            return ""

        parts: list[str] = ["## 相关历史记录"]
        for ep in matched[:max_episodes]:
            parts.append(f"- [{ep.timestamp.strftime('%Y-%m-%d')}] {ep.summary}")

        return "\n".join(parts)

    def get_stats(self) -> dict[str, Any]:
        return self._store.get_stats()

    def _generate_summary(self, user_input: str) -> str:
        if len(user_input) <= 100:
            return user_input
        return user_input[:100] + "..."

    def _extract_entities(self, user_input: str, agent_response: str) -> list[EntityRef]:
        entities: list[EntityRef] = []
        file_pattern = r"[\w\-/\\]+\.(py|js|ts|md|json|yaml|yml|txt)"
        for match in re.finditer(file_pattern, user_input + " " + agent_response):
            entities.append(
                EntityRef(
                    entity_type="file",
                    entity_id=match.group(0),
                    name=match.group(0).split("/")[-1],
                )
            )
        return entities

    def _calculate_importance(
        self,
        user_input: str,
        agent_response: str,
        tool_executions: list[ToolExecution],
    ) -> int:
        importance = 5

        important_keywords = ["重要", "关键", "必须", "记住", "保存", "配置"]
        if any(kw in user_input for kw in important_keywords):
            importance += 2

        if tool_executions:
            importance += 1
            if any(t.error for t in tool_executions):
                importance += 1

        return max(1, min(10, importance))

    def _extract_tags(self, user_input: str) -> list[str]:
        tags: list[str] = []
        if any(kw in user_input for kw in ["代码", "编程", "函数", "类"]):
            tags.append("coding")
        if any(kw in user_input for kw in ["错误", "问题", "bug", "失败"]):
            tags.append("error")
        if any(kw in user_input for kw in ["配置", "设置", "参数"]):
            tags.append("config")
        return tags

    def _extract_keywords(self, query: str) -> list[str]:
        stop_words = {"我", "你", "是", "的", "了", "在", "有", "什么", "怎么", "如何", "吗", "呢", "请", "问"}
        query_lower = query.lower()
        keywords = [w for w in query_lower.split() if w not in stop_words and len(w) >= 2]
        if not keywords:
            keywords = re.findall(r"[一-龥]{2,}", query_lower)
        return keywords
