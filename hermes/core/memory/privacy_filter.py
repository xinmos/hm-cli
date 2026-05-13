from __future__ import annotations

import re

from hermes.core.memory.models import Episode

PRIVACY_PATTERNS: list[tuple[str, str]] = [
    (r'sk-[A-Za-z0-9]{32,}', '[OPENAI_API_KEY_REDACTED]'),
    (r'sk-ant-[A-Za-z0-9_-]{20,}', '[ANTHROPIC_API_KEY_REDACTED]'),
    (r'AKIA[0-9A-Z]{16}', '[AWS_ACCESS_KEY_REDACTED]'),
    (r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer [TOKEN_REDACTED]'),
    (r'api_key\s*[:=]\s*[^\s,\'"]+', 'api_key=[REDACTED]'),
    (r'password\s*[:=]\s*[^\s,\'"]+', 'password=[REDACTED]'),
    (r'secret\s*[:=]\s*[^\s,\'"]+', 'secret=[REDACTED]'),
    (r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----[^-]*-----END\s+(?:RSA\s+)?PRIVATE\s+KEY-----', '[PRIVATE_KEY_REDACTED]'),
    (r'(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}', '[GITHUB_TOKEN_REDACTED]'),
]


def filter_text(text: str) -> str:
    """Strip sensitive data from a text string."""
    for pattern, replacement in PRIVACY_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


def filter_episode(episode: Episode) -> Episode:
    """Strip sensitive data from an episode in place."""
    episode.summary = filter_text(episode.summary)

    if "user_input" in episode.raw_data and isinstance(episode.raw_data["user_input"], str):
        episode.raw_data["user_input"] = filter_text(episode.raw_data["user_input"])
    if "agent_response" in episode.raw_data and isinstance(episode.raw_data["agent_response"], str):
        episode.raw_data["agent_response"] = filter_text(episode.raw_data["agent_response"])

    for entity in episode.entities:
        entity.name = filter_text(entity.name)

    return episode
