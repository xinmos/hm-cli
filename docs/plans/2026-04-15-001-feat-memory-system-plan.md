---
title: 实现记忆系统 (Memory System)
type: feat
status: active
date: 2026-04-15
---

# 记忆系统实现计划

## 概述

为 Hermes CLI 实现一个分层记忆系统，使 Agent 能够跨会话保持上下文、学习用户偏好、并从历史交互中检索相关信息。

## 背景与动机

当前 `AgentSession` 仅维护内存中的消息列表，会话结束后所有上下文丢失。用户需要重复提供背景信息，Agent 无法学习长期偏好。记忆系统将解决：

1. **上下文延续** - 跨会话保持对话连贯性
2. **个性化** - 学习并应用用户偏好
3. **知识累积** - 从交互中提取并复用知识

## 技术方案

### 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                        AgentSession                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  WorkingMemory                          │   │
│  │  - 当前对话历史 (messages)                              │   │
│  │  - 活跃任务目标                                          │   │
│  │  - 注意力权重管理                                        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MemoryManager                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  EpisodicMemory │  │ SemanticMemory  │  │  MemoryStore    │ │
│  │  - 事件日志      │  │  - 知识图谱      │  │  - 统一存储接口  │ │
│  │  - 向量索引      │  │  - 规则引擎      │  │  - SQLite/JSON  │ │
│  │  - 时间索引      │  │  - 实体关系      │  │  - 可选:向量DB  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 核心组件

#### 1. WorkingMemory (工作记忆)

**职责**: 管理当前会话的短期状态

**核心数据结构**:

```python
@dataclass
class WorkingMemory:
    """工作记忆 - 当前会话状态"""
    messages: list[Message]                    # 对话历史
    active_goals: list[Goal]                   # 活跃目标
    attention_weights: dict[str, float]        # 注意力权重
    tool_chain: list[ToolExecution]            # 工具执行链
    temp_vars: dict[str, Any]                  # 临时变量
    session_start: datetime                    # 会话开始时间
    last_activity: datetime                    # 最后活动时间

@dataclass
class Goal:
    """目标定义"""
    id: str
    description: str
    priority: int                               # 1-10
    status: GoalStatus                          # active, completed, failed
    parent_id: str | None                       # 父目标ID
    created_at: datetime
    deadline: datetime | None
```

**关键方法**:

```python
class WorkingMemoryManager:
    def update_attention(self, query: str) -> None:
        """基于查询更新注意力权重"""
        
    def get_context_window(self, max_tokens: int) -> list[Message]:
        """获取适合上下文窗口的消息列表"""
        
    def add_goal(self, goal: Goal) -> None:
        """添加新目标"""
        
    def complete_goal(self, goal_id: str) -> None:
        """完成目标"""
```

#### 2. EpisodicMemory (情景记忆)

**职责**: 存储和检索具体交互事件

**核心数据结构**:

```python
@dataclass
class Episode:
    """情景记忆单元"""
    id: str                                      # 唯一ID
    timestamp: datetime                          # 发生时间
    event_type: EventType                        # 事件类型
    session_id: str                              # 所属会话
    summary: str                                 # 摘要
    raw_data: dict[str, Any]                     # 原始数据
    entities: list[EntityRef]                    # 关联实体
    importance: int                              # 重要性 1-10
    retention_score: float                       # 保留分数 (遗忘曲线)
    vector_embedding: list[float] | None         # 向量嵌入
    tags: list[str]                              # 标签

@dataclass
class EntityRef:
    """实体引用"""
    entity_type: str                             # user, file, tool, etc.
    entity_id: str                               # 实体标识
    name: str                                    # 显示名称

class EventType(Enum):
    """事件类型"""
    USER_MESSAGE = "user_message"                # 用户消息
    ASSISTANT_RESPONSE = "assistant_response"  # 助手回复
    TOOL_EXECUTION = "tool_execution"          # 工具执行
    GOAL_CREATED = "goal_created"              # 目标创建
    GOAL_COMPLETED = "goal_completed"          # 目标完成
    ERROR_OCCURRED = "error_occurred"          # 错误发生
    USER_PREFERENCE = "user_preference"        # 用户偏好表达
    SESSION_START = "session_start"            # 会话开始
    SESSION_END = "session_end"                # 会话结束
```

