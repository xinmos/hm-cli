from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from urllib.request import urlopen

import yaml

from web.backend.models.skill import (
    MarketSkill,
    SkillCreateRequest,
    SkillEnabledUpdate,
    SkillFileResponse,
    SkillInstallRequest,
    SkillMarketSource,
    SkillSummary,
)
from web.backend.services.container import WebServiceContainer
from web.backend.services.exceptions import (
    ConflictError,
    NotFoundError,
    UpstreamServiceError,
    ValidationError,
)

SKILL_MARKET_SOURCES = {
    "claude-code-skills": {
        "name": "claude-code-skills",
        "url": "https://raw.githubusercontent.com/alirezarezvani/claude-skills/main/marketplace.json",
        "fallback_url": "https://raw.githubusercontent.com/alirezarezvani/claude-skills/main/.claude-plugin/marketplace.json",
        "raw_base_url": "https://raw.githubusercontent.com/alirezarezvani/claude-skills/main",
    },
    "daymade-skills": {
        "name": "daymade-skills",
        "url": "https://raw.githubusercontent.com/daymade/claude-code-skills/main/marketplace.json",
        "fallback_url": "https://raw.githubusercontent.com/daymade/claude-code-skills/main/.claude-plugin/marketplace.json",
        "raw_base_url": "https://raw.githubusercontent.com/daymade/claude-code-skills/main",
    },
}


