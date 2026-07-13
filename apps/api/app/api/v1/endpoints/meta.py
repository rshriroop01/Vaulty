from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter()


class VersionResponse(BaseModel):
    name: str
    version: str
    environment: str
    api_version: str


@router.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    settings = get_settings()
    return VersionResponse(
        name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        api_version="v1",
    )