**存储实现**:

```python
class EpisodicStore:
    """情景记忆存储"""
    
    def __init__(self, db_path: Path, vector_store: VectorStore | None = None):
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
                    raw_data TEXT,  -- JSON
                    entities TEXT,  -- JSON
                    importance INTEGER DEFAULT 5,
                    retention_score REAL DEFAULT 1.0,
                    tags TEXT,  -- JSON
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
            
    def append(self, episode: Episode) -> None:
        """追加情景记录"""
        
    def query_by_time(self, start: datetime, end: datetime) -> list[Episode]:
        """按时间范围查询"""
        
    def query_by_similarity(self, query: str, top_k: int = 5) -> list[Episode]:
        """按语义相似度查询"""
```

#### 3. SemanticMemory (语义记忆)

**职责**: 存储抽象知识和规则

**核心数据结构**:

```python
@dataclass
class KnowledgeNode:
    """知识图谱节点"""
    id: str
    entity_type: str                           # concept, rule, preference, etc.
    name: str
    attributes: dict[str, Any]                # 属性字典
    confidence: float                          # 置信度 0-1
    source_episodes: list[str]                # 来源情景ID
    created_at: datetime
    updated_at: datetime
    version: int                               # 版本号

@dataclass
class KnowledgeEdge:
    """知识图谱关系"""
    id: str
    source_id: str
    target_id: str
    relation_type: str                         # is_a, has_a, related_to, etc.
    attributes: dict[str, Any]
    confidence: float
    source_episodes: list[str]

@dataclass
class Rule:
    """规则定义"""
    id: str
    name: str
    condition: str                           # 条件表达式
    action: str                              # 动作描述
    priority: int                             # 优先级
    enabled: bool
    success_count: int                        # 成功应用次数
    fail_count: int                           # 失败次数
    source_episodes: list[str]
    created_at: datetime
    updated_at: datetime
```

**存储实现**:

```python
class SemanticStore:
    """语义记忆存储"""
    
    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._init_schema()
        
    def _init_schema(self) -> None:
        """初始化知识图谱结构"""
        with sqlite3.connect(self._db_path) as conn:
            # 知识节点表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_nodes (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    attributes TEXT,  -- JSON
                    confidence REAL DEFAULT 0.5,
                    source_episodes TEXT,  -- JSON array
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    version INTEGER DEFAULT 1
                )
            """)
            
            # 关系边表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_edges (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    attributes TEXT,  -- JSON
                    confidence REAL DEFAULT 0.5,
                    source_episodes TEXT,  -- JSON array
                    FOREIGN KEY (source_id) REFERENCES knowledge_nodes(id),
                    FOREIGN KEY (target_id) REFERENCES knowledge_nodes(id)
                )
            """)
            
            # 规则表
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
                    source_episodes TEXT,  -- JSON array
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
```

#### 4. MemoryManager (记忆管理器)

**职责**: 协调各记忆层，提供统一接口