class SkillApiService:
    def __init__(self, services: WebServiceContainer):
        self._services = services

    def list_local_skills(self) -> list[SkillSummary]:
        root = self._skills_root()
        return [self._parse_skill_summary(root, path) for path in self._list_skill_files(root)]

    @classmethod
    def from_static_sources(cls) -> list[SkillMarketSource]:
        return [
            SkillMarketSource(id=source_id, name=source["name"], url=source["url"])
            for source_id, source in SKILL_MARKET_SOURCES.items()
        ]

    def list_market_sources(self) -> list[SkillMarketSource]:
        return self.from_static_sources()

    def list_market_skills(self, source_id: str) -> list[MarketSkill]:
        return self._load_market_skills(source_id)

    def install_market_skill(self, payload: SkillInstallRequest) -> SkillFileResponse:
        root = self._skills_root()
        market_skill = next(
            (skill for skill in self._load_market_skills(payload.source_id) if skill.id == payload.id),
            None,
        )
        if market_skill is None:
            raise NotFoundError("Market skill not found")

        slug = self._slugify_skill_name(market_skill.id)
        skill_dir = root / slug
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            raise ConflictError("Skill already installed")

        skill_dir.mkdir(parents=True, exist_ok=False)
        content = self._normalize_installed_skill_content(
            market_skill,
            self._market_skill_content(market_skill),
        )
        skill_file.write_text(content, encoding="utf-8")
        return SkillFileResponse(skill=self._parse_skill_summary(root, skill_file), content=content)

    def create_local_skill(self, payload: SkillCreateRequest) -> SkillFileResponse:
        root = self._skills_root()
        slug = self._slugify_skill_name(payload.name)
        skill_dir = root / slug
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            raise ConflictError("Skill already exists")

        skill_dir.mkdir(parents=True, exist_ok=False)
        description = payload.description.strip()
        frontmatter = yaml.safe_dump(
            {
                "id": slug,
                "name": slug,
                "description": description,
                "version": "0.1.0",
                "author": "Local",
                "enabled": True,
                "slash_command": f"/{slug}",
                "allowed-tools": "",
            },
            allow_unicode=True,
            sort_keys=False,
        ).strip()
        content = (
            f"---\n{frontmatter}\n---\n\n"
            "## Instructions\n\n描述这个技能的使用方式、执行步骤和边界。\n"
        )
        skill_file.write_text(content, encoding="utf-8")
        return SkillFileResponse(skill=self._parse_skill_summary(root, skill_file), content=content)

    def read_local_skill(self, path: str) -> SkillFileResponse:
        root, target = self._resolve_existing_skill_file(path)
        content = target.read_text(encoding="utf-8")
        return SkillFileResponse(skill=self._parse_skill_summary(root, target), content=content)

    def update_local_skill_enabled(self, path: str, payload: SkillEnabledUpdate) -> SkillSummary:
        root, target = self._resolve_existing_skill_file(path)
        content = target.read_text(encoding="utf-8")
        meta, body = self._split_frontmatter(content)
        meta["enabled"] = payload.enabled
        target.write_text(self._dump_skill_content(meta, body), encoding="utf-8")
        return self._parse_skill_summary(root, target)

    def delete_local_skill(self, path: str) -> None:
        root, target = self._resolve_existing_skill_file(path)
        target.unlink()
        parent = target.parent
        if parent != root and parent.parent == root and not any(parent.iterdir()):
            parent.rmdir()

    def _skills_root(self) -> Path:
        return self._services.settings.workdir / ".hermes" / "skills"

    def _resolve_existing_skill_file(self, relative_path: str) -> tuple[Path, Path]:
        root = self._skills_root()
        target = self._resolve_skill_file(root, relative_path)
        if not target.exists() or not target.is_file():
            raise NotFoundError("Skill not found")
        return root, target

    def _resolve_skill_file(self, root: Path, relative_path: str) -> Path:
        if not relative_path:
            raise ValidationError("Skill path is required")

        candidate = (root / relative_path.lstrip("/")).resolve()
        root = root.resolve()
        if candidate != root and root not in candidate.parents:
            raise ValidationError("Path escapes skills directory")
        if candidate.name != "SKILL.md" and candidate.suffix.lower() != ".md":
            raise ValidationError("Only skill markdown files are supported")
        return candidate

    def _to_api_path(self, root: Path, path: Path) -> str:
        return path.resolve().relative_to(root.resolve()).as_posix()

    def _slugify_skill_name(self, name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower()).strip("-_")
        if not slug:
            raise ValidationError("Skill name must contain letters or numbers")
        return slug

    def _split_frontmatter(self, content: str) -> tuple[dict[str, object], str]:
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not frontmatter_match:
            return {}, content

        try:
            loaded = yaml.safe_load(frontmatter_match.group(1)) or {}
        except yaml.YAMLError:
            return {}, frontmatter_match.group(2)

        return loaded if isinstance(loaded, dict) else {}, frontmatter_match.group(2)

    def _dump_skill_content(self, meta: dict[str, object], body: str) -> str:
        frontmatter = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
        return f"---\n{frontmatter}\n---\n{body if body.startswith(chr(10)) else chr(10) + body}"

    def _capabilities_from_meta(self, meta: dict[str, object]) -> list[str]:
        capabilities = meta.get("capabilities")
        if isinstance(capabilities, list):
            return [str(item) for item in capabilities if str(item).strip()]

        allowed_tools = str(meta.get("allowed-tools") or "")
        tags: list[str] = []
        tool_map = {
            "Read": "文件读取",
            "Write": "文件写入",
            "Edit": "文件编辑",
            "Bash": "命令执行",
            "WebFetch": "网络请求",
            "WebSearch": "网络搜索",
        }
        for token, label in tool_map.items():
            if token in allowed_tools and label not in tags:
                tags.append(label)
        return tags

    def _parse_skill_summary(self, root: Path, path: Path) -> SkillSummary:
        content = path.read_text(encoding="utf-8")
        meta, _body = self._split_frontmatter(content)

        fallback_name = path.parent.name if path.name == "SKILL.md" else path.stem
        skill_id = str(meta.get("id") or fallback_name)
        name = str(meta.get("name") or fallback_name)
        slash_command = str(meta.get("slash_command") or f"/{name}")
        slash_commands = meta.get("slash_commands")
        if isinstance(slash_commands, list) and slash_commands:
            first = slash_commands[0]
            if isinstance(first, dict):
                slash_command = str(first.get("command") or slash_command)

        return SkillSummary(
            path=self._to_api_path(root, path),
            id=skill_id,
            name=name,
            description=str(meta.get("description") or ""),
            version=str(meta.get("version") or "1.0.0"),
            author=str(meta.get("author") or "Unknown"),
            enabled=bool(meta.get("enabled", True)),
            slash_command=slash_command,
            allowed_tools=str(meta.get("allowed-tools") or ""),
            capabilities=self._capabilities_from_meta(meta),
            size=path.stat().st_size,
            updated_at=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
        )

    def _list_skill_files(self, root: Path) -> list[Path]:
        if not root.exists():
            return []

        files: list[Path] = []
        for file_path in root.glob("*.md"):
            if not file_path.name.startswith("_"):
                files.append(file_path)

        for child in root.iterdir():
            if child.is_dir():
                skill_file = child / "SKILL.md"
                if skill_file.exists():
                    files.append(skill_file)

        return sorted(files, key=lambda item: self._to_api_path(root, item).lower())

    def _read_remote_yaml(self, url: str) -> object:
        with urlopen(url, timeout=8) as response:
            return yaml.safe_load(response.read().decode("utf-8"))

    def _plugin_to_market_skill(
        self,
        item: dict[str, object],
        source_id: str,
        source: dict[str, str],
        owner: str,
    ) -> MarketSkill:
        skill_paths = item.get("skills")
        source_url = ""
        if isinstance(skill_paths, list) and skill_paths:
            first_path = str(skill_paths[0]).strip()
            first_path = first_path[2:] if first_path.startswith("./") else first_path
            source_url = f"{source['raw_base_url']}/{first_path.rstrip('/')}/SKILL.md"
        elif isinstance(item.get("source"), str):
            source_path = str(item["source"]).strip()
            if source_path.startswith("http"):
                source_url = source_path
            else:
                source_path = source_path[2:] if source_path.startswith("./") else source_path
                source_url = f"{source['raw_base_url']}/{source_path.rstrip('/')}/SKILL.md"

        capabilities = item.get("capabilities")
        if not isinstance(capabilities, list):
            keywords = item.get("keywords")
            if isinstance(keywords, list) and keywords:
                capabilities = [str(keyword) for keyword in keywords[:6]]
            elif item.get("category"):
                capabilities = [str(item["category"])]
            else:
                capabilities = []

        raw_author = item.get("author")
        if isinstance(raw_author, dict):
            author = str(raw_author.get("name") or owner or source["name"])
        else:
            author = str(raw_author or owner or source["name"])

        return MarketSkill(
            id=str(item.get("id") or item.get("name") or ""),
            name=str(item.get("name") or item.get("id") or ""),
            description=str(item.get("description") or ""),
            version=str(item.get("version") or "1.0.0"),
            author=author,
            capabilities=[str(capability) for capability in capabilities],
            allowed_tools=str(item.get("allowed_tools") or item.get("allowed-tools") or ""),
            source_id=source_id,
            source_url=source_url,
        )

    def _load_market_skills(self, source_id: str) -> list[MarketSkill]:
        source = SKILL_MARKET_SOURCES.get(source_id)
        if source is None:
            raise NotFoundError("Skill source not found")

        try:
            try:
                payload = self._read_remote_yaml(source["url"])
            except Exception:
                payload = self._read_remote_yaml(source["fallback_url"])
        except Exception as exc:
            raise UpstreamServiceError("Unable to connect to skill source") from exc

        owner = ""
        if isinstance(payload, dict):
            raw_owner = payload.get("owner")
            if isinstance(raw_owner, dict):
                owner = str(raw_owner.get("name") or "")
            raw_items = payload.get("skills") or payload.get("plugins") or payload
        else:
            raw_items = payload
        if not isinstance(raw_items, list):
            raise UpstreamServiceError("Invalid skill source")

        market_skills: list[MarketSkill] = []
        for item in raw_items:
            if isinstance(item, dict):
                normalized = dict(item)
                normalized["source_id"] = source_id
                if "source" in normalized and "source_url" not in normalized:
                    normalized["source_url"] = normalized["source"]
                try:
                    if "skills" in normalized or "source" in normalized:
                        market_skills.append(self._plugin_to_market_skill(normalized, source_id, source, owner))
                    else:
                        market_skills.append(MarketSkill(**normalized))
                except Exception:
                    continue
        return [skill for skill in market_skills if skill.id and skill.source_url]

    def _market_skill_content(self, skill: MarketSkill) -> str:
        if skill.content:
            return skill.content
        if skill.source_url:
            try:
                with urlopen(skill.source_url, timeout=8) as response:
                    return response.read().decode("utf-8")
            except Exception as exc:
                raise UpstreamServiceError("Failed to download skill") from exc

        meta = {
            "id": skill.id,
            "name": skill.id,
            "description": skill.description,
            "version": skill.version,
            "author": skill.author,
            "enabled": True,
            "slash_command": f"/{skill.id}",
            "capabilities": skill.capabilities,
            "allowed-tools": skill.allowed_tools,
        }
        return self._dump_skill_content(meta, f"\n## Instructions\n\n{skill.description}\n")

    def _normalize_installed_skill_content(self, skill: MarketSkill, content: str) -> str:
        meta, body = self._split_frontmatter(content)
        meta.setdefault("id", skill.id)
        meta.setdefault("name", skill.id)
        meta.setdefault("description", skill.description)
        meta.setdefault("version", skill.version)
        meta.setdefault("author", skill.author)
        meta.setdefault("enabled", True)
        meta.setdefault("slash_command", f"/{skill.id}")
        meta.setdefault("capabilities", skill.capabilities)
        if skill.allowed_tools:
            meta.setdefault("allowed-tools", skill.allowed_tools)
        meta["market_source"] = skill.source_id
        meta["source_url"] = skill.source_url
        return self._dump_skill_content(meta, body)
