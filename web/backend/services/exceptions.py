from __future__ import annotations


class BackendServiceError(Exception):
    status_code = 500
    detail = "Internal server error"

    def __init__(self, detail: str | None = None):
        super().__init__(detail or self.detail)
        self.detail = detail or self.detail


class ValidationError(BackendServiceError):
    status_code = 400
    detail = "Invalid request"


class NotFoundError(BackendServiceError):
    status_code = 404
    detail = "Not found"


class ConflictError(BackendServiceError):
    status_code = 409
    detail = "Conflict"


class PayloadTooLargeError(BackendServiceError):
    status_code = 413
    detail = "Payload too large"


class UnsupportedMediaError(BackendServiceError):
    status_code = 415
    detail = "Unsupported media type"


class UpstreamServiceError(BackendServiceError):
    status_code = 502
    detail = "Upstream service error"
