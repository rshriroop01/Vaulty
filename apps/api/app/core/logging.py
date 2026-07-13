import logging
import sys
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings

REQUEST_ID_HEADER = "X-Request-ID"


def configure_logging() -> None:
    """JSON logs in production, pretty console logs locally. All logs carry contextvars."""
    settings = get_settings()

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if settings.is_production
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[*shared_processors, structlog.processors.format_exc_info, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns every request an ID, binds it to the log context, and logs the access line."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id, method=request.method, path=request.url.path
        )
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        structlog.get_logger("access").info("request", status_code=response.status_code)
        return response
