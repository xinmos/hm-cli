import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from hermes.core.memory.models import (
    CompressionStrategy,
    Episode,
    EntityRef,
    EventType,
    Goal,
    KnowledgeNode,
    MemoryConfig,
    Message,
    RetrievedContext,
    Rule,
    ToolExecution,
    WorkingMemory,
)
from hermes.core.memory.working_memory import WorkingMemoryManager
from hermes.infra.persistence.memory_stores import MemoryStore


class MemoryManager:
    """记忆管理器 - 统一协调各记忆层"""

    def __init__(
        self,
        working_memory: WorkingMemory | None = None,
        config: MemoryConfig | None = None,
        memory_store: MemoryStore | None = None,
    ) -> None:
        self._config = config or MemoryConfig()
        self._wm = working_memory or WorkingMemory()
        self._wm_manager = WorkingMemoryManager(self._wm)

        # 初始化存储
        if memory_store is None:
            db_path = Path(self._config.db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._store = MemoryStore(db_path)
        else:
            self._store = memory_store

        # 初始化组件
        self._reflection_engine: Any = None  # 延迟加载
        self._retrieval_engine: Any = None  # 延迟加载

    @property
    def working_memory(self) -> WorkingMemory:
        """获取工作记忆"""
        return self._wm

    @property
    def config(self) -> MemoryConfig:
        """获取配置"""
        return self._config

    async def process_interaction(
        self,
        user_input: str,
        agent_response: str,
        tool_executions: list[ToolExecution] | None = None,
    ) -> None:
        """处理交互并触发记忆形成"""
        tools = tool_executions or []

        # 1. 记录到工作记忆
        self._wm.add_message("user", user_input)
        self._wm.add_message("assistant", agent_response)

        # 2. 创建情景记录
        episode = Episode(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            event_type=EventType.USER_MESSAGE,
            session_id=self._wm.session_id,
            summary=self._generate_summary(user_input, agent_response),
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

        # 3. 评估重要性并存储
        if self._should_store_episode(episode):
            self._store.episodic.append(episode)

            # 4. 触发语义提取
            await self._extract_semantic_knowledge(episode)

    def _generate_summary(self, user_input: str, agent_response: str) -> str:
        """生成摘要"""
        # 简化实现：截取用户输入前100字符
        if len(user_input) <= 100:
            return user_input
        return user_input[:100] + "..."

    def _extract_entities(self, user_input: str, agent_response: str) -> list[EntityRef]:
        """提取实体引用"""
        entities: list[EntityRef] = []

        # 简化实现：提取可能的文件路径
        import re

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
        self, user_input: str, agent_response: str, tool_executions: list[ToolExecution]
    ) -> int:
        """计算重要性"""
        importance = 5

        # 基于关键词调整
        important_keywords = ["重要", "关键", "必须", "记住", "保存", "配置"]
        if any(kw in user_input for kw in important_keywords):
            importance += 2

        # 基于工具执行调整
        if tool_executions:
            importance += 1
            # 如果有错误，重要性更高
            if any(t.error for t in tool_executions):
                importance += 1

        return max(1, min(10, importance))

    def _extract_tags(self, user_input: str) -> list[str]:
        """提取标签"""
        tags: list[str] = []

        # 基于关键词标签化
        if any(kw in user_input for kw in ["代码", "编程", "函数", "类"]):
            tags.append("coding")
        if any(kw in user_input for kw in ["错误", "问题", "bug", "失败"]):
            tags.append("error")
        if any(kw in user_input for kw in ["配置", "设置", "参数"]):
            tags.append("config")

        return tags

    def _should_store_episode(self, episode: Episode) -> bool:
        """决定是否应该存储该情景"""
        return episode.importance >= self._config.importance_threshold

    async def _extract_semantic_knowledge(self, episode: Episode) -> None:
        """从情景中提取语义知识"""
        # 简化实现：从用户偏好类型的episode中提取知识
        if episode.event_type == EventType.USER_PREFERENCE:
            for entity in episode.entities:
                node = KnowledgeNode(
                    id=str(uuid.uuid4()),
                    entity_type="preference",
                    name=entity.name,
                    attributes={
                        "entity_type": entity.entity_type,
                        "source": episode.summary,
                    },
                    confidence=0.7,
                    source_episodes=[episode.id],
                )
                self._store.semantic.add_node(node)

    async def retrieve_relevant_context(
        self,
        query: str,
        current_messages: list[Message] | None = None,
        max_tokens: int = 4000,
    ) -> RetrievedContext:
        """检索相关上下文"""
        # 简化实现：基于关键词的简单检索
        context = RetrievedContext()

        # 1. 从情景记忆中检索
        # 提取查询关键词（去掉疑问词）
        query_lower = query.lower()
        # 提取有意义的关键词（去掉常见疑问词和助词）
        stop_words = {"我", "你", "是", "的", "了", "在", "有", "什么", "怎么", "如何", "吗", "呢", "请", "问"}
        keywords = [w for w in query_lower.split() if w not in stop_words and len(w) >= 2]

        # 如果没有有效关键词，尝试提取所有中文字符
        if not keywords:
            import re

            keywords = re.findall(r"[\u4e00-\u9fa5]{2,}", query_lower)

        recent_episodes = self._store.episodic.query_by_time(
            datetime.now() - timedelta(days=30),
            datetime.now(),
        )

        for ep in recent_episodes:
            summary_lower = ep.summary.lower()
            # 检查是否有任何关键词匹配
            for keyword in keywords:
                if keyword in summary_lower:
                    context.episodes.append(ep)
                    context.relevance_scores[ep.id] = 0.8
                    break

        # 2. 从工作记忆中获取高注意力内容
        for key, weight in self._wm.attention_weights.items():
            if weight > 0.7:
                # 查找相关消息
                for msg in self._wm.messages:
                    if key.lower() in msg.content.lower():
                        context.working_fragments.append(msg)
                        break

        # 3. 格式化上下文
        context.formatted_text = self._format_context(context)

        return context

    def _format_context(self, context: RetrievedContext) -> str:
        """格式化上下文为文本"""
        parts: list[str] = []

        if context.episodes:
            parts.append("## 相关历史记录")
            for ep in context.episodes[:5]:  # 限制数量
                parts.append(f"- [{ep.timestamp.strftime('%Y-%m-%d')}] {ep.summary}")
            parts.append("")

        if context.working_fragments:
            parts.append("## 当前关注")
            for msg in context.working_fragments[:3]:
                preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                parts.append(f"- {preview}")
            parts.append("")

        return "\n".join(parts)

    async def compress_memory(self, strategy: CompressionStrategy) -> dict[str, Any]:
        """执行记忆压缩"""
        result: dict[str, Any] = {"strategy": strategy.value, "affected": 0}

        if strategy == CompressionStrategy.FLUSH:
            # 冲刷：创建检查点
            result["checkpoint"] = self._create_checkpoint()

        elif strategy == CompressionStrategy.PRUNE:
            # 裁剪：移除低权重内容
            removed = self._prune_working_memory()
            result["removed_messages"] = removed
            result["affected"] = removed

        elif strategy == CompressionStrategy.SUMMARIZE:
            # 摘要：对旧情景生成摘要
            summarized = self._summarize_old_episodes()
            result["summarized_episodes"] = summarized
            result["affected"] = summarized

        elif strategy == CompressionStrategy.SEGMENT:
            # 分段：创建新的会话段
            segment_id = self._create_session_segment()
            result["segment_id"] = segment_id

        return result

    def _create_checkpoint(self) -> str:
        """创建检查点"""
        checkpoint_id = str(uuid.uuid4())[:8]
        # 保存当前工作记忆状态
        # 这里可以添加更多的检查点逻辑
        return checkpoint_id

    def _prune_working_memory(self) -> int:
        """裁剪工作记忆中的低权重内容"""
        if len(self._wm.messages) <= 10:
            return 0

        # 保留系统消息和高注意力消息
        system_msgs = [m for m in self._wm.messages if m.role == "system"]
        other_msgs = [m for m in self._wm.messages if m.role != "system"]

        # 保留最近的消息
        keep_count = min(20, len(other_msgs))
        kept_msgs = other_msgs[-keep_count:]

        removed = len(self._wm.messages) - len(system_msgs) - len(kept_msgs)
        self._wm.messages = system_msgs + kept_msgs

        return removed

    def _summarize_old_episodes(self) -> int:
        """对旧的情景记录生成摘要"""
        # 简化实现：标记超过90天的记录为已归档
        cutoff = datetime.now() - timedelta(days=90)
        # 这里可以添加实际的摘要生成逻辑
        return 0

    def _create_session_segment(self) -> str:
        """创建新的会话段"""
        segment_id = str(uuid.uuid4())[:8]
        # 重置工作记忆但保留系统消息
        system_msgs = [m for m in self._wm.messages if m.role == "system"]
        self._wm.messages = system_msgs
        self._wm.active_goals.clear()
        self._wm.tool_chain.clear()
        self._wm.temp_vars.clear()
        self._wm.session_start = datetime.now()
        return segment_id

    def get_store_stats(self) -> dict[str, Any]:
        """获取存储统计"""
        return self._store.get_stats()

    def close(self) -> None:
        """关闭记忆管理器"""
        self._store.close()