```python
class MemoryManager:
    """记忆管理器 - 统一协调各记忆层"""
    
    def __init__(
        self,
        working_memory: WorkingMemory,
        episodic_store: EpisodicStore,
        semantic_store: SemanticStore,
        config: MemoryConfig,
    ):
        self._wm = working_memory
        self._episodic = episodic_store
        self._semantic = semantic_store
        self._config = config
        self._importance_classifier = ImportanceClassifier()
        self._reflection_engine = ReflectionEngine(semantic_store)
        
    async def process_interaction(
        self,
        user_input: str,
        agent_response: str,
        tool_executions: list[ToolExecution],
    ) -> None:
        """处理交互并触发记忆形成"""
        
        # 1. 记录到工作记忆
        self._wm.messages.append(Message(role="user", content=user_input))
        self._wm.messages.append(Message(role="assistant", content=agent_response))
        
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
                "tool_executions": [t.to_dict() for t in tool_executions],
            },
            entities=self._extract_entities(user_input, agent_response),
            importance=self._calculate_importance(user_input, agent_response, tool_executions),
            retention_score=1.0,
            tags=self._extract_tags(user_input),
        )
        
        # 3. 评估重要性并存储
        if self._should_store_episode(episode):
            await self._episodic.append(episode)
            
            # 4. 触发语义提取
            await self._extract_semantic_knowledge(episode)
            
            # 5. 检测负面情绪触发反思
            if self._detect_negative_signal(user_input, agent_response):
                await self._reflection_engine.reflect(episode)
    
    async def retrieve_relevant_context(
        self,
        query: str,
        current_messages: list[Message],
        max_tokens: int = 4000,
    ) -> RetrievedContext:
        """检索相关上下文"""
        
        # 1. 理解查询意图
        query_understanding = self._understand_query(query, current_messages)
        
        # 2. 并行检索三个通道
        semantic_results = await self._semantic.search(
            query=query_understanding.intent,
            entity_types=query_understanding.entity_types,
            top_k=5,
        )
        
        episodic_results = await self._episodic.query_by_similarity(
            query=query,
            top_k=5,
            time_range=query_understanding.time_range,
        )
        
        working_results = self._wm.get_high_attention_fragments(
            query=query,
            top_k=3,
        )
        
        # 3. 融合排序
        fused_results = self._fuse_results(
            semantic=semantic_results,
            episodic=episodic_results,
            working=working_results,
            query_weights=query_understanding.source_weights,
        )
        
        # 4. 格式化为上下文
        return self._format_context(fused_results, max_tokens)
    
    async def compress_memory(self, strategy: CompressionStrategy) -> CompressionResult:
        """执行记忆压缩"""
        
        if strategy == CompressionStrategy.FLUSH:
            # 冲刷：创建检查点
            return await self._flush_to_disk()
            
        elif strategy == CompressionStrategy.PRUNE:
            # 裁剪：移除低权重工具结果
            return await self._prune_working_memory()
            
        elif strategy == CompressionStrategy.SUMMARIZE:
            # 摘要：为旧情景生成摘要
            return await self._summarize_episodes()
            
        elif strategy == CompressionStrategy.SEGMENT:
            # 分段：会话分段
            return await self._segment_session()
```

### 数据流

```
交互输入
    │
    ▼
┌─────────────────┐
│  WorkingMemory  │ ◄──── 更新当前状态
│  (当前会话)      │
└─────────────────┘
    │
    ▼
┌─────────────────┐     重要性评估
│ Importance      │ ──► 是否重要?
│ Classifier      │
└─────────────────┘
    │ 是
    ▼
┌─────────────────┐
│ EpisodicMemory  │ ◄──── 追加事件记录
│ (事件日志)       │
└─────────────────┘
    │
    ├───► 语义提取 ──► SemanticMemory (知识)
    │
    └───► 负面情绪? ──► ReflectionEngine (反思)
```

## 文件结构

```
hermes/
├── core/
│   ├── memory/                           # 记忆系统核心
│   │   ├── __init__.py
│   │   ├── working_memory.py             # 工作记忆
│   │   ├── episodic_memory.py            # 情景记忆
│   │   ├── semantic_memory.py             # 语义记忆
│   │   ├── memory_manager.py             # 记忆管理器
│   │   ├── importance_classifier.py      # 重要性评估
│   │   ├── reflection_engine.py          # 反思引擎
│   │   ├── retrieval_engine.py           # 检索引擎
│   │   ├── compression.py                # 压缩策略
│   │   └── models.py                     # 数据模型
│   │
│   └── agent.py                          # 集成记忆系统
│
├── infra/
│   └── persistence/
│       ├── memory_stores.py              # 记忆存储实现
│       └── vector_store.py               # 向量存储(可选)
│
└── prompts/
    └── memory_prompts.py                 # 记忆相关提示词
```

