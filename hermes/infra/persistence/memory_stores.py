import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from hermes.core.memory.models import (
    Episode,
    EntityRef,
    EventType,
    KnowledgeEdge,
    KnowledgeNode,
    Rule,
)


class EpisodicStore:
    """情景记忆存储"""

    def __init__(self, db_path: Path, vector_store: Any | None = None) -> None:
        self._db_path = db_path
        self._vector_store = vector_store
        self._init_schema()

    def _init_schema(self) -> None:
        """初始化数据库结构"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    summary TEXT,
                    raw_data TEXT,
                    entities TEXT,
                    importance INTEGER DEFAULT 5,
                    retention_score REAL DEFAULT 1.0,
                    tags TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodes_timestamp
                ON episodes(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodes_session
                ON episodes(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodes_type
                ON episodes(event_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodes_importance
                ON episodes(importance)
            """)

    def append(self, episode: Episode) -> None:
        """追加情景记录"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO episodes
                (id, timestamp, event_type, session_id, summary, raw_data, entities,
                 importance, retention_score, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    episode.id,
                    episode.timestamp.isoformat(),
                    episode.event_type.value,
                    episode.session_id,
                    episode.summary,
                    json.dumps(episode.raw_data, default=str),
                    json.dumps([e.to_dict() for e in episode.entities]),
                    episode.importance,
                    episode.retention_score,
                    json.dumps(episode.tags),
                ),
            )

        if self._vector_store and episode.vector_embedding:
            # 异步操作，这里不等待
            pass

    def get(self, episode_id: str) -> Episode | None:
        """获取单个情景"""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM episodes WHERE id = ?", (episode_id,)
            ).fetchone()

        if row is None:
            return None

        return self._row_to_episode(row)

    def query_by_time(
        self, start: datetime, end: datetime, session_id: str | None = None
    ) -> list[Episode]:
        """按时间范围查询"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            if session_id:
                rows = conn.execute(
                    """
                    SELECT * FROM episodes
                    WHERE timestamp >= ? AND timestamp <= ? AND session_id = ?
                    ORDER BY timestamp
                """,
                    (start.isoformat(), end.isoformat(), session_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM episodes
                    WHERE timestamp >= ? AND timestamp <= ?
                    ORDER BY timestamp
                """,
                    (start.isoformat(), end.isoformat()),
                ).fetchall()

        return [self._row_to_episode(row) for row in rows]

    def query_by_session(self, session_id: str) -> list[Episode]:
        """按会话查询"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM episodes WHERE session_id = ? ORDER BY timestamp
            """,
                (session_id,),
            ).fetchall()

        return [self._row_to_episode(row) for row in rows]

    def query_by_type(self, event_type: EventType) -> list[Episode]:
        """按事件类型查询"""
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM episodes WHERE event_type = ? ORDER BY timestamp DESC
            """,
                (event_type.value,),
            ).fetchall()

        return [self._row_to_episode(row) for row in rows]

    def query_by_importance(self, min_importance: int, limit: int = 100) -> list[Episode]:
        """按重要性查询"""
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM episodes
                WHERE importance >= ?
                ORDER BY importance DESC, timestamp DESC
                LIMIT ?
            """,
                (min_importance, limit),
            ).fetchall()

        return [self._row_to_episode(row) for row in rows]

    def update_retention_score(self, episode_id: str, score: float) -> None:
        """更新保留分数"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE episodes SET retention_score = ? WHERE id = ?",
                (score, episode_id),
            )

    def delete_old_episodes(self, before: datetime) -> int:
        """删除旧的情景记录"""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM episodes WHERE timestamp < ?",
                (before.isoformat(),),
            )
            return cursor.rowcount

    def _row_to_episode(self, row: sqlite3.Row) -> Episode:
        """将行数据转换为Episode"""
        entities_raw = row["entities"]
        entities = []
        if entities_raw:
            try:
                entities_data = json.loads(entities_raw)
                entities = [EntityRef.from_dict(e) for e in entities_data]
            except (json.JSONDecodeError, TypeError):
                pass

        tags_raw = row["tags"]
        tags = []
        if tags_raw:
            try:
                tags = json.loads(tags_raw)
            except (json.JSONDecodeError, TypeError):
                pass

        raw_data = {}
        raw_data_raw = row["raw_data"]
        if raw_data_raw:
            try:
                raw_data = json.loads(raw_data_raw)
            except (json.JSONDecodeError, TypeError):
                pass

        return Episode(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            event_type=EventType(row["event_type"]),
            session_id=row["session_id"],
            summary=row["summary"] or "",
            raw_data=raw_data,
            entities=entities,
            importance=row["importance"],
            retention_score=row["retention_score"],
            vector_embedding=None,
            tags=tags,
        )


