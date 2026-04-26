from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from urllib.request import urlopen

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
import yaml

from web.backend.app_state import WebServiceContainer

router = APIRouter()

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


class SkillSummary(BaseModel):
    path: str
    id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    author: str = "Unknown"
    enabled: bool = True
    slash_command: str = ""
    allowed_tools: str = ""
    capabilities: list[str] = Field(default_factory=list)
    size: int
    updated_at: str


class SkillFileResponse(BaseModel):
    skill: SkillSummary
    content: str


class SkillCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str = ""


class SkillEnabledUpdate(BaseModel):
    enabled: bool


class MarketSkill(BaseModel):
    id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    author: str = "Hermes"
    capabilities: list[str] = Field(default_factory=list)
    allowed_tools: str = ""
    source_id: str = ""
    content: str = Field(default="", exclude=True)
    source_url: str = ""


class SkillInstallRequest(BaseModel):
    id: str
    source_id: str = "claude-code-skills"


class SkillMarketSource(BaseModel):
    id: str
    name: str
    url: str


def _read_remote_yaml(url: str) -> object:
    with urlopen(url, timeout=8) as response:
        return yaml.safe_load(response.read().decode("utf-8"))


def _services(request: Request) -> WebServiceContainer:
    return request.app.state.services


def _skills_root(request: Request) -> Path:
    return _services(request).settings.workdir / ".hermes" / "skills"


def _to_api_path(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _resolve_skill_file(root: Path, relative_path: str) -> Path:
    if not relative_path:
        raise HTTPException(status_code=400, detail="Skill path is required")

    candidate = (root / relative_path.lstrip("/")).resolve()
    root = root.resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(status_code=400, detail="Path escapes skills directory")
    if candidate.name != "SKILL.md" and candidate.suffix.lower() != ".md":
        raise HTTPException(status_code=400, detail="Only skill markdown files are supported")
    return candidate


def _slugify_skill_name(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower()).strip("-_")
    if not slug:
        raise HTTPException(status_code=400, detail="Skill name must contain letters or numbers")
    return slug


def _split_frontmatter(content: str) -> tuple[dict[str, object], str]:
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if not frontmatter_match:
        return {}, content

    try:
        loaded = yaml.safe_load(frontmatter_match.group(1)) or {}
    except yaml.YAMLError:
        return {}, frontmatter_match.group(2)

    return loaded if isinstance(loaded, dict) else {}, frontmatter_match.group(2)


def _dump_skill_content(meta: dict[str, object], body: str) -> str:
    frontmatter = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{frontmatter}\n---\n{body if body.startswith(chr(10)) else chr(10) + body}"


def _capabilities_from_meta(meta: dict[str, object]) -> list[str]:
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


def _parse_skill_summary(root: Path, path: Path) -> SkillSummary:
    content = path.read_text(encoding="utf-8")
    meta, _body = _split_frontmatter(content)

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
        path=_to_api_path(root, path),
        id=skill_id,
        name=name,
        description=str(meta.get("description") or ""),
        version=str(meta.get("version") or "1.0.0"),
        author=str(meta.get("author") or "Unknown"),
        enabled=bool(meta.get("enabled", True)),
        slash_command=slash_command,
        allowed_tools=str(meta.get("allowed-tools") or ""),
        capabilities=_capabilities_from_meta(meta),
        size=path.stat().st_size,
        updated_at=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
    )


def _list_skill_files(root: Path) -> list[Path]:
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

    return sorted(files, key=lambda item: _to_api_path(root, item).lower())


def _plugin_to_market_skill(item: dict[str, object], source_id: str, source: dict[str, str], owner: str) -> MarketSkill:
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


def _load_market_skills(source_id: str) -> list[MarketSkill]:
    source = SKILL_MARKET_SOURCES.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Skill source not found")

    try:
        try:
            payload = _read_remote_yaml(source["url"])
        except Exception:
            payload = _read_remote_yaml(source["fallback_url"])
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unable to connect to skill source") from exc

    owner = ""
    if isinstance(payload, dict):
        raw_owner = payload.get("owner")
        if isinstance(raw_owner, dict):
            owner = str(raw_owner.get("name") or "")
        raw_items = payload.get("skills") or payload.get("plugins") or payload
    else:
        raw_items = payload
    if not isinstance(raw_items, list):
        raise HTTPException(status_code=502, detail="Invalid skill source")

    market_skills: list[MarketSkill] = []
    for item in raw_items:
        if isinstance(item, dict):
            normalized = dict(item)
            normalized["source_id"] = source_id
            if "source" in normalized and "source_url" not in normalized:
                normalized["source_url"] = normalized["source"]
            try:
                if "skills" in normalized or "source" in normalized:
                    market_skills.append(_plugin_to_market_skill(normalized, source_id, source, owner))
                else:
                    market_skills.append(MarketSkill(**normalized))
            except Exception:
                continue
    return [skill for skill in market_skills if skill.id and skill.source_url]


def _market_skill_content(skill: MarketSkill) -> str:
    if skill.content:
        return skill.content
    if skill.source_url:
        try:
            with urlopen(skill.source_url, timeout=8) as response:
                return response.read().decode("utf-8")
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Failed to download skill") from exc

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
    return _dump_skill_content(meta, f"\n## Instructions\n\n{skill.description}\n")


def _normalize_installed_skill_content(skill: MarketSkill, content: str) -> str:
    meta, body = _split_frontmatter(content)
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
    return _dump_skill_content(meta, body)


@router.get("", response_model=list[SkillSummary])
async def list_local_skills(request: Request) -> list[SkillSummary]:
    root = _skills_root(request)
    return [_parse_skill_summary(root, path) for path in _list_skill_files(root)]


@router.get("/sources", response_model=list[SkillMarketSource])
async def list_market_sources() -> list[SkillMarketSource]:
    return [
        SkillMarketSource(id=source_id, name=source["name"], url=source["url"])
        for source_id, source in SKILL_MARKET_SOURCES.items()
    ]


@router.get("/market", response_model=list[MarketSkill])
async def list_market_skills(source_id: str = Query(default="claude-code-skills")) -> list[MarketSkill]:
    return _load_market_skills(source_id)


@router.post("/install", response_model=SkillFileResponse, status_code=201)
async def install_market_skill(payload: SkillInstallRequest, request: Request) -> SkillFileResponse:
    root = _skills_root(request)
    market_skill = next((skill for skill in _load_market_skills(payload.source_id) if skill.id == payload.id), None)
    if market_skill is None:
        raise HTTPException(status_code=404, detail="Market skill not found")

    slug = _slugify_skill_name(market_skill.id)
    skill_dir = root / slug
    skill_file = skill_dir / "SKILL.md"
    if skill_file.exists():
        raise HTTPException(status_code=409, detail="Skill already installed")

    skill_dir.mkdir(parents=True, exist_ok=False)
    content = _normalize_installed_skill_content(market_skill, _market_skill_content(market_skill))
    skill_file.write_text(content, encoding="utf-8")
    return SkillFileResponse(skill=_parse_skill_summary(root, skill_file), content=content)


@router.post("", response_model=SkillFileResponse, status_code=201)
async def create_local_skill(payload: SkillCreateRequest, request: Request) -> SkillFileResponse:
    root = _skills_root(request)
    slug = _slugify_skill_name(payload.name)
    skill_dir = root / slug
    skill_file = skill_dir / "SKILL.md"
    if skill_file.exists():
        raise HTTPException(status_code=409, detail="Skill already exists")

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
    content = f"---\n{frontmatter}\n---\n\n## Instructions\n\n描述这个技能的使用方式、执行步骤和边界。\n"
    skill_file.write_text(content, encoding="utf-8")
    return SkillFileResponse(skill=_parse_skill_summary(root, skill_file), content=content)


@router.get("/file", response_model=SkillFileResponse)
async def read_local_skill(
    request: Request,
    path: str = Query(..., min_length=1),
) -> SkillFileResponse:
    root = _skills_root(request)
    target = _resolve_skill_file(root, path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Skill not found")

    content = target.read_text(encoding="utf-8")
    return SkillFileResponse(skill=_parse_skill_summary(root, target), content=content)


@router.put("/file/enabled", response_model=SkillSummary)
async def update_local_skill_enabled(
    payload: SkillEnabledUpdate,
    request: Request,
    path: str = Query(..., min_length=1),
) -> SkillSummary:
    root = _skills_root(request)
    target = _resolve_skill_file(root, path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Skill not found")

    content = target.read_text(encoding="utf-8")
    meta, body = _split_frontmatter(content)
    meta["enabled"] = payload.enabled
    target.write_text(_dump_skill_content(meta, body), encoding="utf-8")
    return _parse_skill_summary(root, target)


@router.delete("/file", status_code=204)
async def delete_local_skill(
    request: Request,
    path: str = Query(..., min_length=1),
) -> None:
    root = _skills_root(request)
    target = _resolve_skill_file(root, path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Skill not found")

    target.unlink()
    parent = target.parent
    if parent != root and parent.parent == root and not any(parent.iterdir()):
        parent.rmdir()
