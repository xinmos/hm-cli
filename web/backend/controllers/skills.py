from __future__ import annotations

from fastapi import APIRouter, Query, Request

from web.backend.controllers.dependencies import get_services, to_http_error
from web.backend.models.skill import (
    MarketSkill,
    SkillCreateRequest,
    SkillEnabledUpdate,
    SkillFileResponse,
    SkillInstallRequest,
    SkillMarketSource,
    SkillSummary,
)
from web.backend.services.exceptions import BackendServiceError
from web.backend.services.skill_service import SkillApiService

router = APIRouter()


def _skill_service(request: Request) -> SkillApiService:
    return SkillApiService(get_services(request))


@router.get("", response_model=list[SkillSummary])
async def list_local_skills(request: Request) -> list[SkillSummary]:
    return _skill_service(request).list_local_skills()


@router.get("/sources", response_model=list[SkillMarketSource])
async def list_market_sources() -> list[SkillMarketSource]:
    return SkillApiService.from_static_sources()


@router.get("/market", response_model=list[MarketSkill])
async def list_market_skills(
    request: Request,
    source_id: str = Query(default="claude-code-skills"),
) -> list[MarketSkill]:
    try:
        return _skill_service(request).list_market_skills(source_id)
    except BackendServiceError as exc:
        raise to_http_error(exc) from exc


@router.post("/install", response_model=SkillFileResponse, status_code=201)
async def install_market_skill(payload: SkillInstallRequest, request: Request) -> SkillFileResponse:
    try:
        return _skill_service(request).install_market_skill(payload)
    except BackendServiceError as exc:
        raise to_http_error(exc) from exc


@router.post("", response_model=SkillFileResponse, status_code=201)
async def create_local_skill(payload: SkillCreateRequest, request: Request) -> SkillFileResponse:
    try:
        return _skill_service(request).create_local_skill(payload)
    except BackendServiceError as exc:
        raise to_http_error(exc) from exc


@router.get("/file", response_model=SkillFileResponse)
async def read_local_skill(
    request: Request,
    path: str = Query(..., min_length=1),
) -> SkillFileResponse:
    try:
        return _skill_service(request).read_local_skill(path)
    except BackendServiceError as exc:
        raise to_http_error(exc) from exc


@router.put("/file/enabled", response_model=SkillSummary)
async def update_local_skill_enabled(
    payload: SkillEnabledUpdate,
    request: Request,
    path: str = Query(..., min_length=1),
) -> SkillSummary:
    try:
        return _skill_service(request).update_local_skill_enabled(path, payload)
    except BackendServiceError as exc:
        raise to_http_error(exc) from exc


@router.delete("/file", status_code=204)
async def delete_local_skill(
    request: Request,
    path: str = Query(..., min_length=1),
) -> None:
    try:
        _skill_service(request).delete_local_skill(path)
    except BackendServiceError as exc:
        raise to_http_error(exc) from exc
