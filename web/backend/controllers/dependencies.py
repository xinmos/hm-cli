from __future__ import annotations

from fastapi import HTTPException, Request

from web.backend.services.container import WebServiceContainer
from web.backend.services.exceptions import BackendServiceError


def get_services(request: Request) -> WebServiceContainer:
    return request.app.state.services


def to_http_error(exc: BackendServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)
