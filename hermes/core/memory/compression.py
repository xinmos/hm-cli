import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from hermes.core.memory.models import CompressionStrategy, Episode, WorkingMemory


@dataclass
class CompressionResult:
    strategy: CompressionStrategy
    success: bool
    items_affected: int
    bytes_saved: int = 0
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "success": self.success,
            "items_affected": self.items_affected,
            "bytes_saved": self.bytes_saved,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class CompressionEngine:
    def __init__(self, db_path: Path, working_memory: WorkingMemory) -> None:
        self._db_path = db_path
        self._wm = working_memory

    async def compress(self, strategy: CompressionStrategy) -> CompressionResult:
        if strategy == CompressionStrategy.FLUSH:
            return await self._flush()
        elif strategy == CompressionStrategy.PRUNE:
            return await self._prune()
        elif strategy == CompressionStrategy.SUMMARIZE:
            return await self._summarize()
        elif strategy == CompressionStrategy.SEGMENT:
            return await self._segment()
        else:
            return CompressionResult(
                strategy=strategy,
                success=False,
                items_affected=0,
                details={"error": "Unknown strategy"},
            )

    async def _flush(self) -> CompressionResult:
        """冲刷：创建检查点"""
        checkpoint_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now()

        snapshot = {
            "checkpoint_id": checkpoint_id,
            "timestamp": timestamp.isoformat(),
            "working_memory": self._wm.to_dict(),
        }

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    data TEXT NOT NULL
                )
            """
            )
            conn.execute(
                "INSERT INTO checkpoints VALUES (?, ?, ?)",
                (checkpoint_id, timestamp.isoformat(), json.dumps(snapshot)),
            )

        return CompressionResult(
            strategy=CompressionStrategy.FLUSH,
            success=True,
            items_affected=1,
            details={
                "checkpoint_id": checkpoint_id,
                "timestamp": timestamp.isoformat(),
            },
        )

    async def _prune(self) -> CompressionResult:
        """裁剪：移除低权重内容"""
        initial_count = len(self._wm.messages)

        if initial_count <= 10:
            return CompressionResult(
                strategy=CompressionStrategy.PRUNE,
                success=True,
                items_affected=0,
                details={"reason": "Message count below threshold"},
            )

        system_msgs = [m for m in self._wm.messages if m.role == "system"]
        other_msgs = [m for m in self._wm.messages if m.role != "system"]

        keep_count = min(20, len(other_msgs))
        kept_msgs = other_msgs[-keep_count:]

        # 保留高注意力权重的消息
        for msg in other_msgs[:-keep_count]:
            # 检查是否与高注意力关键词相关
            for key, weight in self._wm.attention_weights.items():
                if weight > 0.7 and key.lower() in msg.content.lower():
                    if msg not in kept_msgs:
                        kept_msgs.append(msg)
                    break

        self._wm.messages = system_msgs + kept_msgs
        removed = initial_count - len(self._wm.messages)

        # 同时清理工具执行链
        initial_tool_count = len(self._wm.tool_chain)
        # 保留最近的10个工具执行
        if len(self._wm.tool_chain) > 10:
            self._wm.tool_chain = self._wm.tool_chain[-10:]
        tools_removed = initial_tool_count - len(self._wm.tool_chain)

        return CompressionResult(
            strategy=CompressionStrategy.PRUNE,
            success=True,
            items_affected=removed + tools_removed,
            details={
                "messages_removed": removed,
                "tools_removed": tools_removed,
                "messages_remaining": len(self._wm.messages),
            },
        )

    async def _summarize(self) -> CompressionResult:
        """摘要：为旧情景生成摘要"""
        cutoff = datetime.now() - timedelta(days=30)

        # 获取旧的情景记录
        old_episodes = self._episodic.query_by_time(
            datetime.min.replace(year=2000), cutoff
        )

        if not old_episodes:
            return CompressionResult(
                strategy=CompressionStrategy.SUMMARIZE,
                success=True,
                items_affected=0,
                details={"reason": "No old episodes to summarize"},
            )

        # 按类型分组
        episodes_by_type: dict[str, list[Episode]] = {}
        for ep in old_episodes:
            key = ep.event_type.value
            if key not in episodes_by_type:
                episodes_by_type[key] = []
            episodes_by_type[key].append(ep)

        # 创建摘要记录（简化实现）
        summaries_created = 0
        for event_type, episodes in episodes_by_type.items():
            if len(episodes) >= 5:
                # 创建摘要episode
                summary_ep = Episode(
                    id=str(uuid.uuid4()),
                    timestamp=episodes[-1].timestamp,  # 使用最新的时间
                    event_type=episodes[0].event_type,
                    session_id="summary",
                    summary=f"[{event_type}] {len(episodes)} 个相关事件的摘要",
                    raw_data={
                        "summarized_count": len(episodes),
                        "event_type": event_type,
                        "date_range": [
                            episodes[0].timestamp.isoformat(),
                            episodes[-1].timestamp.isoformat(),
                        ],
                    },
                    entities=[],
                    importance=min(8, max(ep.importance for ep in episodes)),
                    retention_score=1.0,
                    tags=["summary", "compressed"],
                )

                # 添加摘要episode
                self._episodic.append(summary_ep)
                summaries_created += 1

        return CompressionResult(
            strategy=CompressionStrategy.SUMMARIZE,
            success=True,
            items_affected=summaries_created,
            details={
                "summaries_created": summaries_created,
                "episodes_processed": len(old_episodes),
                "date_cutoff": cutoff.isoformat(),
            },
        )

    async def _segment(self) -> CompressionResult:
        """分段：会话分段"""
        segment_id = str(uuid.uuid4())[:8]

        # 保存当前段的信息
        segment_info = {
            "segment_id": segment_id,
            "message_count": len(self._wm.messages),
            "goal_count": len(self._wm.active_goals),
            "start_time": self._wm.session_start.isoformat(),
            "end_time": datetime.now().isoformat(),
        }

        # 重置工作记忆但保留系统消息
        system_msgs = [m for m in self._wm.messages if m.role == "system"]

        # 创建新的工作记忆
        self._wm.messages = system_msgs
        self._wm.active_goals.clear()
        self._wm.tool_chain.clear()
        self._wm.temp_vars.clear()
        self._wm.attention_weights.clear()
        self._wm.session_start = datetime.now()
        self._wm.session_id = str(uuid.uuid4())

        return CompressionResult(
            strategy=CompressionStrategy.SEGMENT,
            success=True,
            items_affected=1,
            details={
                "segment_id": segment_id,
                "segment_info": segment_info,
                "new_session_id": self._wm.session_id,
            },
        )
