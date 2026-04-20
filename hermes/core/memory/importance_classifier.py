from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from hermes.core.memory.models import Episode, ToolExecution


@dataclass
class ImportanceScore:
    """重要性评分结果"""

    overall: int  # 1-10 总体重要性
    semantic: int  # 语义重要性
    emotional: int  # 情感重要性
    novelty: int  # 新颖性
    reasons: list[str]  # 评分理由


class ImportanceClassifier:
    """重要性评估器"""

    # 高重要性关键词
    HIGH_IMPORTANCE_KEYWORDS = [
        # 中文
        "重要", "关键", "必须", "记住", "保存", "配置", "设置",
        "密码", "密钥", "token", "api_key", "秘密",
        "偏好", "喜欢", "不喜欢", "总是", "从不",
        "规则", "约定", "规范", "标准",
        # 英文
        "important", "key", "critical", "must", "remember", "save",
        "password", "secret", "token", "api_key",
        "preference", "like", "dislike", "always", "never",
        "rule", "convention", "standard",
    ]

    # 负面情绪关键词（触发反思）
    NEGATIVE_EMOTION_KEYWORDS = [
        "错误", "失败", "bug", "问题", "不对", "不行",
        "error", "fail", "wrong", "incorrect", "not working",
        "抱歉", "对不起", "抱歉", "apologize", "sorry",
        "困惑", "confused", "不理解", "不明白",
    ]

    # 积极确认关键词
    POSITIVE_CONFIRMATION = [
        "正确", "很好", "完美", "正是", "没错",
        "correct", "right", "perfect", "exactly", "yes",
    ]

    def classify(
        self,
        user_input: str,
        agent_response: str,
        tool_executions: list[ToolExecution] | None = None,
    ) -> ImportanceScore:
        """评估重要性"""
        tools = tool_executions or []
        text = f"{user_input} {agent_response}".lower()

        reasons: list[str] = []

        # 语义重要性 (1-10)
        semantic = self._calculate_semantic_importance(text, tools, reasons)

        # 情感重要性 (1-10)
        emotional = self._calculate_emotional_importance(text, reasons)

        # 新颖性 (1-10)
        novelty = self._calculate_novelty(text, reasons)

        # 总体重要性
        overall = self._calculate_overall(semantic, emotional, novelty, tools, reasons)

        return ImportanceScore(
            overall=overall,
            semantic=semantic,
            emotional=emotional,
            novelty=novelty,
            reasons=reasons,
        )

    def classify_episode(self, episode: Episode) -> ImportanceScore:
        """评估情景的重要性"""
        # 从episode中提取信息
        raw_data = episode.raw_data
        user_input = raw_data.get("user_input", "")
        agent_response = raw_data.get("agent_response", "")

        tools = []
        tools_data = raw_data.get("tool_executions", [])
        for tool_data in tools_data:
            tools.append(ToolExecution.from_dict(tool_data))

        return self.classify(user_input, agent_response, tools)

    def detect_negative_signal(
        self, user_input: str, agent_response: str
    ) -> tuple[bool, list[str]]:
        """检测负面情绪信号"""
        text = f"{user_input} {agent_response}".lower()
        reasons: list[str] = []

        for keyword in self.NEGATIVE_EMOTION_KEYWORDS:
            if keyword in text:
                reasons.append(f"检测到负面情绪词: {keyword}")

        # 检测用户纠正
        if any(kw in user_input for kw in self.NEGATIVE_EMOTION_KEYWORDS):
            if any(kw in agent_response for kw in self.POSITIVE_CONFIRMATION):
                reasons.append("用户纠正后被确认")

        return len(reasons) > 0, reasons

    def _calculate_semantic_importance(
        self, text: str, tools: list[ToolExecution], reasons: list[str]
    ) -> int:
        """计算语义重要性"""
        score = 5  # 基础分

        # 检查高重要性关键词
        for keyword in self.HIGH_IMPORTANCE_KEYWORDS:
            if keyword in text:
                score += 1
                if len(reasons) < 3:  # 限制理由数量
                    reasons.append(f"包含重要关键词: {keyword}")
                break

        # 检查是否有工具执行
        if tools:
            score += 1
            if len(reasons) < 3:
                reasons.append(f"涉及{len(tools)}个工具调用")

        # 检查文本长度（信息量大）
        if len(text) > 500:
            score += 1

        return min(10, score)

    def _calculate_emotional_importance(self, text: str, reasons: list[str]) -> int:
        """计算情感重要性"""
        score = 5

        # 检测负面情绪
        negative_count = 0
        for keyword in self.NEGATIVE_EMOTION_KEYWORDS:
            if keyword in text:
                negative_count += 1

        if negative_count > 0:
            score += min(3, negative_count)
            if len(reasons) < 3:
                reasons.append(f"检测到{negative_count}个负面情绪信号")

        # 检测积极确认
        if any(kw in text for kw in self.POSITIVE_CONFIRMATION):
            score += 1

        return min(10, max(1, score))

    def _calculate_novelty(self, text: str, reasons: list[str]) -> int:
        """计算新颖性"""
        # 简化实现：基于特定模式判断
        score = 5

        # 检测到新信息模式
        novelty_patterns = [
            r"第一次",
            r"首次",
            r"新的",
            r"刚",
            r"第一次|first time",
            r"新的|new",
        ]

        for pattern in novelty_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                score += 2
                if len(reasons) < 3:
                    reasons.append("检测到新信息")
                break

        return min(10, score)

    def _calculate_overall(
        self,
        semantic: int,
        emotional: int,
        novelty: int,
        tools: list[ToolExecution],
        reasons: list[str],
    ) -> int:
        """计算总体重要性"""
        # 加权平均
        weights = {"semantic": 0.4, "emotional": 0.3, "novelty": 0.3}

        score = int(
            semantic * weights["semantic"]
            + emotional * weights["emotional"]
            + novelty * weights["novelty"]
        )

        # 工具调用加分
        if tools:
            score = min(10, score + 1)

        return max(1, min(10, score))
