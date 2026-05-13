from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from hermes.core.memory.bm25 import BM25Scorer, ScoredEpisode, fuse_results
from hermes.core.memory.episode_store import EpisodeStore
from hermes.core.memory.models import (
    EntityRef,
    Episode,
    EventType,
    MemoryConfig,
    ToolExecution,
)
from hermes.core.memory.privacy_filter import filter_episode, filter_text


class MemoryManager:
    """记忆管理器 - 情景记录、BM25+关键词融合检索、隐私过滤、去重、衰减"""

    def __init__(
        self,
        episodes_path: Path,
        config: MemoryConfig | None = None,
        knowledge_graph_path: Path | None = None,
    ) -> None:
        self._config = config or MemoryConfig(episodes_path=str(episodes_path))
        self._store = EpisodeStore(
            Path(self._config.episodes_path),
            decay_rate=self._config.decay_rate,
            min_retention_score=self._config.min_retention_score,
        )
        self._bm25 = BM25Scorer()
        self._bm25_dirty = True
        self._recent_hashes: dict[str, datetime] = {}
        self._dedup_window = timedelta(minutes=5)

        self._kg = None
        if knowledge_graph_path:
            from hermes.core.memory.knowledge_graph import KnowledgeGraph

            self._kg = KnowledgeGraph(knowledge_graph_path)

    # ── write path ──────────────────────────────────────────────

    def record_interaction(
        self,
        session_id: str,
        user_input: str,
        agent_response: str,
        tool_executions: list[ToolExecution] | None = None,
    ) -> Episode | None:
        """记录一次交互，返回存储的 Episode 或 None（被去重/阈值过滤）"""
        tools = tool_executions or []

        # Dedup check (SHA-256, 5min window)
        content_hash = hashlib.sha256(
            f"{session_id}:{user_input[:200]}".encode()
        ).hexdigest()
        self._clean_stale_hashes()
        if content_hash in self._recent_hashes:
            return None

        # Prune decayed before adding new
        self._store.prune_decayed(datetime.now())

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
            content_hash=content_hash,
        )

        # Privacy filter before persistence
        filter_episode(episode)

        if episode.importance >= self._config.importance_threshold:
            self._store.append(episode)
            self._recent_hashes[content_hash] = datetime.now()
            self._bm25_dirty = True

            # Feed knowledge graph
            if self._kg and episode.entities:
                try:
                    self._kg.add_entities(episode.entities, episode.id)
                except Exception:
                    pass

            return episode
        return None

    # ── read path ───────────────────────────────────────────────

    def retrieve_context(
        self,
        query: str,
        max_episodes: int = 5,
        recent_days: int = 30,
    ) -> str:
        """检索相关上下文（BM25 + 关键词融合 + 图谱增强），返回格式化文本"""
        now = datetime.now()
        episodes = self._store.query_by_time(
            now - timedelta(days=recent_days),
            now,
        )

        if not episodes:
            return ""

        # BM25 scoring
        if self._bm25_dirty or self._bm25.is_empty:
            summaries = [ep.summary for ep in episodes]
            self._bm25.fit(summaries)
            self._bm25_dirty = False

        bm25_scores = self._bm25.score(query)

        # Keyword match scores
        kw_scores = [self._keyword_match_score(query, ep.summary) for ep in episodes]

        # Fuse
        candidates = fuse_results(episodes, bm25_scores, kw_scores, alpha=0.6)

        # Graph enrichment (1-hop from query entities)
        if self._kg:
            candidates = self._enrich_from_graph(query, episodes, candidates)

        if not candidates:
            return ""

        # Session diversification (max 3 per session)
        diversified = self._diversify(candidates, max_episodes)

        # Record access (strengthens retrieved memories)
        for scored in diversified:
            try:
                self._store.record_access(scored.episode.id, now)
            except Exception:
                pass

        # Format output
        parts: list[str] = ["## 相关历史记录"]
        for scored in diversified:
            ep = scored.episode
            date_str = ep.timestamp.strftime("%Y-%m-%d")
            parts.append(f"- [{date_str}] {ep.summary}")

        result = "\n".join(parts)
        return filter_text(result)

    def get_stats(self) -> dict[str, Any]:
        return self._store.get_stats()

    # ── private helpers ─────────────────────────────────────────

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

    def _keyword_match_score(self, query: str, text: str) -> float:
        keywords = self._extract_keywords(query)
        if not keywords:
            return 0.0
        text_lower = text.lower()
        hits = sum(1 for kw in keywords if kw in text_lower)
        return hits / len(keywords)

    def _diversify(
        self, candidates: list[ScoredEpisode], max_episodes: int, max_per_session: int = 3
    ) -> list[ScoredEpisode]:
        session_counts: dict[str, int] = {}
        diversified: list[ScoredEpisode] = []
        for scored in candidates:
            sid = scored.episode.session_id
            count = session_counts.get(sid, 0)
            if count < max_per_session:
                diversified.append(scored)
                session_counts[sid] = count + 1
            if len(diversified) >= max_episodes:
                break
        return diversified

    def _enrich_from_graph(
        self,
        query: str,
        all_episodes: list[Episode],
        candidates: list[ScoredEpisode],
    ) -> list[ScoredEpisode]:
        """Boost episodes that relate to graph entities found in the query."""
        if not self._kg:
            return candidates

        entities = self._extract_entities(query, "")
        if not entities:
            return candidates

        graph_episode_ids: set[str] = set()
        for entity in entities:
            related = self._kg.query_related_entities(entity.name)
            for node, _edge in related:
                graph_episode_ids.update(node.source_episodes)

        if not graph_episode_ids:
            return candidates

        existing_ids = {s.episode.id for s in candidates}
        all_eps_by_id = {ep.id: ep for ep in all_episodes}
        for ep_id in graph_episode_ids:
            if ep_id not in existing_ids and ep_id in all_eps_by_id:
                candidates.append(
                    ScoredEpisode(
                        episode=all_eps_by_id[ep_id],
                        bm25_score=0.0,
                        keyword_score=0.3,
                        combined_score=0.21,  # 0.3 * 0.7 (graph bonus multiplier)
                    )
                )

        candidates.sort(key=lambda s: s.combined_score, reverse=True)
        return candidates

    def _clean_stale_hashes(self) -> None:
        cutoff = datetime.now() - self._dedup_window * 2
        stale = [h for h, ts in self._recent_hashes.items() if ts < cutoff]
        for h in stale:
            del self._recent_hashes[h]
