"""Application errors and global exception handlers.

Every error response follows RFC 7807 (problem+json):
{"type", "title", "status", "detail", "request_id"}
"""

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger("errors")

PROBLEM_CONTENT_TYPE = "application/problem+json"


class AppError(Exception):
    """Base class for expected, domain-level failures."""

    status_code = 400
    title = "Bad Request"
    error_type = "about:blank"

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class UnauthorizedError(AppError):
    status_code = 401
    title = "Unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    title = "Forbidden"


class NotFoundError(AppError):
    status_code = 404
    title = "Not Found"


class ConflictError(AppError):
    status_code = 409
    title = "Conflict"


class PlanUpgradeRequiredError(AppError):
    """Feature gated behind a paid plan (PRD business model). The distinct
    `type` lets the frontend render an upsell card instead of a plain error."""

    status_code = 403
    title = "Upgrade Required"
    error_type = "https://vaultly.app/problems/plan-upgrade-required"


def _problem(request: Request, status: int, title: str, detail: str, type_: str) -> JSONResponse:
    body = {
        "type": type_,
        "title": title,
        "status": status,
        "detail": detail,
        "request_id": request.headers.get("X-Request-ID"),
    }
    return JSONResponse(status_code=status, content=body, media_type=PROBLEM_CONTENT_TYPE)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return _problem(request, exc.status_code, exc.title, exc.detail, exc.error_type)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = str(exc.detail or "Error")
        return _problem(request, exc.status_code, detail, detail, "about:blank")

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Human-readable, safe to show directly in UIs: "email: value is not a valid email"
        detail = "; ".join(
            f"{'.'.join(str(part) for part in err['loc'] if part != 'body')}: {err['msg']}"
            for err in exc.errors()
        )
        return _problem(request, 422, "Validation Error", detail, "about:blank")

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", path=request.url.path)
        return _problem(
            request, 500, "Internal Server Error", "An unexpected error occurred.", "about:blank"
        )
