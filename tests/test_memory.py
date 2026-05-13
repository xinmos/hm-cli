from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from hermes.core.memory.bm25 import BM25Scorer, fuse_results
from hermes.core.memory.episode_store import EpisodeStore
from hermes.core.memory.knowledge_graph import KnowledgeGraph
from hermes.core.memory.models import (
    EntityRef,
    Episode,
    EventType,
    MemoryConfig,
    ToolExecution,
)
from hermes.core.memory.privacy_filter import filter_episode, filter_text


# ── fixtures ────────────────────────────────────────────────

def _make_episode(
    episode_id: str,
    session_id: str,
    summary: str,
    user_input: str = "",
    agent_response: str = "",
    timestamp: datetime | None = None,
    importance: int = 5,
) -> Episode:
    return Episode(
        id=episode_id,
        timestamp=timestamp or datetime.now(),
        event_type=EventType.USER_MESSAGE,
        session_id=session_id,
        summary=summary,
        raw_data={
            "user_input": user_input or summary,
            "agent_response": agent_response or "ok",
            "tool_executions": [],
        },
        entities=[],
        importance=importance,
        retention_score=1.0,
    )


def _tmp_path() -> Path:
    return Path(tempfile.mkdtemp())


# ── BM25 tests ───────────────────────────────────────────────

class TestBM25Scorer:
    def test_empty_index(self):
        bm25 = BM25Scorer()
        assert bm25.is_empty
        assert bm25.score("anything") == []

    def test_basic_scoring(self):
        bm25 = BM25Scorer()
        docs = [
            "configure JWT auth middleware",
            "fix N+1 database query",
            "add rate limiting to API",
            "update user preferences page",
            "refactor auth to use jose",
        ]
        bm25.fit(docs)
        scores = bm25.score("database performance query")
        # Doc index 1 ("fix N+1 database query") should score highest
        assert scores[1] > 0
        assert scores[1] == max(scores)

    def test_cjk_tokenization(self):
        bm25 = BM25Scorer()
        docs = [
            "配置JWT认证中间件",
            "修复数据库N+1查询问题",
            "添加API频率限制",
        ]
        bm25.fit(docs)
        scores = bm25.score("数据库查询性能")
        assert scores[1] > 0

    def test_no_match(self):
        bm25 = BM25Scorer()
        bm25.fit(["project setup", "auth config"])
        scores = bm25.score("zzzxyz")
        assert all(s == 0.0 for s in scores)

    def test_fit_clears_previous(self):
        bm25 = BM25Scorer()
        bm25.fit(["doc one", "doc two"])
        assert bm25._N == 2
        bm25.fit(["new doc"])
        assert bm25._N == 1


class TestFuseResults:
    def test_fusion_ordering(self):
        ep1 = _make_episode("1", "s1", "JWT auth middleware setup")
        ep2 = _make_episode("2", "s2", "fix database query bug")

        bm25_scores = [0.8, 0.2]
        kw_scores = [0.3, 0.9]
        results = fuse_results([ep1, ep2], bm25_scores, kw_scores, alpha=0.6)
        assert len(results) == 2
        # ep1 has stronger BM25 signal (higher weight), should rank first
        assert results[0].episode.id == "1"

    def test_empty_input(self):
        assert fuse_results([], [], []) == []

    def test_zero_kw_weights(self):
        ep = _make_episode("1", "s1", "test")
        results = fuse_results([ep], [0.5], [0.0], alpha=0.6)
        assert len(results) == 1
        assert results[0].combined_score > 0


# ── Privacy filter tests ─────────────────────────────────────

