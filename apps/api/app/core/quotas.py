"""Plan limits (PRD business model). Enforced from the first upload so paid tiers
are just limit changes — billing itself is milestone M9."""

from dataclasses import dataclass

from app.models.vault import VaultPlan

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # per-file cap from design screen 2b

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/webp",
}


@dataclass(frozen=True)
class PlanLimits:
    max_documents: int | None  # None = unlimited
    max_storage_bytes: int | None
    ocr_per_month: int | None


PLAN_LIMITS: dict[VaultPlan, PlanLimits] = {
    VaultPlan.free: PlanLimits(
        max_documents=25, max_storage_bytes=100 * 1024 * 1024, ocr_per_month=5
    ),
    VaultPlan.premium: PlanLimits(max_documents=None, max_storage_bytes=None, ocr_per_month=None),
    VaultPlan.family: PlanLimits(max_documents=None, max_storage_bytes=None, ocr_per_month=None),
}
