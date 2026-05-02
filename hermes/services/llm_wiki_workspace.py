from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


REQUIRED_DIRECTORIES = [
    ".obsidian",
    "raw/assets",
    "raw/sources",
    "schema",
    "wiki/comparisons",
    "wiki/concepts",
    "wiki/entities",
    "wiki/queries",
    "wiki/sources",
    "wiki/synthesis",
]


@dataclass(frozen=True)
class LLMWikiStatus:
    exists: bool
    is_directory: bool
    is_initialized: bool
    missing_items: list[str]
    message: str

    def to_dict(self) -> dict[str, bool | list[str] | str]:
        return {
            "exists": self.exists,
            "is_directory": self.is_directory,
            "is_initialized": self.is_initialized,
            "missing_items": self.missing_items,
            "message": self.message,
        }


@dataclass(frozen=True)
class LLMWikiInitResult:
    path: str
    created_dirs: list[str]
    created_files: list[str]
    skipped_files: list[str]
    status: LLMWikiStatus

    def to_dict(self) -> dict[str, str | list[str] | dict[str, bool | list[str] | str]]:
        return {
            "path": self.path,
            "created_dirs": self.created_dirs,
            "created_files": self.created_files,
            "skipped_files": self.skipped_files,
            "status": self.status.to_dict(),
        }


def default_templates_dir() -> Path:
    return Path(__file__).parent.parent / "skills" / "llm-wiki" / "templates"


def inspect_llm_wiki(path: Path, templates_dir: Path | None = None) -> LLMWikiStatus:
    templates = templates_dir or default_templates_dir()
    missing_items: list[str] = []
    exists = path.exists()
    is_directory = path.is_dir()

    if exists and not is_directory:
        return LLMWikiStatus(
            exists=True,
            is_directory=False,
            is_initialized=False,
            missing_items=["<root-directory>"],
            message="路径已存在，但不是文件夹",
        )

    for relative_dir in REQUIRED_DIRECTORIES:
        if not (path / relative_dir).is_dir():
            missing_items.append(relative_dir)

    if templates.exists():
        for template_path in sorted(templates.rglob("*")):
            if not template_path.is_file():
                continue
            relative_path = str(template_path.relative_to(templates))
            if not (path / relative_path).is_file():
                missing_items.append(relative_path)
    else:
        missing_items.append("<bundled-templates>")

    if not missing_items:
        message = "知识库已初始化"
    elif not exists:
        message = "目录还不存在，可以一键初始化"
    else:
        message = f"目录缺少 {len(missing_items)} 个必要项目，可以补齐初始化"

    return LLMWikiStatus(
        exists=exists,
        is_directory=is_directory or not exists,
        is_initialized=not missing_items,
        missing_items=missing_items,
        message=message,
    )


def initialize_llm_wiki(path: Path, templates_dir: Path | None = None) -> LLMWikiInitResult:
    templates = templates_dir or default_templates_dir()
    if not templates.exists():
        raise ValueError(f"Template directory not found: {templates}")
    if path.exists() and not path.is_dir():
        raise ValueError(f"llm-wiki path exists but is not a directory: {path}")

    path.mkdir(parents=True, exist_ok=True)

    created_dirs: list[str] = []
    for relative_dir in REQUIRED_DIRECTORIES:
        target_dir = path / relative_dir
        if not target_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)
            created_dirs.append(relative_dir)

    created_files: list[str] = []
    skipped_files: list[str] = []
    for template_path in sorted(templates.rglob("*")):
        if not template_path.is_file():
            continue
        relative_path = template_path.relative_to(templates)
        target_path = path / relative_path
        relative_name = str(relative_path)
        if target_path.exists():
            skipped_files.append(relative_name)
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(template_path, target_path)
        created_files.append(relative_name)

    return LLMWikiInitResult(
        path=str(path),
        created_dirs=created_dirs,
        created_files=created_files,
        skipped_files=skipped_files,
        status=inspect_llm_wiki(path, templates),
    )