## 实现阶段

### Phase 1: 核心模型与存储 (2-3 天)

1. **数据模型定义** (`hermes/core/memory/models.py`)
   - `Episode`, `KnowledgeNode`, `KnowledgeEdge`, `Rule`
   - `WorkingMemory`, `Goal`, `Message`
   - 所有模型的序列化/反序列化

2. **存储层实现** (`hermes/infra/persistence/memory_stores.py`)
   - `EpisodicStore`: SQLite 存储 + 索引
   - `SemanticStore`: 知识图谱 + 规则存储
   - `MemoryStore`: 统一接口

3. **工作记忆** (`hermes/core/memory/working_memory.py`)
   - `WorkingMemory` 类
   - 注意力权重管理
   - 目标追踪

### Phase 2: 记忆形成 (2-3 天)

1. **重要性评估** (`hermes/core/memory/importance_classifier.py`)
   - 基于规则的快速分类
   - LLM 辅助的精细评估
   - 负面情绪检测

2. **语义提取** (集成到 `memory_manager.py`)
   - 实体识别
   - 关系抽取
   - 规则归纳

3. **反思引擎** (`hermes/core/memory/reflection_engine.py`)
   - 错误分析
   - 规则生成
   - 知识修正

### Phase 3: 检索与融合 (2-3 天)

1. **检索引擎** (`hermes/core/memory/retrieval_engine.py`)
   - 查询理解
   - 多源检索 (语义 + 情景 + 工作记忆)
   - 结果融合排序

2. **上下文格式化** (集成到 `memory_manager.py`)
   - 检索结果转自然语言
   - 置信度标注
   - 溯源链接

3. **向量检索** (可选) (`hermes/infra/persistence/vector_store.py`)
   - 嵌入生成
   - 相似度检索

### Phase 4: 压缩与维护 (1-2 天)

1. **压缩策略** (`hermes/core/memory/compression.py`)
   - Flush: 检查点创建
   - Prune: 工作记忆裁剪
   - Summarize: 情景摘要
   - Segment: 会话分段

2. **遗忘曲线** (集成到 `episodic_memory.py`)
   - 保留分数衰减
   - 检索时惩罚
   - 显式强化

3. **记忆自纠错** (集成到 `semantic_memory.py`)
   - 冲突检测
   - 知识更新
   - 历史保留

### Phase 5: 集成与测试 (2-3 天)

1. **Agent 集成** (`hermes/core/agent.py`)
   - 注入 MemoryManager
   - 消息流转
   - 上下文注入

2. **系统提示集成** (`hermes/prompts/memory_prompts.py`)
   - 记忆使用提示
   - 检索指导

3. **测试**
   - 单元测试 (各组件)
   - 集成测试 (完整流程)
   - 性能测试 (检索速度)

## 关键决策

### 1. 存储选型

- **SQLite**: 主要存储，支持 ACID，无需外部依赖
- **JSON 文件**: 可选回退，便于人工查看
- **向量数据库**: 可选 (如需要高性能语义检索)

### 2. 嵌入模型

- 默认使用 OpenAI API (text-embedding-3-small)
- 可选本地模型 (如 ollama 的 nomic-embed-text)
- 支持无嵌入的精确匹配检索

### 3. 检索策略

- **默认**: 混合检索 (语义 + 关键词 + 时间)
- **工作记忆**: 高注意力权重优先
- **情景记忆**: 时间衰减 + 相似度排序
- **语义记忆**: 精确匹配优先

### 4. 隐私与安全

