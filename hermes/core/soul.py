from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter


@dataclass
class SoulIdentity:
    """Agent 身份定义"""

    name: str
    persona: str
    voice: str
    principles: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    memory_prompt: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_system_prompt(self) -> str:
        """生成系统提示词"""
        lines = [
            f"# 身份: {self.name}",
            "",
            "## 人格",
            self.persona,
            "",
            "## 说话方式",
            self.voice,
            "",
        ]

        if self.principles:
            lines.extend(["## 行为准则", ""])
            for p in self.principles:
                lines.append(f"- {p}")
            lines.append("")

        if self.skills:
            lines.extend(["## 专长", ""])
            for s in self.skills:
                lines.append(f"- {s}")
            lines.append("")

        if self.memory_prompt:
            lines.extend(["## 记忆", "", self.memory_prompt, ""])

        return "\n".join(lines)


class SoulLoader:
    """从文件系统加载 soul 定义"""

    SOUL_EXTENSIONS = {".md", ".soul.md", ".soul"}

    def __init__(self, souls_dir: Path):
        self._souls_dir = souls_dir
        self._cache: dict[str, SoulIdentity] = {}

    def load(self, name: str) -> SoulIdentity | None:
        """加载指定 soul"""
        if name in self._cache:
            return self._cache[name]

        soul_file = self._find_soul_file(name)
        if not soul_file:
            return None

        soul = self._parse_soul_file(soul_file)
        if soul:
            self._cache[name] = soul
        return soul

    def list_souls(self) -> list[str]:
        """列出所有可用 soul"""
        souls: list[str] = []
        if not self._souls_dir.exists():
            return souls

        for path in self._souls_dir.iterdir():
            if path.suffix in self.SOUL_EXTENSIONS or path.name.endswith(".soul.md"):
                name = path.stem
                if name.endswith(".soul"):
                    name = name[:-5]
                souls.append(name)

        return sorted(souls)

    def clear_cache(self) -> None:
        """清除缓存"""
        self._cache.clear()

    def _find_soul_file(self, name: str) -> Path | None:
        """查找 soul 文件"""
        if not self._souls_dir.exists():
            return None

        candidates = [
            self._souls_dir / f"{name}.md",
            self._souls_dir / f"{name}.soul.md",
            self._souls_dir / f"{name}.soul",
        ]

        for path in candidates:
            if path.exists():
                return path

        return None

    def _parse_soul_file(self, path: Path) -> SoulIdentity | None:
        """解析 soul 文件"""
        try:
            post = frontmatter.load(path)

            name = post.get("name", path.stem)
            if name.endswith(".soul"):
                name = name[:-5]

            persona = post.get("persona", post.get("description", ""))
            voice = post.get("voice", post.get("tone", "专业、简洁、直接"))

            principles = post.get("principles", [])
            if isinstance(principles, str):
                principles = [p.strip() for p in principles.split("\n") if p.strip()]

            skills = post.get("skills", [])
            if isinstance(skills, str):
                skills = [s.strip() for s in skills.split("\n") if s.strip()]

            memory_prompt = post.get("memory", "")

            return SoulIdentity(
                name=name,
                persona=persona,
                voice=voice,
                principles=principles,
                skills=skills,
                memory_prompt=memory_prompt,
                metadata=dict(post.metadata),
            )
        except Exception:
            return None


def get_default_souls_dir() -> Path:
    """获取默认 soul 目录"""
    from hermes.app.settings import Settings

    workdir = Settings.workdir if hasattr(Settings, "workdir") else Path(".").resolve()
    return workdir / ".hermes" / "souls"
