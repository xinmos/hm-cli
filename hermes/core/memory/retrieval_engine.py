from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from hermes.core.memory.models import (
    Episode,
    KnowledgeNode,
    Message,
    RetrievedContext,
    WorkingMemory,
)
from hermes.infra.persistence.memory_stores import EpisodicStore, SemanticStore


@dataclass
class QueryUnderstanding:
    """查询理解结果"""

    intent: str
    entity_types: list[str]
    time_range: tuple[datetime, datetime] | None
    source_weights: dict[str, float]
    keywords: list[str]


@dataclass
class SearchResult:
    """搜索结果"""

    item: Episode | KnowledgeNode | Message
    source: str  # "episodic", "semantic", "working"
    relevance_score: float
    match_reason: str


class RetrievalEngine:
    """检索引擎"""

    def __init__(
        self,
        episodic_store: EpisodicStore,
        semantic_store: SemanticStore,
        working_memory: WorkingMemory,
    ) -> None:
        self._episodic = episodic_store
        self._semantic = semantic_store
        self._wm = working_memory

    async def retrieve(
        self,
        query: str,
        max_tokens: int = 4000,
        top_k: int = 10,
    ) -> RetrievedContext:
        """检索相关上下文"""
        # 1. 理解查询
        query_understanding = self._understand_query(query)

        # 2. 并行检索三个通道
        all_results: list[SearchResult] = []

        # 从情景记忆检索
        episodic_results = self._search_episodic(query_understanding, top_k)
        all_results.extend(episodic_results)

        # 从语义记忆检索
        semantic_results = self._search_semantic(query_understanding, top_k // 2)
        all_results.extend(semantic_results)

        # 从工作记忆检索
        working_results = self._search_working(query_understanding, top_k // 2)
        all_results.extend(working_results)

        # 3. 融合排序
        fused_results = self._fuse_results(all_results, query_understanding)

        # 4. 组装上下文
        context = self._assemble_context(fused_results[:top_k], max_tokens)

        return context

    def _understand_query(self, query: str) -> QueryUnderstanding:
        """理解查询意图"""
        query_lower = query.lower()

        # 提取关键词
        keywords = self._extract_keywords(query)

        # 识别实体类型
        entity_types: list[str] = []
        if any(kw in query_lower for kw in ["文件", "file", "文档", "document"]):
            entity_types.append("file")
        if any(kw in query_lower for kw in ["函数", "function", "方法", "method", "类", "class"]):
            entity_types.append("code")
        if any(kw in query_lower for kw in ["设置", "配置", "config", "setting", "preference"]):
            entity_types.append("preference")

        # 识别时间范围
        time_range = self._extract_time_range(query_lower)

        # 确定来源权重
        source_weights = {"episodic": 0.4, "semantic": 0.3, "working": 0.3}

        # 根据查询类型调整权重
        if entity_types and "preference" in entity_types:
            # 偏好查询更依赖语义记忆
            source_weights = {"episodic": 0.2, "semantic": 0.5, "working": 0.3}
        elif "最近" in query or "recent" in query_lower:
            # 最近查询更依赖工作记忆和情景记忆
            source_weights = {"episodic": 0.5, "semantic": 0.2, "working": 0.3}

        return QueryUnderstanding(
            intent=query,
            entity_types=entity_types,
            time_range=time_range,
            source_weights=source_weights,
            keywords=keywords,
        )

    def _extract_keywords(self, text: str) -> list[str]:
        """提取关键词"""
        # 简单的关键词提取：去除停用词后的有意义的词
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "的", "了", "是", "在", "有", "和", "与", "或",
        }

        words = re.findall(r"\b\w+\b", text.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        # 去重并保持顺序
        seen: set[str] = set()
        result: list[str] = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                result.append(kw)

        return result[:10]  # 限制关键词数量

    def _extract_time_range(self, query: str) -> tuple[datetime, datetime] | None:
        """从查询中提取时间范围"""
        now = datetime.now()

        # 检测常见时间表达
        if any(kw in query for kw in ["今天", "today"]):
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return (start, now)

        if any(kw in query for kw in ["昨天", "yesterday"]):
            end = now.replace(hour=0, minute=0, second=0, microsecond=0)
            start = end - __import__("datetime").timedelta(days=1)
            return (start, end)

        if any(kw in query for kw in ["本周", "这周", "this week"]):
            start = now - __import__("datetime").timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            return (start, now)

        if any(kw in query for kw in ["最近", "近期", "recent", "lately"]):
            start = now - __import__("datetime").timedelta(days=7)
            return (start, now)

        if any(kw in query for kw in ["上个月", "last month"]):
            end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if end.month == 1:
                start = end.replace(year=end.year - 1, month=12)
            else:
                start = end.replace(month=end.month - 1)
            return (start, end)

        return None

    def _search_episodic(
        self, query: QueryUnderstanding, top_k: int
    ) -> list[SearchResult]:
        """搜索情景记忆"""
        results: list[SearchResult] = []

        # 基于时间范围查询
        if query.time_range:
            episodes = self._episodic.query_by_time(
                query.time_range[0], query.time_range[1]
            )
        else:
            # 默认查询最近30天
            from datetime import datetime, timedelta
            episodes = self._episodic.query_by_time(
                datetime.now() - timedelta(days=30),
                datetime.now(),
            )

        # 计算相关性分数
        for ep in episodes:
            score = self._calculate_episode_relevance(ep, query)
            if score > 0.3:  # 阈值
                results.append(
                    SearchResult(
                        item=ep,
                        source="episodic",
                        relevance_score=score,
                        match_reason="关键词匹配" if query.keywords else "时间范围匹配",
                    )
                )

        # 按分数排序并限制数量
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:top_k]

    def _calculate_episode_relevance(
        self, episode: Episode, query: QueryUnderstanding
    ) -> float:
        """计算情景与查询的相关性"""
        score = 0.0
        text = f"{episode.summary} {' '.join(episode.tags)}".lower()

        # 关键词匹配
        if query.keywords:
            matches = sum(1 for kw in query.keywords if kw.lower() in text)
            score += (matches / len(query.keywords)) * 0.5

        # 实体类型匹配
        if query.entity_types:
            for entity in episode.entities:
                if entity.entity_type in query.entity_types:
                    score += 0.3
                    break

        # 时间衰减
        days_old = (datetime.now() - episode.timestamp).days
        time_decay = max(0.3, 1.0 - (days_old / 30))  # 30天后衰减到0.3
        score *= time_decay

        return min(1.0, score)

    def _search_semantic(
        self, query: QueryUnderstanding, top_k: int
    ) -> list[SearchResult]:
        """搜索语义记忆"""
        results: list[SearchResult] = []

        # 基于实体类型查询
        if query.entity_types:
            for entity_type in query.entity_types:
                # 这里简化实现，实际应该支持按类型查询
                pass

        # 基于关键词查询节点
        for keyword in query.keywords[:3]:  # 限制关键词数量
            nodes = self._semantic.find_nodes_by_name(keyword)
            for node in nodes:
                score = self._calculate_node_relevance(node, query)
                results.append(
                    SearchResult(
                        item=node,
                        source="semantic",
                        relevance_score=score,
                        match_reason=f"匹配节点: {node.name}",
                    )
                )

        # 去重并按分数排序
        seen_ids: set[str] = set()
        unique_results: list[SearchResult] = []
        for r in sorted(results, key=lambda x: x.relevance_score, reverse=True):
            item_id = r.item.id if hasattr(r.item, "id") else str(id(r.item))
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                unique_results.append(r)

        return unique_results[:top_k]

    def _calculate_node_relevance(
        self, node: KnowledgeNode, query: QueryUnderstanding
    ) -> float:
        """计算节点与查询的相关性"""
        score = node.confidence  # 基础分来自节点置信度

        # 名称匹配
        name_lower = node.name.lower()
        for keyword in query.keywords:
            if keyword.lower() in name_lower:
                score += 0.3

        # 实体类型匹配
        if node.entity_type in query.entity_types:
            score += 0.2

        return min(1.0, score)

    def _search_working(
        self, query: QueryUnderstanding, top_k: int
    ) -> list[SearchResult]:
        """搜索工作记忆"""
        results: list[SearchResult] = []

        # 获取高注意力的消息
        for msg in self._wm.messages:
            score = self._calculate_message_relevance(msg, query)
            if score > 0.3:
                results.append(
                    SearchResult(
                        item=msg,
                        source="working",
                        relevance_score=score,
                        match_reason="工作记忆中的相关消息",
                    )
                )

        # 按分数排序
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:top_k]

    def _calculate_message_relevance(
        self, message: Message, query: QueryUnderstanding
    ) -> float:
        """计算消息与查询的相关性"""
        score = 0.0
        content_lower = message.content.lower()

        # 关键词匹配
        for keyword in query.keywords:
            if keyword.lower() in content_lower:
                score += 0.4

        # 角色权重
        if message.role == "system":
            score += 0.1

        # 时间衰减（越新的消息越重要）
        if message.timestamp:
            age_hours = (datetime.now() - message.timestamp).total_seconds() / 3600
            time_decay = max(0.5, 1.0 - (age_hours / 24))  # 24小时后衰减到0.5
            score *= time_decay

        return min(1.0, score)

    def _fuse_results(
        self,
        results: list[SearchResult],
        query: QueryUnderstanding,
    ) -> list[SearchResult]:
        """融合多个来源的检索结果"""
        if not results:
            return []

        # 应用来源权重
        weights = query.source_weights
        for result in results:
            source_weight = weights.get(result.source, 0.33)
            result.relevance_score *= source_weight

        # 按分数排序
        results.sort(key=lambda x: x.relevance_score, reverse=True)

        # 多样性处理：确保不同类型的结果都有代表
        final_results: list[SearchResult] = []
        source_counts: dict[str, int] = {"episodic": 0, "semantic": 0, "working": 0}
        max_per_source = 5

        for result in results:
            source = result.source
            if source_counts[source] < max_per_source:
                final_results.append(result)
                source_counts[source] += 1

            if len(final_results) >= 10:  # 限制总数
                break

        return final_results

    def _assemble_context(
        self, results: list[SearchResult], max_tokens: int
    ) -> RetrievedContext:
        """组装检索结果到上下文"""
        context = RetrievedContext()

        episodes: list[Episode] = []
        nodes: list[KnowledgeNode] = []
        messages: list[Message] = []

        for result in results:
            if isinstance(result.item, Episode):
                episodes.append(result.item)
                context.relevance_scores[result.item.id] = result.relevance_score
            elif isinstance(result.item, KnowledgeNode):
                nodes.append(result.item)
                context.relevance_scores[result.item.id] = result.relevance_score
            elif isinstance(result.item, Message):
                messages.append(result.item)

        context.episodes = episodes
        context.knowledge_nodes = nodes
        context.working_fragments = messages

        # 格式化为文本
        context.formatted_text = self._format_context_text(context)

        return context

    def _format_context_text(self, context: RetrievedContext) -> str:
        """格式化上下文为文本"""
        parts: list[str] = []

        if context.episodes:
            parts.append("## 相关历史")
            for ep in context.episodes[:3]:
                date_str = ep.timestamp.strftime("%m-%d")
                parts.append(f"[{date_str}] {ep.summary}")
            parts.append("")

        if context.knowledge_nodes:
            parts.append("## 相关知识")
            for node in context.knowledge_nodes[:3]:
                parts.append(f"- {node.name} ({node.entity_type})")
            parts.append("")

        if context.working_fragments:
            parts.append("## 当前上下文")
            for msg in context.working_fragments[:2]:
                preview = msg.content[:100]
                if len(msg.content) > 100:
                    preview += "..."
                parts.append(f"[{msg.role}] {preview}")
            parts.append("")

        return "\n".join(parts)