- 敏感信息 (密码、token) 检测与屏蔽
- 本地存储，不上传云端
- 可选加密存储

## 文件清单

### Phase 1 文件

| 文件 | 描述 | 行数预估 |
|------|------|----------|
| `hermes/core/memory/models.py` | 数据模型定义 | ~300 |
| `hermes/core/memory/working_memory.py` | 工作记忆 | ~250 |
| `hermes/infra/persistence/memory_stores.py` | 存储实现 | ~400 |

### Phase 2 文件

| 文件 | 描述 | 行数预估 |
|------|------|----------|
| `hermes/core/memory/importance_classifier.py` | 重要性评估 | ~150 |
| `hermes/core/memory/reflection_engine.py` | 反思引擎 | ~200 |

### Phase 3 文件

| 文件 | 描述 | 行数预估 |
|------|------|----------|
| `hermes/core/memory/retrieval_engine.py` | 检索引擎 | ~300 |
| `hermes/infra/persistence/vector_store.py` | 向量存储 | ~150 |

### Phase 4 文件

| 文件 | 描述 | 行数预估 |
|------|------|----------|
| `hermes/core/memory/compression.py` | 压缩策略 | ~200 |

### Phase 5 文件

| 文件 | 描述 | 行数预估 |
|------|------|----------|
| `hermes/core/memory/__init__.py` | 模块导出 | ~50 |
| `hermes/core/memory/memory_manager.py` | 记忆管理器 | ~300 |
| `hermes/prompts/memory_prompts.py` | 记忆提示 | ~100 |
| `tests/memory/` | 测试目录 | ~500 |

**总计**: ~4200 行

## 验收标准

### 功能标准

- [ ] 工作记忆正确维护对话历史和目标
- [ ] 重要事件自动记录到情景记忆
- [ ] 用户偏好正确提取到语义记忆
- [ ] 检索能返回相关历史信息
- [ ] 上下文正确注入到系统提示
- [ ] 会话压缩不丢失关键信息
- [ ] 记忆自纠错能更新错误知识

### 性能标准

- [ ] 记忆写入延迟 < 100ms
- [ ] 检索响应时间 < 500ms
- [ ] 支持 10K+ 情景记录
- [ ] 内存占用 < 200MB (不含嵌入)

### 质量标凅

- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试覆盖主要流程
- [ ] 代码通过类型检查
- [ ] 文档完整 (模块、类、方法)

## 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 检索质量差 | 中 | 高 | 混合检索 + 重排序 + 反馈调优 |
| 存储膨胀 | 中 | 中 | 压缩策略 + 定期清理 + 归档 |
| 隐私泄露 | 低 | 高 | 敏感信息检测 + 加密 + 访问控制 |
| 性能下降 | 中 | 中 | 索引优化 + 缓存 + 异步处理 |

## 后续迭代

1. **V1.1** - 多模态记忆 (支持文件、图片引用)
2. **V1.2** - 分布式记忆 (跨设备同步)
3. **V1.3** - 主动回忆 (Agent 主动提醒相关信息)
4. **V2.0** - 终身学习 (从所有交互中持续学习)

## 来源与参考

### 设计参考

- **论文**: "Augmenting Language Models with Long-Term Memory" (Zhong et al., 2023)
- **论文**: "MemoryBank: Enhancing Large Language Models with Long-Term Memory" (Wu et al., 2023)
- **设计**: MemGPT 的分层记忆架构
- **设计**: LangChain Memory 模块的接口设计

### 技术参考

- **SQLite**: https://www.sqlite.org/docs.html
- **向量检索**: faiss, annoy, or sqlite-vec
- **嵌入模型**: OpenAI text-embedding-3-small

### 内部参考

- `hermes/core/agent.py` - Agent 会话实现
- `hermes/core/soul.py` - Soul 身份系统
- `hermes/app/bootstrap.py` - 应用启动流程
