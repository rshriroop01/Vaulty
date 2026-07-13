from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.health import router as health_router


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    if settings.is_production and settings.secret_key == "dev-only-secret-change-me":  # noqa: S105
        raise RuntimeError("SECRET_KEY must be set in production")

    app = FastAPI(
        title="Vaultly API",
        version=settings.app_version,
        # OpenAPI + docs live under the versioned prefix; the contract is the
        # source for generated frontend types (packages/shared-types).
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url=f"{settings.api_v1_prefix}/docs",
        redoc_url=None,
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
