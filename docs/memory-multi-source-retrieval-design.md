# 记忆系统多源检索与结果融合机制设计

## 目录

1. [背景与目标](#背景与目标)
2. [查询理解 (Query Understanding)](#查询理解-query-understanding)
3. [多源检索策略](#多源检索策略)
4. [结果融合与排序](#结果融合与排序)
5. [结果呈现](#结果呈现)
6. [完整检索流程](#完整检索流程)
7. [实现路线图](#实现路线图)

---

## 背景与目标

### 当前架构

基于代码库分析，当前记忆系统已实现以下组件：

| 记忆类型 | 存储方式 | 检索方式 | 状态 |
|---------|---------|---------|------|
| 工作记忆 (WorkingMemory) | 内存列表 + SQLite | 注意力权重排序 | 已实现 |
| 情景记忆 (EpisodicMemory) | SQLite + 可选向量 | 时间范围 + 相似度 | 已实现 |
| 语义记忆 (SemanticMemory) | SQLite | 概念匹配 | 部分实现 |

### 核心挑战

1. **查询理解不足**: 缺乏对用户意图（事实查找/方法寻找/操作重现）的识别
2. **检索孤立**: 各记忆源独立检索，缺乏协同
3. **结果融合缺失**: 没有统一的排序和去重机制
4. **时间理解薄弱**: "昨天"、"上次"等时间表达未解析

### 设计目标

- 支持三种查询意图的自动识别
- 实现三源协同检索 (工作 + 情景 + 语义)
- 建立相关性、时效性、权威性综合排序机制
- 提供可解释的结果溯源

---

## 查询理解 (Query Understanding)

### 1. 意图识别

#### 查询意图分类

| 意图类型 | 描述 | 典型关键词 | 示例 |
|---------|------|-----------|------|
| 事实查找 (FactLookup) | 检索具体信息 | 密码、配置、值、地址 | "数据库密码是什么" |
| 方法寻找 (MethodSeeking) | 查找解决方案 | 怎么、如何、解决、步骤 | "怎么解决连接问题" |
| 操作重现 (ActionReplay) | 重复执行历史操作 | 再、重复、重新、执行 | "再执行一遍清理脚本" |

#### 实现方案

**方案A: 规则 + 轻量分类器 (推荐)**

```python
from enum import Enum
from typing import List, Tuple
import re

class QueryIntent(Enum):
    FACT_LOOKUP = "fact_lookup"
    METHOD_SEEKING = "method_seeking"
    ACTION_REPLAY = "action_replay"
    UNKNOWN = "unknown"


class IntentPatterns:
    """意图识别规则模式"""

    FACT_KEYWORDS = [
        r"密码|密码是|密钥|token|secret|配置|地址|端口|用户名",
        r"什么|多少|值|状态|版本|路径",
    ]

    METHOD_KEYWORDS = [
        r"怎么|如何|怎样|解决|修复|处理|配置|设置|安装|部署",
        r"步骤|方法|方案|教程|指南|文档",
    ]

    ACTION_KEYWORDS = [
        r"再|再次|重新|重复|执行|运行|发起|调用",
        r"再来|重做|回滚|恢复|还原",
    ]


class IntentClassifier:
    """意图分类器 - 规则 + 置信度"""

    def __init__(self):
        self.patterns = IntentPatterns()
        self._compile_patterns()

    def _compile_patterns(self):
        self.fact_regex = [re.compile(p) for p in self.patterns.FACT_KEYWORDS]
        self.method_regex = [re.compile(p) for p in self.patterns.METHOD_KEYWORDS]
        self.action_regex = [re.compile(p) for p in self.patterns.ACTION_KEYWORDS]

    def classify(self, query: str) -> Tuple[QueryIntent, float]:
        """
        返回意图类型和置信度

        置信度计算：
        - 匹配关键词数量 / 总关键词数
        - 关键词位置权重（句首 > 句中）
        """
        query = query.lower()

        scores = {
            QueryIntent.FACT_LOOKUP: self._calc_score(query, self.fact_regex),
            QueryIntent.METHOD_SEEKING: self._calc_score(query, self.method_regex),
            QueryIntent.ACTION_REPLAY: self._calc_score(query, self.action_regex),
        }

        max_intent = max(scores, key=scores.get)
        max_score = scores[max_intent]

        # 如果最高分数低于阈值，标记为未知
        if max_score < 0.3:
            return QueryIntent.UNKNOWN, 0.0

        return max_intent, max_score

    def _calc_score(self, query: str, patterns: List[re.Pattern]) -> float:
        matches = 0
        for pattern in patterns:
            if pattern.search(query):
                matches += 1
        return matches / len(patterns) if patterns else 0.0
```

**方案B: 小型LLM分类器**

对于更复杂的意图识别，可以使用轻量级模型（如distilbert-base）进行微调：

```python
# 意图识别提示模板（用于LLM-based分类）
INTENT_CLASSIFICATION_PROMPT = """
分析以下用户查询，识别其主要意图类型。

意图类型定义：
1. fact_lookup - 用户想要查找某个具体事实、值、配置、密码等
2. method_seeking - 用户想要知道如何解决某个问题、方法步骤
3. action_replay - 用户想要重复执行之前的某个操作

用户查询: {query}

请用JSON格式输出：
{{
    "intent": "fact_lookup|method_seeking|action_replay|unknown",
    "confidence": 0.0-1.0,
    "reasoning": "简要解释"
}}
"""
```

### 2. 实体提取

#### 实体类型定义

| 实体类型 | 描述 | 示例 |
|---------|------|------|
| PERSON | 人名 | "张三"、"李四" |
| FILE | 文件名/路径 | "config.json"、"/etc/nginx/nginx.conf" |
| COMMAND | 命令/工具名 | "grep"、"kubectl"、"python" |
| PARAMETER | 参数名 | "--port"、"-c"、"database_url" |
| URL | 网址 | "https://example.com" |
| TIME | 时间点/时间段 | "昨天"、"3点"、"上周" |
| VALUE | 值/数据 | "3306"、"admin"、"127.0.0.1" |

#### 实现方案

```python
from dataclasses import dataclass
from typing import List, Optional
import re


@dataclass
class Entity:
    """提取的实体"""
    type: str
    value: str
    start: int
    end: int
    normalized: Optional[str] = None
    confidence: float = 1.0


class EntityExtractor:
    """基于规则的实体提取器"""

    # 文件扩展名模式
    FILE_EXTENSIONS = r'\.(py|js|ts|json|yaml|yml|toml|md|txt|log|conf|config|sh|bash|zsh|sql|dockerfile|env|ini|xml|csv|tsv|gitignore)'

    # 参数模式
    PARAMETER_PATTERNS = [
        r'--[a-zA-Z0-9-]+[=\s]?',  # --option, --option=value
        r'-[a-zA-Z0-9][\s=]?',     # -a, -a value, -a=value
    ]

    # URL 模式
    URL_PATTERN = r'https?://[^\s\)\]\}<>"\']+'

    # 时间模式
    TIME_PATTERNS = {
        'relative': r'(今天|昨天|前天|明天|后天|上周|这周|下周|上个月|这个月|下个月|去年|今年|明年)',
        'duration': r'(\d+\s*[秒分钟小时天周月年])+[前后来]?',
        'clock': r'(\d{1,2})[:点](\d{1,2})?\s*[分时]?',
    }

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        self.file_ext_regex = re.compile(self.FILE_EXTENSIONS, re.IGNORECASE)
        self.url_regex = re.compile(self.URL_PATTERN, re.IGNORECASE)
        self.param_regexes = [re.compile(p, re.IGNORECASE) for p in self.PARAMETER_PATTERNS]
        self.time_regexes = {
            k: re.compile(v, re.IGNORECASE) for k, v in self.TIME_PATTERNS.items()
        }

    def extract(self, text: str) -> List[Entity]:
        """提取文本中的所有实体"""
        entities = []

        entities.extend(self._extract_files(text))
        entities.extend(self._extract_urls(text))
        entities.extend(self._extract_parameters(text))
        entities.extend(self._extract_time(text))
        entities.extend(self._extract_commands(text))
        entities.extend(self._extract_values(text))

        # 按位置排序并处理重叠
        entities = self._resolve_overlaps(entities)

        return entities

    def _extract_files(self, text: str) -> List[Entity]:
        """提取文件名和路径"""
        entities = []

        # 匹配带扩展名的文件
        for match in self.file_ext_regex.finditer(text):
            # 向前查找完整文件名
            start = match.start()
            while start > 0 and text[start - 1] not in ' \t\n\r<>"\'()[]{}':
                start -= 1

            filename = text[start:match.end()]
            entities.append(Entity(
                type="FILE",
                value=filename,
                start=start,
                end=match.end(),
                normalized=filename.strip()
            ))

        return entities

    def _extract_urls(self, text: str) -> List[Entity]:
        """提取URL"""
        entities = []
        for match in self.url_regex.finditer(text):
            entities.append(Entity(
                type="URL",
                value=match.group(),
                start=match.start(),
                end=match.end()
            ))
        return entities

    def _extract_parameters(self, text: str) -> List[Entity]:
        """提取参数"""
        entities = []
        seen = set()

        for regex in self.param_regexes:
            for match in regex.finditer(text):
                value = match.group().strip()
                if value not in seen:
                    seen.add(value)
                    entities.append(Entity(
                        type="PARAMETER",
                        value=value,
                        start=match.start(),
                        end=match.end()
                    ))
        return entities

    def _extract_time(self, text: str) -> List[Entity]:
        """提取时间表达"""
        entities = []

        for time_type, regex in self.time_regexes.items():
            for match in regex.finditer(text):
                entities.append(Entity(
                    type="TIME",
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    normalized=self._normalize_time(match.group(), time_type)
                ))
        return entities

    def _normalize_time(self, time_str: str, time_type: str) -> str:
        """将时间表达归一化为具体的时间区间"""
        from datetime import datetime, timedelta

        now = datetime.now()

        if time_type == 'relative':
            mapping = {
                '今天': (now.replace(hour=0, minute=0, second=0),
                        now.replace(hour=23, minute=59, second=59)),
                '昨天': (now - timedelta(days=1)).replace(hour=0, minute=0, second=0),
                        (now - timedelta(days=1)).replace(hour=23, minute=59, second=59)),
                '上周': (now - timedelta(days=now.weekday() + 7)).replace(hour=0, minute=0, second=0),
                        (now - timedelta(days=now.weekday() + 1)).replace(hour=23, minute=59, second=59)),
                # ... 更多映射
            }
            if time_str in mapping:
                start, end = mapping[time_str]
                return f"[{start.isoformat()}, {end.isoformat()}]"

        return time_str

    def _extract_commands(self, text: str) -> List[Entity]:
        """提取命令/工具名"""
        entities = []

        # 常见的命令模式
        command_patterns = [
            r'\b(git|docker|kubectl|helm|npm|pip|curl|wget|ssh|scp|rsync|grep|awk|sed|find|cat|ls|cd|mkdir|rm|cp|mv|python|node|go|ruby|java)\b',
            r'\b(部署|安装|启动|停止|重启|查看|创建|删除|更新|查询|执行|运行)\s*[了过]?\s*(\w+)',
        ]

        for pattern in command_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities.append(Entity(
                    type="COMMAND",
                    value=match.group(1) if len(match.groups()) > 0 else match.group(),
                    start=match.start(),
                    end=match.end()
                ))

        return entities

    def _extract_values(self, text: str) -> List[Entity]:
        """提取数值/数据"""
        entities = []

        # IP地址
        ip_pattern = r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b'
        for match in re.finditer(ip_pattern, text):
            entities.append(Entity(
                type="VALUE",
                value=match.group(),
                start=match.start(),
                end=match.end(),
                normalized=f"IP:{match.group()}"
            ))

        # 端口号 (跟在冒号后面)
        port_pattern = r':(\d{2,5})\b'
        for match in re.finditer(port_pattern, text):
            port = int(match.group(1))
            if 1 <= port <= 65535:
                entities.append(Entity(
                    type="VALUE",
                    value=match.group(1),
                    start=match.start(),
                    end=match.end(),
                    normalized=f"PORT:{port}"
                ))

        return entities

    def _resolve_overlaps(self, entities: List[Entity]) -> List[Entity]:
        """解决实体重叠，优先保留置信度高的"""
        if not entities:
            return []

        # 按位置排序
        sorted_entities = sorted(entities, key=lambda e: (e.start, -e.confidence))

        result = []
        for entity in sorted_entities:
            # 检查是否与已保留的实体重叠
            overlap = False
            for kept in result:
                if not (entity.end <= kept.start or entity.start >= kept.end):
                    overlap = True
                    break

            if not overlap:
                result.append(entity)

        return sorted(result, key=lambda e: e.start)


class QueryUnderstandingResult:
    """查询理解结果"""

    def __init__(self):
        self.raw_query: str = ""
        self.intent: QueryIntent = QueryIntent.UNKNOWN
        self.intent_confidence: float = 0.0
        self.entities: List[Entity] = []
        self.time_range: Optional[Tuple[datetime, datetime]] = None
        self.context_references: List[str] = []  # 指代消解结果

    def to_dict(self) -> dict:
        return {
            "raw_query": self.raw_query,
            "intent": self.intent.value,
            "intent_confidence": self.intent_confidence,
            "entities": [
                {
                    "type": e.type,
                    "value": e.value,
                    "normalized": e.normalized,
                }
                for e in self.entities
            ],
            "time_range": (
                (self.time_range[0].isoformat(), self.time_range[1].isoformat())
                if self.time_range else None
            ),
            "context_references": self.context_references,
        }
```

#### 核心挑战与解决方案

| 挑战 | 解决方案 | 实现要点 |
|-----|---------|---------|
| 意图边界模糊 | 多意图识别 + 置信度 | 允许一个查询同时标记多个意图，按置信度排序 |
| 口语化表达 | 关键词扩展 + 同义词 | 建立同义词词典（"密码"="口令"="密钥"） |
| 上下文依赖 | 会话状态跟踪 | 维护最近的查询历史，用于指代消解 |

#### 评估方式

```python
# 意图识别评估指标

def evaluate_intent_classification(test_cases: List[dict]):
    """
    test_case = {
        "query": "数据库密码是什么",
        "expected_intent": "fact_lookup",
        "expected_entities": ["数据库", "密码"]
    }
    """
    metrics = {
        "intent_accuracy": 0.0,  # 意图识别准确率
        "entity_precision": 0.0,  # 实体精确率
        "entity_recall": 0.0,     # 实体召回率
        "time_resolution_accuracy": 0.0,  # 时间解析准确率
    }
    # ... 计算逻辑
    return metrics
```

---

## 多源检索策略

### 2.1 语义记忆检索

#### 特点
- 存储概念、规则、方法知识
- 结构化程度高，边界清晰
- 更新频率低，相对稳定

#### 检索算法

```python
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class SemanticMemoryEntry:
    """语义记忆条目"""
    id: str
    concept: str
    category: str  # "concept", "rule", "method"
    content: str
    keywords: List[str]
    related_concepts: List[str]
    importance: float  # 0.0 - 1.0


class SemanticMemoryRetriever:
    """语义记忆检索器"""

    def __init__(self, memory_store):
        self.store = memory_store
        self.keyword_index = {}  # 倒排索引

    def retrieve(
        self,
        query: str,
        query_entities: List[Entity],
        intent: QueryIntent,
        top_k: int = 5,
    ) -> List[Dict]:
        """
        语义记忆检索主入口

        策略：
        1. 关键词匹配 (精确匹配 + 模糊匹配)
        2. 概念分类过滤 (根据意图)
        3. 重要性加权排序
        """
        candidates = []

        # 1. 提取查询关键词
        query_keywords = self._extract_keywords(query)
        for entity in query_entities:
            query_keywords.append(entity.value)
            if entity.normalized:
                query_keywords.append(entity.normalized)

        # 2. 基于意图的类别过滤
        target_categories = self._get_categories_by_intent(intent)

        # 3. 倒排索引检索
        for keyword in query_keywords:
            entries = self.keyword_index.get(keyword.lower(), [])
            for entry in entries:
                if entry.category in target_categories:
                    candidates.append(entry)

        # 去重
        seen_ids = set()
        unique_candidates = []
        for c in candidates:
            if c.id not in seen_ids:
                seen_ids.add(c.id)
                unique_candidates.append(c)

        # 4. 计算相关性分数并排序
        results = []
        for entry in unique_candidates:
            score = self._calculate_relevance(
                entry=entry,
                query_keywords=query_keywords,
                intent=intent,
            )
            results.append({
                "entry": entry,
                "score": score,
                "source": "semantic_memory",
            })

        # 按分数降序排序
        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:top_k]

    def _extract_keywords(self, query: str) -> List[str]:
        """提取查询关键词"""
        # 简单的分词 + 停用词过滤
        stopwords = {"的", "是", "在", "有", "和", "与", "或", "怎么", "什么"}
        words = query.lower().split()
        return [w for w in words if w not in stopwords and len(w) > 1]

    def _get_categories_by_intent(self, intent: QueryIntent) -> List[str]:
        """根据意图获取目标类别"""
        mapping = {
            QueryIntent.FACT_LOOKUP: ["concept", "rule"],
            QueryIntent.METHOD_SEEKING: ["method", "rule"],
            QueryIntent.ACTION_REPLAY: ["method"],
            QueryIntent.UNKNOWN: ["concept", "rule", "method"],
        }
        return mapping.get(intent, ["concept", "rule", "method"])

    def _calculate_relevance(
        self,
        entry: SemanticMemoryEntry,
        query_keywords: List[str],
        intent: QueryIntent,
    ) -> float:
        """计算相关性分数"""
        # 关键词匹配分数
        keyword_hits = sum(1 for k in query_keywords if k in entry.keywords)
        keyword_score = keyword_hits / max(len(entry.keywords), len(query_keywords))

        # 重要性加权
        importance_weight = entry.importance

        # 意图匹配加权
        intent_match = 1.0 if self._matches_intent(entry, intent) else 0.5

        # 综合分数
        final_score = (keyword_score * 0.4 + importance_weight * 0.3 + intent_match * 0.3)

        return round(final_score, 4)

    def _matches_intent(self, entry: SemanticMemoryEntry, intent: QueryIntent) -> bool:
        """检查条目是否与意图匹配"""
        if intent == QueryIntent.FACT_LOOKUP:
            return entry.category in ["concept", "rule"]
        elif intent == QueryIntent.METHOD_SEEKING:
            return entry.category in ["method", "rule"]
        elif intent == QueryIntent.ACTION_REPLAY:
            return entry.category == "method"
        return True
```

#### 核心挑战与解决方案

| 挑战 | 解决方案 | 实现要点 |
|-----|---------|---------|
| 概念粒度不一 | 层次化概念组织 | 建立概念层级关系（is-a, has-a），支持上/下位词扩展检索 |
| 规则冲突 | 规则优先级 + 上下文匹配 | 每条规则附加优先级分数，冲突时选优先级高者 |
| 知识更新 | 版本控制 + 热度加权 | 记录知识更新时间和访问频率，新知识和热点知识优先 |

### 2.2 情景记忆检索

#### 特点
- 存储用户交互历史
- 时间敏感，有明确的时序关系
- 向量表示 + 结构化元数据

#### 检索算法

```python
from datetime import datetime, timedelta
from typing import Tuple, Optional
import numpy as np


@dataclass
class EpisodicMemoryEntry:
    """情景记忆条目"""
    id: str
    timestamp: datetime
    content: str
    embedding: np.ndarray
    importance: float
    tags: List[str]
    related_episodes: List[str]
    outcome: Optional[str] = None  # 执行结果：成功/失败


class EpisodicMemoryRetriever:
    """情景记忆检索器"""

    def __init__(
        self,
        vector_store,
        embedding_model,
        temporal_decay_factor: float = 0.95,  # 时间衰减因子
    ):
        self.vector_store = vector_store
        self.embedding_model = embedding_model
        self.temporal_decay_factor = temporal_decay_factor

    def retrieve(
        self,
        query: str,
        query_embedding: np.ndarray,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        intent: QueryIntent = QueryIntent.UNKNOWN,
        top_k: int = 10,
    ) -> List[Dict]:
        """
        情景记忆检索主入口

        策略：
        1. 向量相似度搜索（语义匹配）
        2. 时间范围过滤（如果提供）
        3. 时间衰减加权（越近越重要）
        4. 结果重排序
        """
        # 1. 向量相似度搜索
        candidates = self._vector_search(query_embedding, top_k * 3)

        # 2. 时间范围过滤
        if time_range:
            candidates = [
                c for c in candidates
                if time_range[0] <= c["entry"].timestamp <= time_range[1]
            ]

        # 3. 计算综合分数
        results = []
        now = datetime.now()

        for candidate in candidates:
            entry = candidate["entry"]

            # 基础相似度分数
            similarity_score = candidate["similarity"]

            # 时间衰减分数 (越近越高)
            days_ago = (now - entry.timestamp).total_seconds() / 86400
            temporal_score = self.temporal_decay_factor ** days_ago

            # 重要性加权
            importance_weight = entry.importance

            # 意图匹配加权
            intent_match = self._calculate_intent_match(entry, intent)

            # 结果反馈加权 (成功的操作优先)
            outcome_boost = 1.2 if entry.outcome == "success" else 1.0

            # 综合分数
            final_score = (
                similarity_score * 0.35 +
                temporal_score * 0.25 +
                importance_weight * 0.2 +
                intent_match * 0.1
            ) * outcome_boost

            results.append({
                "entry": entry,
                "score": round(final_score, 4),
                "source": "episodic_memory",
                "components": {
                    "similarity": round(similarity_score, 4),
                    "temporal": round(temporal_score, 4),
                    "importance": importance_weight,
                    "intent_match": round(intent_match, 4),
                }
            })

        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:top_k]

    def _vector_search(
        self,
        query_embedding: np.ndarray,
        top_k: int,
    ) -> List[Dict]:
        """向量相似度搜索"""
        # 使用向量数据库存储的近似最近邻搜索
        results = self.vector_store.similarity_search(
            embedding=query_embedding,
            top_k=top_k,
        )

        return [
            {
                "entry": result["document"],
                "similarity": result["score"],
            }
            for result in results
        ]

    def _calculate_intent_match(
        self,
        entry: EpisodicMemoryEntry,
        intent: QueryIntent,
    ) -> float:
        """计算条目与意图的匹配程度"""
        if intent == QueryIntent.ACTION_REPLAY:
            # 操作重现优先选择有明确操作结果的记录
            if entry.outcome:
                return 1.0
            return 0.5

        elif intent == QueryIntent.FACT_LOOKUP:
            # 事实查找优先选择包含具体值的记录
            if any(tag in ["config", "value", "fact"] for tag in entry.tags):
                return 1.0
            return 0.6

        elif intent == QueryIntent.METHOD_SEEKING:
            # 方法寻找优先选择有成功结果的记录
            if entry.outcome == "success":
                return 1.0
            return 0.7

        return 0.5
```

#### 核心挑战与解决方案

| 挑战 | 解决方案 | 实现要点 |
|-----|---------|---------|
| 时间表达模糊 | 时间归一化 + 区间映射 | "昨天"映射到[昨天00:00, 昨天23:59] |
| 相似度与时间冲突 | 多因子加权 | 语义相似度35% + 时间衰减25% + 重要性20% |
| 结果稀疏 | 语义扩展 + 关联检索 | 使用相关episode作为桥梁，扩展检索范围 |

### 2.3 工作记忆检索

#### 特点
- 当前会话的短期信息
- 注意力机制加权
- 快速访问，无需复杂检索

#### 检索算法

```python
class WorkingMemoryRetriever:
    """工作记忆检索器"""

    def __init__(self, working_memory):
        self.wm = working_memory

    def retrieve(
        self,
        query: str,
        query_entities: List[Entity],
        top_k: int = 5,
    ) -> List[Dict]:
        """
        工作记忆检索

        策略：
        1. 注意力权重排序
        2. 实体匹配增强
        3. 时效性加权
        """
        candidates = []

        for entry in self.wm.get_all_entries():
            # 基础注意力分数
            attention_score = entry.attention_weight

            # 实体匹配分数
            entity_match_score = self._calculate_entity_match(
                entry, query_entities
            )

            # 时效性分数 (越新的记忆分数越高)
            recency_score = self._calculate_recency(entry)

            # 综合分数
            final_score = (
                attention_score * 0.5 +
                entity_match_score * 0.3 +
                recency_score * 0.2
            )

            candidates.append({
                "entry": entry,
                "score": round(final_score, 4),
                "source": "working_memory",
                "components": {
                    "attention": round(attention_score, 4),
                    "entity_match": round(entity_match_score, 4),
                    "recency": round(recency_score, 4),
                }
            })

        # 按分数排序
        candidates.sort(key=lambda x: x["score"], reverse=True)

        return candidates[:top_k]

    def _calculate_entity_match(
        self,
        entry,
        query_entities: List[Entity],
    ) -> float:
        """计算实体匹配分数"""
        if not query_entities:
            return 0.0

        entry_text = entry.content.lower()
        matches = 0

        for entity in query_entities:
            if entity.value.lower() in entry_text:
                matches += 1
            if entity.normalized and entity.normalized.lower() in entry_text:
                matches += 0.5

        return min(matches / len(query_entities), 1.0)

    def _calculate_recency(self, entry) -> float:
        """计算时效性分数"""
        from datetime import datetime

        age = (datetime.now() - entry.timestamp).total_seconds()

        # 指数衰减，半衰期1小时
        import math
        half_life = 3600  # 1小时
        score = math.exp(-age / half_life)

        return round(score, 4)
```

---

## 结果融合与排序

### 3.1 融合架构

```python
from enum import Enum
from typing import List, Dict, Callable


class FusionStrategy(Enum):
    """融合策略"""
    RRF = "rrf"  # Reciprocal Rank Fusion
    SCORE_WEIGHTED = "score_weighted"  # 分数加权
    LINEAR_COMBINATION = "linear"  # 线性组合
    BORDA_COUNT = "borda"  # Borda计数


class ResultFusionEngine:
    """结果融合引擎"""

    def __init__(
        self,
        strategy: FusionStrategy = FusionStrategy.RRF,
        rrf_k: int = 60,
        source_weights: Dict[str, float] = None,
    ):
        self.strategy = strategy
        self.rrf_k = rrf_k  # RRF常数
        self.source_weights = source_weights or {
            "working_memory": 0.3,
            "episodic_memory": 0.4,
            "semantic_memory": 0.3,
        }

    def fuse(
        self,
        working_memory_results: List[Dict],
        episodic_results: List[Dict],
        semantic_results: List[Dict],
        query_intent: QueryIntent,
    ) -> List[Dict]:
        """
        融合多源检索结果

        流程：
        1. 归一化各源分数
        2. 根据策略融合
        3. 去重
        4. 重排序
        """
        # 根据意图调整源权重
        adjusted_weights = self._adjust_weights_by_intent(query_intent)

        # 收集所有结果
        all_sources = {
            "working_memory": working_memory_results,
            "episodic_memory": episodic_results,
            "semantic_memory": semantic_results,
        }

        # 根据策略融合
        if self.strategy == FusionStrategy.RRF:
            fused = self._rrf_fusion(all_sources, adjusted_weights)
        elif self.strategy == FusionStrategy.SCORE_WEIGHTED:
            fused = self._score_weighted_fusion(all_sources, adjusted_weights)
        elif self.strategy == FusionStrategy.BORDA_COUNT:
            fused = self._borda_fusion(all_sources, adjusted_weights)
        else:
            fused = self._linear_fusion(all_sources, adjusted_weights)

        # 去重
        fused = self._deduplicate(fused)

        # 最终排序
        fused.sort(key=lambda x: x["fused_score"], reverse=True)

        return fused

    def _rrf_fusion(
        self,
        sources: Dict[str, List[Dict]],
        weights: Dict[str, float],
    ) -> List[Dict]:
        """
        Reciprocal Rank Fusion (RRF)

        RRF分数 = Σ(1 / (k + rank_i)) * weight_i

        优点：
        - 不需要归一化分数
        - 对异常值鲁棒
        - 支持任意数量的列表
        """
        scores = {}  # id -> { "item": item, "rrf_score": float }

        for source_name, results in sources.items():
            weight = weights.get(source_name, 1.0)

            for rank, result in enumerate(results, start=1):
                item_id = self._get_item_id(result)

                rrf_score = (1.0 / (self.rrf_k + rank)) * weight

                if item_id not in scores:
                    scores[item_id] = {
                        "item": result,
                        "rrf_score": 0.0,
                        "sources": [],
                    }

                scores[item_id]["rrf_score"] += rrf_score
                scores[item_id]["sources"].append(source_name)

        # 转换为列表
        fused = []
        for item_data in scores.values():
            fused.append({
                **item_data["item"],
                "fused_score": item_data["rrf_score"],
                "sources": list(set(item_data["sources"])),
            })

        return fused

    def _score_weighted_fusion(
        self,
        sources: Dict[str, List[Dict]],
        weights: Dict[str, float],
    ) -> List[Dict]:
        """
        分数加权融合

        每源结果需要先进行Min-Max归一化到[0,1]区间

        融合分数 = Σ(normalized_score_i * weight_i)
        """
        # 首先归一化各源分数
        normalized_sources = {}
        for source_name, results in sources.items():
            normalized_sources[source_name] = self._min_max_normalize(results)

        # 加权融合
        scores = {}
        for source_name, results in normalized_sources.items():
            weight = weights.get(source_name, 1.0)

            for result in results:
                item_id = self._get_item_id(result)

                if item_id not in scores:
                    scores[item_id] = {
                        "item": result,
                        "fused_score": 0.0,
                        "sources": [],
                    }

                scores[item_id]["fused_score"] += result["normalized_score"] * weight
                scores[item_id]["sources"].append(source_name)

        return list(scores.values())

    def _min_max_normalize(self, results: List[Dict]) -> List[Dict]:
        """Min-Max归一化到[0,1]区间"""
        if not results:
            return results

        scores = [r.get("score", 0.0) for r in results]
        min_score, max_score = min(scores), max(scores)

        if max_score == min_score:
            return [{**r, "normalized_score": 1.0} for r in results]

        normalized = []
        for result in results:
            score = result.get("score", 0.0)
            norm_score = (score - min_score) / (max_score - min_score)
            normalized.append({
                **result,
                "normalized_score": round(norm_score, 4),
            })

        return normalized

    def _adjust_weights_by_intent(
        self,
        intent: QueryIntent,
    ) -> Dict[str, float]:
        """根据查询意图调整源权重"""
        base_weights = self.source_weights.copy()

        if intent == QueryIntent.FACT_LOOKUP:
            # 事实查找：优先工作记忆，其次是情景记忆
            return {
                "working_memory": 0.5,
                "episodic_memory": 0.3,
                "semantic_memory": 0.2,
            }

        elif intent == QueryIntent.METHOD_SEEKING:
            # 方法寻找：优先语义记忆和情景记忆
            return {
                "working_memory": 0.2,
                "episodic_memory": 0.4,
                "semantic_memory": 0.4,
            }

        elif intent == QueryIntent.ACTION_REPLAY:
            # 操作重现：优先情景记忆
            return {
                "working_memory": 0.2,
                "episodic_memory": 0.6,
                "semantic_memory": 0.2,
            }

        return base_weights

    def _get_item_id(self, result: Dict) -> str:
        """获取结果条目的唯一标识"""
        # 优先使用entry.id
        if "entry" in result and hasattr(result["entry"], "id"):
            return result["entry"].id
        if "id" in result:
            return result["id"]
        # 使用内容哈希作为fallback
        content = result.get("content", str(result))
        import hashlib
        return hashlib.md5(content.encode()).hexdigest()

    def _deduplicate(self, fused: List[Dict]) -> List[Dict]:
        """去重：合并来自不同源的相同条目"""
        seen = {}

        for item in fused:
            item_id = self._get_item_id(item)

            if item_id in seen:
                # 合并来源和分数
                existing = seen[item_id]
                existing["sources"] = list(set(existing.get("sources", []) + item.get("sources", [])))
                existing["fused_score"] = max(existing.get("fused_score", 0), item.get("fused_score", 0))
            else:
                seen[item_id] = item

        return list(seen.values())

    def _borda_fusion(
        self,
        sources: Dict[str, List[Dict]],
        weights: Dict[str, float],
    ) -> List[Dict]:
        """Borda计数融合"""
        scores = {}

        for source_name, results in sources.items():
            weight = weights.get(source_name, 1.0)
            n = len(results)

            for rank, result in enumerate(results, start=1):
                item_id = self._get_item_id(result)
                borda_score = (n - rank) * weight

                if item_id not in scores:
                    scores[item_id] = {
                        "item": result,
                        "fused_score": 0.0,
                        "sources": [],
                    }

                scores[item_id]["fused_score"] += borda_score
                scores[item_id]["sources"].append(source_name)

        return list(scores.values())

    def _linear_fusion(
        self,
        sources: Dict[str, List[Dict]],
        weights: Dict[str, float],
    ) -> List[Dict]:
        """简单线性融合"""
        scores = {}

        for source_name, results in sources.items():
            weight = weights.get(source_name, 1.0)

            for result in results:
                item_id = self._get_item_id(result)
                score = result.get("score", 0.0) * weight

                if item_id not in scores:
                    scores[item_id] = {
                        "item": result,
                        "fused_score": 0.0,
                        "sources": [],
                    }

                scores[item_id]["fused_score"] += score
                scores[item_id]["sources"].append(source_name)

        return list(scores.values())
```

### 3.2 排序优化

#### 重排序 (Reranking)

```python
class Reranker:
    """结果重排序器"""

    def __init__(self, cross_encoder_model=None):
        self.cross_encoder = cross_encoder_model

    def rerank(
        self,
        query: str,
        results: List[Dict],
        top_k: int = 10,
    ) -> List[Dict]:
        """
        使用交叉编码器重排序

        相比双塔模型，交叉编码器可以捕获更精细的query-doc交互
        """
        if not self.cross_encoder or len(results) == 0:
            return results[:top_k]

        # 准备输入
        pairs = [(query, r["entry"].content) for r in results]

        # 批量打分
        scores = self.cross_encoder.predict(pairs)

        # 更新分数
        for i, score in enumerate(scores):
            results[i]["rerank_score"] = float(score)
            # 融合分数：原分数 * 0.4 + 重排分数 * 0.6
            results[i]["final_score"] = (
                results[i].get("fused_score", 0) * 0.4 +
                float(score) * 0.6
            )

        # 按最终分数排序
        results.sort(key=lambda x: x["final_score"], reverse=True)

        return results[:top_k]


class MMRDiversifier:
    """Maximal Marginal Relevance (MMR) 结果多样化"""

    def __init__(self, lambda_param: float = 0.5):
        """
        lambda_param: 相关性 vs 多样性的权衡
        - 1.0 = 只考虑相关性
        - 0.0 = 只考虑多样性
        """
        self.lambda_param = lambda_param

    def diversify(
        self,
        results: List[Dict],
        embeddings: Dict[str, np.ndarray],
        top_k: int = 10,
    ) -> List[Dict]:
        """
        使用MMR算法实现结果多样化

        MMR = argmax_{d_i ∈ R\S} [λ * Sim(d_i, q) - (1-λ) * max_{d_j ∈ S} Sim(d_i, d_j)]
        """
        if not results:
            return []

        selected = []
        remaining = list(range(len(results)))

        while remaining and len(selected) < top_k:
            best_idx = None
            best_mmr_score = -float('inf')

            for idx in remaining:
                result = results[idx]

                # 相关性分数 (归一化)
                relevance = result.get("final_score", 0.0) or result.get("fused_score", 0.0)

                # 与已选结果的相似度 (取最大)
                max_sim_to_selected = 0.0
                if selected:
                    entry = result["entry"]
                    entry_embedding = embeddings.get(entry.id)

                    if entry_embedding is not None:
                        for sel_idx in selected:
                            sel_entry = results[sel_idx]["entry"]
                            sel_embedding = embeddings.get(sel_entry.id)

                            if sel_embedding is not None:
                                sim = self._cosine_similarity(
                                    entry_embedding, sel_embedding
                                )
                                max_sim_to_selected = max(max_sim_to_selected, sim)

                # MMR分数
                mmr_score = (
                    self.lambda_param * relevance -
                    (1 - self.lambda_param) * max_sim_to_selected
                )

                if mmr_score > best_mmr_score:
                    best_mmr_score = mmr_score
                    best_idx = idx

            if best_idx is not None:
                selected.append(best_idx)
                remaining.remove(best_idx)
            else:
                break

        return [results[i] for i in selected]

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """计算余弦相似度"""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
```

---

## 结果呈现

### 4.1 格式化输出

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class RetrievedResult:
    """检索结果"""
    content: str
    source: str  # working_memory / episodic_memory / semantic_memory
    score: float
    confidence: str  # high / medium / low
    timestamp: Optional[datetime] = None
    metadata: Dict = None
    context_links: List[str] = None  # 关联记忆的ID


class ResultPresenter:
    """结果呈现器"""

    CONFIDENCE_THRESHOLD_HIGH = 0.8
    CONFIDENCE_THRESHOLD_MEDIUM = 0.5

    def present(
        self,
        results: List[RetrievedResult],
        query_intent: QueryIntent,
        include_metadata: bool = False,
    ) -> str:
        """
        将检索结果格式化为自然语言输出
        """
        if not results:
            return self._format_no_results(query_intent)

        sections = []

        # 1. 置信度摘要
        sections.append(self._format_confidence_summary(results))

        # 2. 按意图格式化结果
        if query_intent == QueryIntent.FACT_LOOKUP:
            sections.append(self._format_fact_results(results))
        elif query_intent == QueryIntent.METHOD_SEEKING:
            sections.append(self._format_method_results(results))
        elif query_intent == QueryIntent.ACTION_REPLAY:
            sections.append(self._format_action_results(results))
        else:
            sections.append(self._format_generic_results(results))

        # 3. 溯源信息
        if include_metadata:
            sections.append(self._format_sources(results))

        return "\n\n".join(sections)

    def _format_confidence_summary(self, results: List[RetrievedResult]) -> str:
        """格式化置信度摘要"""
        high = sum(1 for r in results if r.confidence == "high")
        medium = sum(1 for r in results if r.confidence == "medium")
        low = len(results) - high - medium

        parts = ["### 检索置信度"]
        if high > 0:
            parts.append(f"- 高置信度: {high}条")
        if medium > 0:
            parts.append(f"- 中等置信度: {medium}条")
        if low > 0:
            parts.append(f"- 低置信度: {low}条")

        return "\n".join(parts)

    def _format_fact_results(self, results: List[RetrievedResult]) -> str:
        """格式化事实查找结果"""
        lines = ["### 找到的相关信息"]

        for i, result in enumerate(results[:5], 1):
            # 提取关键值
            value = self._extract_key_value(result.content)

            confidence_icon = "✓" if result.confidence == "high" else "~" if result.confidence == "medium" else "?"

            lines.append(f"{i}. {confidence_icon} **{value}**")

            if result.timestamp:
                lines.append(f"   记录时间: {result.timestamp.strftime('%Y-%m-%d %H:%M')}")

        return "\n".join(lines)

    def _format_method_results(self, results: List[RetrievedResult]) -> str:
        """格式化方法寻找结果"""
        lines = ["### 解决方案"]

        for i, result in enumerate(results[:3], 1):
            lines.append(f"\n**方案 {i}** (置信度: {result.confidence})")
            lines.append(result.content[:500])  # 截断显示

            if result.metadata and "success_rate" in result.metadata:
                lines.append(f"历史成功率: {result.metadata['success_rate']:.0%}")

        return "\n".join(lines)

    def _format_action_results(self, results: List[RetrievedResult]) -> str:
        """格式化操作重现结果"""
        lines = ["### 历史操作记录"]

        for i, result in enumerate(results[:3], 1):
            lines.append(f"\n**操作 {i}**")

            if result.timestamp:
                lines.append(f"执行时间: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

            lines.append(f"操作内容: {result.content[:300]}")

            if result.metadata:
                if "outcome" in result.metadata:
                    outcome = result.metadata["outcome"]
                    icon = "✓" if outcome == "success" else "✗"
                    lines.append(f"执行结果: {icon} {outcome}")

        return "\n".join(lines)

    def _format_no_results(self, intent: QueryIntent) -> str:
        """格式化无结果情况"""
        messages = {
            QueryIntent.FACT_LOOKUP: "未找到相关信息。请尝试提供更具体的描述，如文件名、时间范围等。",
            QueryIntent.METHOD_SEEKING: "未找到相关解决方案。建议查阅官方文档或尝试其他关键词。",
            QueryIntent.ACTION_REPLAY: "未找到匹配的历史操作记录。请确认操作时间和内容。",
        }
        return messages.get(intent, "未找到相关结果。请尝试其他查询方式。")

    def _extract_key_value(self, content: str) -> str:
        """从内容中提取关键值"""
        # 简单的启发式：提取等号后面、引号里面的内容
        import re

        # 匹配 "key = value" 或 "key: value" 模式
        patterns = [
            r'[:=]\s*["\']?([^"\'\n]{1,50})["\']?',
            r'(?:password|key|token|secret)\s*[:=]\s*["\']?([^"\'\n]{1,50})["\']?',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # 返回前100个字符
        return content[:100] + "..." if len(content) > 100 else content

    def _format_sources(self, results: List[RetrievedResult]) -> str:
        """格式化溯源信息"""
        lines = ["\n### 信息来源"]

        source_counts = {}
        for r in results:
            source_counts[r.source] = source_counts.get(r.source, 0) + 1

        for source, count in source_counts.items():
            source_name = {
                "working_memory": "工作记忆",
                "episodic_memory": "情景记忆",
                "semantic_memory": "语义记忆",
            }.get(source, source)
            lines.append(f"- {source_name}: {count}条")

        return "\n".join(lines)

    def _format_generic_results(self, results: List[RetrievedResult]) -> str:
        """通用格式化"""
        lines = ["### 检索结果"]

        for i, result in enumerate(results[:5], 1):
            lines.append(f"\n{i}. [{result.source}] (置信度: {result.confidence})")
            lines.append(result.content[:300])

        return "\n".join(lines)
```

---

## 完整检索流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         多源记忆检索系统架构                                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              阶段1: 查询理解                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  意图识别    │  │  实体提取    │  │  时间解析    │  │  指代消解    │       │
│  │  Classifier  │  │  NER+Rules   │  │  Temporal    │  │  Coreference │       │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘       │
│           │               │               │               │                 │
│           └───────────────┴───────────────┴───────────────┘                 │
│                              │                                              │
│                              ▼                                              │
│              ┌──────────────────────────────┐                              │
│              │   QueryUnderstandingResult   │                              │
│              │   - intent: FactLookup         │                              │
│              │   - entities: [password, db]   │                              │
│              │   - time_range: [t1, t2]       │                              │
│              └──────────────────────────────┘                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            阶段2: 多源并行检索                                 │
│                                                                             │
│   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│   │   工作记忆检索   │    │   情景记忆检索   │    │   语义记忆检索   │          │
│   │                 │    │                 │    │                 │          │
│   │  输入:          │    │  输入:          │    │  输入:          │          │
│   │  - attention    │    │  - embedding    │    │  - keywords     │          │
│   │  - recency      │    │  - time_range   │    │  - category     │          │
│   │                 │    │                 │    │                 │          │
│   │  算法:          │    │  算法:          │    │  算法:          │          │
│   │  Attention     │    │  Similarity +  │    │  Inverted Index │          │
│   │  + Recency     │    │  Temporal      │    │  + Importance   │          │
│   │                │    │  Decay         │    │                 │          │
│   └────────┬───────┘    └────────┬───────┘    └────────┬───────┘          │
│            │                   │                   │                      │
│            │                   │                   │                      │
│            ▼                   ▼                   ▼                      │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │                    检索结果合并                                    │       │
│   │   - WM: [{entry, score}, ...]                                   │       │
│   │   - EM: [{entry, score, temporal}, ...]                         │       │
│   │   - SM: [{entry, score, importance}, ...]                       │       │
│   └─────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           阶段3: 结果融合与排序                                │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │  1. RRF融合 (Reciprocal Rank Fusion)                            │       │
│   │                                                                 │       │
│   │  RRF_score = Σ(1 / (k + rank_i)) * weight_i                      │       │
│   │                                                                 │       │
│   │  优点: 无需归一化，对异常值鲁棒                                   │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                                    │                                        │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │  2. 去重                                                        │       │
│   │                                                                 │       │
│   │  - 内容相似度 > 0.9 → 视为重复                                  │       │
│   │  - 合并来源列表和分数                                            │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                                    │                                        │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │  3. 重排序 (Reranking)                                          │       │
│   │                                                                 │       │
│   │  a) 交叉编码器重排序                                             │       │
│   │     - 使用 cross-encoder 精确计算 query-doc 相似度                │       │
│   │     - 比 bi-encoder 更精确，但更慢                               │       │
│   │                                                                 │       │
│   │  b) MMR多样化                                                    │       │
│   │     - MMR = argmax[λ*Sim(q,d) - (1-λ)*max Sim(d,d_selected)]      │       │
│   │     - 平衡相关性和多样性                                          │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                                    │                                        │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │  4. 时效性加权 (Temporal Weighting)                             │       │
│   │                                                                 │       │
│   │  score_temporal = score * exp(-λ * age)                         │       │
│   │                                                                 │       │
│   │  λ: 遗忘曲线参数 (默认 0.01，半衰期约70天)                        │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                                    │                                        │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │  最终排序结果                                                   │       │
│   │  [{entry, final_score, source, confidence}, ...]                 │       │
│   └─────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            阶段4: 结果呈现                                     │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │  1. 格式化输出                                                   │       │
│   │                                                                 │       │
│   │  根据意图类型选择不同的展示模板:                                  │       │
│   │                                                                 │       │
│   │  - 事实查找: 提取关键值，简洁呈现                                 │       │
│   │  - 方法寻找: 展示步骤和成功率                                     │       │
│   │  - 操作重现: 展示完整命令和历史上下文                              │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                                    │                                        │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │  2. 置信度评级                                                   │       │
│   │                                                                 │       │
│   │  高 (≥0.8):  结果高度可信，可直接使用                             │       │
│   │  中 (0.5-0.8): 结果有一定可信度，建议验证                          │       │
│   │  低 (<0.5):  结果可信度低，仅供参考                               │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                                    │                                        │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │  3. 溯源链接                                                     │       │
│   │                                                                 │       │
│   │  每个结果附带:                                                   │       │
│   │  - 来源记忆类型 (工作/情景/语义)                                  │       │
│   │  - 原始条目ID (可点击查看完整内容)                                 │       │
│   │  - 相关记忆链接 (上下文关联)                                       │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                                    │                                        │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │  最终输出示例:                                                   │       │
│   │                                                                 │       │
│   │  ### 检索置信度                                                  │       │
│   │  - 高置信度: 2条                                                 │       │
│   │  - 中等置信度: 1条                                               │       │
│   │                                                                 │       │
│   │  ### 找到的相关信息                                              │       │
│   │  1. ✓ **postgres://admin:***@localhost:5432/mydb**               │       │
│   │     记录时间: 2024-01-15 09:30                                    │       │
│   │  2. ✓ **端口: 5432**                                              │       │
│   │     来源: config.json                                             │       │
│   │                                                                 │       │
│   │  ### 信息来源                                                    │       │
│   │  - 工作记忆: 1条                                                  │       │
│   │  - 情景记忆: 2条                                                  │       │
│   └─────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘


## 实现路线图

### 阶段1: 基础架构 (2周)

1. **查询理解模块**
   - 实现意图分类器 (规则版)
   - 实现实体提取器 (基于正则)
   - 实现时间解析器 (相对时间映射)

2. **检索接口标准化**
   - 定义统一的检索结果格式
   - 实现各记忆源的检索接口

### 阶段2: 融合排序 (2周)

1. **RRF融合实现**
   - 实现RRF算法
   - 实现去重逻辑

2. **重排序优化**
   - 集成交叉编码器
   - 实现MMR多样化

### 阶段3: 高级特性 (2周)

1. **指代消解**
   - 实现基础指代消解
   - 集成会话上下文

2. **个性化排序**
   - 收集用户反馈
   - 实现反馈驱动的排序优化

### 阶段4: 评估优化 (持续)

1. **评估体系**
   - 建立评估数据集
   - 实现自动化评估流程

2. **性能优化**
   - 检索性能监控
   - 缓存策略优化

## 附录: 算法复杂度分析

| 组件 | 时间复杂度 | 空间复杂度 | 备注 |
|------|-----------|-----------|------|
| 意图分类 | O(n) | O(1) | n=查询长度 |
| 实体提取 | O(n) | O(e) | e=实体数量 |
| 向量检索 | O(log n) | O(d) | d=向量维度 |
| RRF融合 | O(r * s) | O(r) | r=结果数, s=源数 |
| MMR重排 | O(k * r * d) | O(k) | k=选择数 |

---

**文档版本**: 1.0  
**最后更新**: 2024-01-20  
**作者**: Claude Code
