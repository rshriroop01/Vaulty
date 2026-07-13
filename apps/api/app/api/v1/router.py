from fastapi import APIRouter

from app.api.v1.endpoints import auth, documents, meta, vault

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_v1_router.include_router(vault.router, prefix="/vault", tags=["vault"])
api_v1_router.include_router(meta.router, prefix="/meta", tags=["meta"])
