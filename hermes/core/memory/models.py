from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Protocol

import orjson


class EventType(enum.Enum):
    """事件类型"""

    USER_MESSAGE = "user_message"
    ASSISTANT_RESPONSE = "assistant_response"
    TOOL_EXECUTION = "tool_execution"
    GOAL_CREATED = "goal_created"
    GOAL_COMPLETED = "goal_completed"
    ERROR_OCCURRED = "error_occurred"
    USER_PREFERENCE = "user_preference"
    SESSION_START = "session_start"
    SESSION_END = "session_end"


class GoalStatus(enum.Enum):
    """目标状态"""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CompressionStrategy(enum.Enum):
    """压缩策略"""

    FLUSH = "flush"
    PRUNE = "prune"
    SUMMARIZE = "summarize"
    SEGMENT = "segment"


@dataclass
class EntityRef:
    """实体引用"""

    entity_type: str
    entity_id: str
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntityRef":
        return cls(
            entity_type=data["entity_type"],
            entity_id=data["entity_id"],
            name=data["name"],
        )


@dataclass
class Episode:
    """情景记忆单元"""

    id: str
    timestamp: datetime
    event_type: EventType
    session_id: str
    summary: str
    raw_data: dict[str, Any]
    entities: list[EntityRef]
    importance: int = 5
    retention_score: float = 1.0
    vector_embedding: list[float] | None = None
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if isinstance(self.event_type, str):
            self.event_type = EventType(self.event_type)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "session_id": self.session_id,
            "summary": self.summary,
            "raw_data": self.raw_data,
            "entities": [e.to_dict() for e in self.entities],
            "importance": self.importance,
            "retention_score": self.retention_score,
            "vector_embedding": self.vector_embedding,
            "tags": self.tags,
        }

    def to_json(self) -> bytes:
        return orjson.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Episode":
        return cls(
            id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            event_type=EventType(data["event_type"]),
            session_id=data["session_id"],
            summary=data["summary"],
            raw_data=data["raw_data"],
            entities=[EntityRef.from_dict(e) for e in data.get("entities", [])],
            importance=data.get("importance", 5),
            retention_score=data.get("retention_score", 1.0),
            vector_embedding=data.get("vector_embedding"),
            tags=data.get("tags", []),
        )


@dataclass
class KnowledgeNode:
    """知识图谱节点"""

    id: str
    entity_type: str
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    source_episodes: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "name": self.name,
            "attributes": self.attributes,
            "confidence": self.confidence,
            "source_episodes": self.source_episodes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeNode":
        return cls(
            id=data["id"],
            entity_type=data["entity_type"],
            name=data["name"],
            attributes=data.get("attributes", {}),
            confidence=data.get("confidence", 0.5),
            source_episodes=data.get("source_episodes", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            version=data.get("version", 1),
        )

    def bump_version(self) -> None:
        self.version += 1
        self.updated_at = datetime.now()


@dataclass
class KnowledgeEdge:
    """知识图谱关系"""

    id: str
    source_id: str
    target_id: str
    relation_type: str
    attributes: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    source_episodes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "attributes": self.attributes,
            "confidence": self.confidence,
            "source_episodes": self.source_episodes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeEdge":
        return cls(
            id=data["id"],
            source_id=data["source_id"],
            target_id=data["target_id"],
            relation_type=data["relation_type"],
            attributes=data.get("attributes", {}),
            confidence=data.get("confidence", 0.5),
            source_episodes=data.get("source_episodes", []),
        )


@dataclass
class Rule:
    """规则定义"""

    id: str
    name: str
    condition: str
    action: str
    priority: int = 5
    enabled: bool = True
    success_count: int = 0
    fail_count: int = 0
    source_episodes: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "condition": self.condition,
            "action": self.action,
            "priority": self.priority,
            "enabled": self.enabled,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "source_episodes": self.source_episodes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Rule":
        return cls(
            id=data["id"],
            name=data["name"],
            condition=data["condition"],
            action=data["action"],
            priority=data.get("priority", 5),
            enabled=data.get("enabled", True),
            success_count=data.get("success_count", 0),
            fail_count=data.get("fail_count", 0),
            source_episodes=data.get("source_episodes", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

    def record_success(self) -> None:
        self.success_count += 1
        self.updated_at = datetime.now()

    def record_failure(self) -> None:
        self.fail_count += 1
        self.updated_at = datetime.now()

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        if total == 0:
            return 0.5
        return self.success_count / total


@dataclass
class Goal:
    """目标定义"""

    id: str
    description: str
    priority: int = 5
    status: GoalStatus = field(default_factory=lambda: GoalStatus.ACTIVE)
    parent_id: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    deadline: datetime | None = None
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        if isinstance(self.status, str):
            self.status = GoalStatus(self.status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "priority": self.priority,
            "status": self.status.value,
            "parent_id": self.parent_id,
            "created_at": self.created_at.isoformat(),
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Goal":
        return cls(
            id=data["id"],
            description=data["description"],
            priority=data.get("priority", 5),
            status=GoalStatus(data.get("status", "active")),
            parent_id=data.get("parent_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
            deadline=datetime.fromisoformat(data["deadline"]) if data.get("deadline") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        )

    def complete(self) -> None:
        self.status = GoalStatus.COMPLETED
        self.completed_at = datetime.now()

    def fail(self) -> None:
        self.status = GoalStatus.FAILED
        self.completed_at = datetime.now()

    def is_active(self) -> bool:
        return self.status == GoalStatus.ACTIVE


@dataclass
class ToolExecution:
    """工具执行记录"""

    tool_name: str
    arguments: dict[str, Any]
    result: Any = None
    error: str | None = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result,
            "error": self.error,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolExecution":
        return cls(
            tool_name=data["tool_name"],
            arguments=data.get("arguments", {}),
            result=data.get("result"),
            error=data.get("error"),
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
        )

    def finish(self, result: Any) -> None:
        self.result = result
        self.end_time = datetime.now()

    def record_error(self, error: str) -> None:
        self.error = error
        self.end_time = datetime.now()

    @property
    def duration_ms(self) -> float | None:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds() * 1000


@dataclass
class WorkingMemory:
    """工作记忆 - 当前会话状态"""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    active_goals: list[Goal] = field(default_factory=list)
    attention_weights: dict[str, float] = field(default_factory=dict)
    tool_chain: list[ToolExecution] = field(default_factory=list)
    temp_vars: dict[str, Any] = field(default_factory=dict)
    session_start: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "active_goals": [g.to_dict() for g in self.active_goals],
            "attention_weights": self.attention_weights,
            "tool_chain": [t.to_dict() for t in self.tool_chain],
            "temp_vars": self.temp_vars,
            "session_start": self.session_start.isoformat(),
            "last_activity": self.last_activity.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkingMemory":
        return cls(
            session_id=data.get("session_id", str(uuid.uuid4())),
            active_goals=[Goal.from_dict(g) for g in data.get("active_goals", [])],
            attention_weights=data.get("attention_weights", {}),
            tool_chain=[ToolExecution.from_dict(t) for t in data.get("tool_chain", [])],
            temp_vars=data.get("temp_vars", {}),
            session_start=datetime.fromisoformat(data.get("session_start", datetime.now().isoformat())),
            last_activity=datetime.fromisoformat(data.get("last_activity", datetime.now().isoformat())),
        )

    def touch(self) -> None:
        self.last_activity = datetime.now()

    def add_goal(self, description: str, priority: int = 5, parent_id: str | None = None) -> str:
        goal_id = str(uuid.uuid4())
        goal = Goal(
            id=goal_id,
            description=description,
            priority=priority,
            parent_id=parent_id,
        )
        self.active_goals.append(goal)
        self.touch()
        return goal_id

    def complete_goal(self, goal_id: str) -> bool:
        for goal in self.active_goals:
            if goal.id == goal_id and goal.is_active():
                goal.complete()
                self.touch()
                return True
        return False

    def get_active_goals(self) -> list[Goal]:
        return [g for g in self.active_goals if g.is_active()]

    def start_tool_execution(self, tool_name: str, arguments: dict[str, Any]) -> ToolExecution:
        exec_record = ToolExecution(tool_name=tool_name, arguments=arguments)
        self.tool_chain.append(exec_record)
        self.touch()
        return exec_record

    def update_attention(self, key: str, weight: float) -> None:
        self.attention_weights[key] = max(0.0, min(1.0, weight))

    def clear_tool_chain(self) -> None:
        self.tool_chain.clear()


@dataclass
class RetrievedContext:
    """检索到的上下文"""

    episodes: list[Episode] = field(default_factory=list)
    knowledge_nodes: list[KnowledgeNode] = field(default_factory=list)
    working_fragments: list[Message] = field(default_factory=list)
    relevance_scores: dict[str, float] = field(default_factory=dict)
    formatted_text: str = ""

    def is_empty(self) -> bool:
        return not (self.episodes or self.knowledge_nodes or self.working_fragments)


@dataclass
class MemoryConfig:
    """记忆系统配置"""

    episodes_path: str = "~/.hermes/episodes.json"
    enable_vector_store: bool = False
    max_working_messages: int = 50
    episodic_retention_days: int = 90
    importance_threshold: int = 3

    def __post_init__(self) -> None:
        from pathlib import Path

        self.episodes_path = str(Path(self.episodes_path).expanduser())


class VectorStore(Protocol):
    """向量存储接口"""

    async def embed(self, text: str) -> list[float]: ...

    async def store(self, id: str, embedding: list[float], metadata: dict[str, Any]) -> None: ...

    async def search(self, query_embedding: list[float], top_k: int = 5) -> list[tuple[str, float]]: ...

    async def delete(self, id: str) -> None: ...