class SemanticStore:
    """语义记忆存储"""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._init_schema()

    def _init_schema(self) -> None:
        """初始化知识图谱结构"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_nodes (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    attributes TEXT,
                    confidence REAL DEFAULT 0.5,
                    source_episodes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    version INTEGER DEFAULT 1
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_edges (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    attributes TEXT,
                    confidence REAL DEFAULT 0.5,
                    source_episodes TEXT,
                    FOREIGN KEY (source_id) REFERENCES knowledge_nodes(id),
                    FOREIGN KEY (target_id) REFERENCES knowledge_nodes(id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS rules (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    condition TEXT NOT NULL,
                    action TEXT NOT NULL,
                    priority INTEGER DEFAULT 5,
                    enabled INTEGER DEFAULT 1,
                    success_count INTEGER DEFAULT 0,
                    fail_count INTEGER DEFAULT 0,
                    source_episodes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_nodes_type ON knowledge_nodes(entity_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_nodes_name ON knowledge_nodes(name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_edges_source ON knowledge_edges(source_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_edges_target ON knowledge_edges(target_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rules_enabled ON rules(enabled)
            """)

    def add_node(self, node: KnowledgeNode) -> None:
        """添加知识节点"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO knowledge_nodes
                (id, entity_type, name, attributes, confidence, source_episodes, version)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    node.id,
                    node.entity_type,
                    node.name,
                    json.dumps(node.attributes),
                    node.confidence,
                    json.dumps(node.source_episodes),
                    node.version,
                ),
            )

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        """获取知识节点"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM knowledge_nodes WHERE id = ?", (node_id,)
            ).fetchone()

        if row is None:
            return None

        return self._row_to_node(row)

    def find_nodes_by_name(self, name: str, entity_type: str | None = None) -> list[KnowledgeNode]:
        """按名称查找节点"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            if entity_type:
                rows = conn.execute(
                    """
                    SELECT * FROM knowledge_nodes
                    WHERE name LIKE ? AND entity_type = ?
                """,
                    (f"%{name}%", entity_type),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM knowledge_nodes WHERE name LIKE ?",
                    (f"%{name}%",),
                ).fetchall()

        return [self._row_to_node(row) for row in rows]

    def add_edge(self, edge: KnowledgeEdge) -> None:
        """添加关系边"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO knowledge_edges
                (id, source_id, target_id, relation_type, attributes, confidence, source_episodes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    edge.id,
                    edge.source_id,
                    edge.target_id,
                    edge.relation_type,
                    json.dumps(edge.attributes),
                    edge.confidence,
                    json.dumps(edge.source_episodes),
                ),
            )

    def get_edges_from_node(self, node_id: str) -> list[KnowledgeEdge]:
        """获取从指定节点出发的关系"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM knowledge_edges WHERE source_id = ?",
                (node_id,),
            ).fetchall()

        return [self._row_to_edge(row) for row in rows]

    def add_rule(self, rule: Rule) -> None:
        """添加规则"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO rules
                (id, name, condition, action, priority, enabled, success_count, fail_count, source_episodes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    rule.id,
                    rule.name,
                    rule.condition,
                    rule.action,
                    rule.priority,
                    1 if rule.enabled else 0,
                    rule.success_count,
                    rule.fail_count,
                    json.dumps(rule.source_episodes),
                ),
            )

    def get_enabled_rules(self) -> list[Rule]:
        """获取所有启用的规则"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM rules WHERE enabled = 1 ORDER BY priority DESC"
            ).fetchall()

        return [self._row_to_rule(row) for row in rows]

    def _row_to_node(self, row: sqlite3.Row) -> KnowledgeNode:
        """将行数据转换为KnowledgeNode"""
        attributes = {}
        attrs_raw = row["attributes"]
        if attrs_raw:
            try:
                attributes = json.loads(attrs_raw)
            except (json.JSONDecodeError, TypeError):
                pass

        source_episodes = []
        source_raw = row["source_episodes"]
        if source_raw:
            try:
                source_episodes = json.loads(source_raw)
            except (json.JSONDecodeError, TypeError):
                pass

        return KnowledgeNode(
            id=row["id"],
            entity_type=row["entity_type"],
            name=row["name"],
            attributes=attributes,
            confidence=row["confidence"],
            source_episodes=source_episodes,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            version=row["version"],
        )

    def _row_to_edge(self, row: sqlite3.Row) -> KnowledgeEdge:
        """将行数据转换为KnowledgeEdge"""
        attributes = {}
        attrs_raw = row["attributes"]
        if attrs_raw:
            try:
                attributes = json.loads(attrs_raw)
            except (json.JSONDecodeError, TypeError):
                pass

        source_episodes = []
        source_raw = row["source_episodes"]
        if source_raw:
            try:
                source_episodes = json.loads(source_raw)
            except (json.JSONDecodeError, TypeError):
                pass

        return KnowledgeEdge(
            id=row["id"],
            source_id=row["source_id"],
            target_id=row["target_id"],
            relation_type=row["relation_type"],
            attributes=attributes,
            confidence=row["confidence"],
            source_episodes=source_episodes,
        )

    def _row_to_rule(self, row: sqlite3.Row) -> Rule:
        """将行数据转换为Rule"""
        source_episodes = []
        source_raw = row["source_episodes"]
        if source_raw:
            try:
                source_episodes = json.loads(source_raw)
            except (json.JSONDecodeError, TypeError):
                pass

        return Rule(
            id=row["id"],
            name=row["name"],
            condition=row["condition"],
            action=row["action"],
            priority=row["priority"],
            enabled=bool(row["enabled"]),
            success_count=row["success_count"],
            fail_count=row["fail_count"],
            source_episodes=source_episodes,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


class MemoryStore:
    """统一记忆存储接口"""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self.episodic = EpisodicStore(self._db_path)
        self.semantic = SemanticStore(self._db_path)

    def close(self) -> None:
        """关闭存储"""
        pass

    def get_stats(self) -> dict[str, Any]:
        """获取存储统计"""
        with sqlite3.connect(self._db_path) as conn:
            episode_count = conn.execute(
                "SELECT COUNT(*) FROM episodes"
            ).fetchone()[0]
            node_count = conn.execute(
                "SELECT COUNT(*) FROM knowledge_nodes"
            ).fetchone()[0]
            edge_count = conn.execute(
                "SELECT COUNT(*) FROM knowledge_edges"
            ).fetchone()[0]
            rule_count = conn.execute(
                "SELECT COUNT(*) FROM rules"
            ).fetchone()[0]

        return {
            "episodes": episode_count,
            "knowledge_nodes": node_count,
            "knowledge_edges": edge_count,
            "rules": rule_count,
        }