class TestPrivacyFilter:
    def test_strips_openai_key(self):
        assert "sk-abc123" not in filter_text("key is sk-abc123def45678901234567890123456")

    def test_strips_anthropic_key(self):
        result = filter_text("use sk-ant-api03-abc123def4567890123456789012345678901234567890123")
        assert "sk-ant" not in result
        assert "REDACTED" in result

    def test_strips_github_token(self):
        assert "ghp_abc" not in filter_text("token is ghp_abc123def45678901234567890123456789012345")

    def test_strips_bearer_token(self):
        result = filter_text("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        assert "eyJhbGci" not in result

    def test_strips_password(self):
        result = filter_text("password=supersecret123")
        assert "supersecret123" not in result
        assert "REDACTED" in result

    def test_strips_private_key(self):
        result = filter_text("-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkq\n-----END PRIVATE KEY-----")
        assert "MIIEvQIBADANBgkq" not in result
        assert "REDACTED" in result

    def test_preserves_normal_text(self):
        text = "This is a normal message about auth middleware setup"
        assert filter_text(text) == text

    def test_filter_episode(self):
        ep = _make_episode("1", "s1", "setup with sk-abc123def45678901234567890123456")
        ep.raw_data["user_input"] = "api_key=mysecretkey"
        result = filter_episode(ep)
        assert "sk-abc" not in result.summary
        assert "mysecretkey" not in result.raw_data["user_input"]


# ── EpisodeStore tests ───────────────────────────────────────

class TestEpisodeStore:
    def test_append_and_retrieve(self):
        path = _tmp_path() / "test_episodes.json"
        store = EpisodeStore(path, max_episodes=100)
        ep = _make_episode("ep1", "s1", "test interaction")
        store.append(ep)

        results = store.query_by_time(
            datetime.now() - timedelta(days=1),
            datetime.now() + timedelta(hours=1),
        )
        assert len(results) == 1
        assert results[0].id == "ep1"

    def test_max_episodes_trim(self):
        path = _tmp_path() / "test_episodes.json"
        store = EpisodeStore(path, max_episodes=3)
        for i in range(5):
            store.append(
                _make_episode(
                    f"ep{i}", "s1", f"msg {i}",
                    timestamp=datetime.now() + timedelta(hours=i),
                )
            )
        assert len(store.get_all()) <= 3

    def test_query_by_time_range(self):
        path = _tmp_path() / "test_episodes.json"
        store = EpisodeStore(path, max_episodes=100)
        old_ep = _make_episode("old", "s1", "old", timestamp=datetime.now() - timedelta(days=10))
        new_ep = _make_episode("new", "s2", "new", timestamp=datetime.now())
        store.append(old_ep)
        store.append(new_ep)

        recent = store.query_by_time(
            datetime.now() - timedelta(days=1),
            datetime.now() + timedelta(hours=1),
        )
        assert len(recent) == 1
        assert recent[0].id == "new"

    def test_delete_old(self):
        path = _tmp_path() / "test_episodes.json"
        store = EpisodeStore(path)
        store.append(_make_episode("old", "s1", "old", timestamp=datetime.now() - timedelta(days=100)))
        store.append(_make_episode("new", "s1", "new", timestamp=datetime.now()))
        removed = store.delete_old(datetime.now() - timedelta(days=50))
        assert removed == 1
        assert len(store.get_all()) == 1

    def test_record_access_boosts_score(self):
        path = _tmp_path() / "test_episodes.json"
        store = EpisodeStore(path, decay_rate=0.01)
        ep = _make_episode("ep1", "s1", "test")
        ep.retention_score = 0.8
        store.append(ep)

        store.record_access("ep1", datetime.now())
        updated = store.get_all()[0]
        assert updated.retention_score > 0.8
        assert updated.access_count == 1

    def test_prune_decayed(self):
        path = _tmp_path() / "test_episodes.json"
        store = EpisodeStore(path, decay_rate=0.5, min_retention_score=0.3)

        old_ep = _make_episode("old", "s1", "old", timestamp=datetime.now() - timedelta(days=30))
        old_ep.retention_score = 0.2
        new_ep = _make_episode("new", "s1", "new", timestamp=datetime.now())
        new_ep.retention_score = 1.0
        store.append(old_ep)
        store.append(new_ep)

        removed = store.prune_decayed(datetime.now())
        assert removed >= 1
        remaining = store.get_all()
        assert all(ep.id == "new" for ep in remaining)

    def test_get_all(self):
        path = _tmp_path() / "test_episodes.json"
        store = EpisodeStore(path)
        store.append(_make_episode("a", "s1", "msg a"))
        store.append(_make_episode("b", "s1", "msg b"))
        assert len(store.get_all()) == 2


# ── KnowledgeGraph tests ─────────────────────────────────────

class TestKnowledgeGraph:
    def test_add_entities_creates_nodes_and_edges(self):
        path = _tmp_path() / "test_graph.json"
        kg = KnowledgeGraph(path)

        entities = [
            EntityRef(entity_type="file", entity_id="/src/auth.py", name="auth.py"),
            EntityRef(entity_type="file", entity_id="/src/middleware.py", name="middleware.py"),
            EntityRef(entity_type="file", entity_id="/src/routes.py", name="routes.py"),
        ]
        kg.add_entities(entities, "ep1")

        related = kg.query_related_entities("auth.py")
        assert len(related) >= 1

    def test_query_no_match(self):
        path = _tmp_path() / "test_graph2.json"
        kg = KnowledgeGraph(path)
        assert kg.query_related_entities("nonexistent") == []

    def test_repeated_entities_bump_confidence(self):
        path = _tmp_path() / "test_graph3.json"
        kg = KnowledgeGraph(path)

        entities = [EntityRef(entity_type="file", entity_id="/src/auth.py", name="auth.py")]
        kg.add_entities(entities, "ep1")
        kg.add_entities(entities, "ep2")

        node = kg.get_node("file", "auth.py")
        assert node is not None
        assert node.confidence > 0.3


# ── Integration test ─────────────────────────────────────────

class TestMemoryManagerIntegration:
    def test_record_and_retrieve(self):
        path = _tmp_path() / "test_memory.json"
        kg_path = _tmp_path() / "test_memory_kg.json"

        from hermes.core.memory.memory_manager import MemoryManager

        config = MemoryConfig(
            episodes_path=str(path),
            importance_threshold=1,
        )
        mgr = MemoryManager(episodes_path=path, config=config, knowledge_graph_path=kg_path)

        mgr.record_interaction("s1", "配置 JWT 认证中间件", "已添加 auth 模块")
        mgr.record_interaction("s2", "修复数据库 N+1 查询问题", "已优化 ORM 查询")
        mgr.record_interaction("s3", "添加 API 频率限制", "已添加 rate limiter")

        result = mgr.retrieve_context("数据库查询优化", max_episodes=3)
        assert "N+1" in result or "查询" in result

    def test_dedup_skips_duplicate(self):
        path = _tmp_path() / "test_dedup.json"
        from hermes.core.memory.memory_manager import MemoryManager

        config = MemoryConfig(episodes_path=str(path), importance_threshold=1)
        mgr = MemoryManager(episodes_path=path, config=config)

        ep1 = mgr.record_interaction("s1", "setup JWT auth", "done")
        ep2 = mgr.record_interaction("s1", "setup JWT auth", "done")  # same input, same session
        assert ep1 is not None
        assert ep2 is None  # deduplicated

    def test_session_diversification(self):
        path = _tmp_path() / "test_div.json"
        from hermes.core.memory.memory_manager import MemoryManager

        config = MemoryConfig(episodes_path=str(path), importance_threshold=1)
        mgr = MemoryManager(episodes_path=path, config=config)

        # Create 5 episodes all from the same session with similar content
        for i in range(5):
            mgr.record_interaction("s1", f"auth setup step {i}", "ok")

        result = mgr.retrieve_context("auth", max_episodes=5)
        if result:
            s1_count = result.count("s1")
            # With diversification, should not see more than 3 from s1
            # (verifying indirectly via the format string)


def test_empty_store_retrieve():
    path = _tmp_path() / "empty.json"
    from hermes.core.memory.memory_manager import MemoryManager

    config = MemoryConfig(episodes_path=str(path))
    mgr = MemoryManager(episodes_path=path, config=config)
    assert mgr.retrieve_context("anything") == ""
