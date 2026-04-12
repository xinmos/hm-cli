from __future__ import annotations

from langchain_core.tools import tool

from hermes.skills import get_registry


@tool
def load_skill(skill_name: str) -> str:
    """Load full instructions for a skill.

    Args:
        skill_name: Name of the skill to load (e.g., "weather-assistant")

    Returns:
        The skill's instructions, or error message
    """
    registry = get_registry()
    skill = registry.get(skill_name)

    if not skill:
        available = [s.name for s in registry.list_skills()]
        return f"Skill '{skill_name}' not found. Available: {available}"

    instructions = registry.load_skill_instructions(skill_name)
    if not instructions:
        return f"Skill '{skill_name}' has no instructions."

    return instructions
