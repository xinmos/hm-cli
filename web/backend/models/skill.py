from __future__ import annotations

from pydantic import BaseModel, Field


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
