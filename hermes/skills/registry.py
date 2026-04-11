from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any
import inspect
import importlib.util
import sys
from pathlib import Path


@dataclass
class Skill:
    name: str
    description: str
    version: str = "1.0.0"
    tools: List[Callable] = field(default_factory=list)
    system_prompt: Optional[str] = None
    triggers: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.triggers and self.tools:
            self.triggers = [t.__name__ for t in self.tools]


class SkillRegistry:
    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._loaded_modules: Dict[str, Any] = {}

    def register(self, skill: Skill) -> None:
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' already registered")
        self._skills[skill.name] = skill

    def unregister(self, name: str) -> bool:
        if name in self._skills:
            del self._skills[name]
            return True
        return False

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def list_skills(self) -> List[Skill]:
        return list(self._skills.values())

    def load_from_file(self, path: str) -> Skill:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Skill file not found: {path}")

        module_name = f"_skill_{path.stem}_{hash(str(path)) % 10000}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        self._loaded_modules[module_name] = module

        if not hasattr(module, "SKILL"):
            raise ValueError(f"Skill file must define 'SKILL' variable: {path}")

        skill = module.SKILL
        if not isinstance(skill, Skill):
            raise ValueError(f"'SKILL' must be a Skill instance: {path}")

        self.register(skill)
        return skill

    def load_from_directory(self, directory: str) -> List[Skill]:
        directory = Path(directory)
        if not directory.exists():
            return []

        loaded = []
        for file_path in directory.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
            try:
                skill = self.load_from_file(str(file_path))
                loaded.append(skill)
            except Exception as e:
                print(f"Failed to load skill {file_path}: {e}")

        return loaded

    def get_all_tools(self) -> List[Callable]:
        tools = []
        for skill in self._skills.values():
            tools.extend(skill.tools)
        return tools

    def get_system_prompts(self) -> List[str]:
        prompts = []
        for skill in self._skills.values():
            if skill.system_prompt:
                prompts.append(skill.system_prompt)
        return prompts

    def clear(self) -> None:
        self._skills.clear()
        for name in list(self._loaded_modules.keys()):
            if name in sys.modules:
                del sys.modules[name]
        self._loaded_modules.clear()
