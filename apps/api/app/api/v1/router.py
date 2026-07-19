from fastapi import APIRouter

from app.api.v1.endpoints import (
    assistant,
    auth,
    billing,
    documents,
    emergency,
    family,
    meta,
    reminders,
    search,
    vault,
)

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_v1_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_v1_router.include_router(search.router, prefix="/search", tags=["search"])
api_v1_router.include_router(assistant.router, prefix="/assistant", tags=["assistant"])
api_v1_router.include_router(reminders.router, prefix="/reminders", tags=["reminders"])
api_v1_router.include_router(family.router, prefix="/family", tags=["family"])
api_v1_router.include_router(emergency.router, prefix="/emergency", tags=["emergency"])
api_v1_router.include_router(vault.router, prefix="/vault", tags=["vault"])
api_v1_router.include_router(meta.router, prefix="/meta", tags=["meta"])
