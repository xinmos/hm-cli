from typing import Callable, Dict, List, Optional

from hermes.skills.registry import SkillRegistry, Skill

__all__ = ["SkillRegistry", "Skill", "get_registry"]

_registry: Optional[SkillRegistry] = None


def get_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry
