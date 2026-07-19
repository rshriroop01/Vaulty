import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import anyio.to_thread
import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentVault, DbSession
from app.core import audit
from app.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import hash_password, verify_password
from app.models import (
    AuditLog,
    Document,
    DocumentCategory,
    DocumentStatus,
    EmergencyBinder,
    EmergencyToken,
    User,
    Vault,
    VaultMembership,
    VaultRole,
)
from app.services.email import get_email_provider

router = APIRouter()
logger = structlog.get_logger("emergency")


class BinderUpdate(BaseModel):
    contacts: list[dict[str, Any]] = Field(default_factory=list, max_length=10)
    medical: dict[str, Any] = Field(default_factory=dict)
    delegates: list[dict[str, Any]] = Field(default_factory=list, max_length=10)


class ChecklistItem(BaseModel):
    key: str
    label: str
    done: bool
    sub: str


class AccessLogEntry(BaseModel):
    at: datetime
    action: str


class BinderOut(BaseModel):
    contacts: list[dict[str, Any]]
    medical: dict[str, Any]
    delegates: list[dict[str, Any]]
    checklist: list[ChecklistItem]
    qr_active: bool
    qr_issued_at: datetime | None
    access_log: list[AccessLogEntry]


class QrIssue(BaseModel):
    pin: str = Field(min_length=4, max_length=8, pattern=r"^\d+$")


class QrIssued(BaseModel):
    token: str  # raw — shown exactly once, lives inside the printed QR
    issued_at: datetime


class PublicAccessRequest(BaseModel):
    pin: str = Field(min_length=1, max_length=16)


class PublicBinder(BaseModel):
    vault_name: str
    contacts: list[dict[str, Any]]
    medical: dict[str, Any]
    insurance: list[dict[str, Any]]
    updated_at: datetime | None


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def _get_or_create_binder(db: DbSession, vault_id: UUID) -> EmergencyBinder:
    binder = await db.get(EmergencyBinder, vault_id)
    if binder is None:
        binder = EmergencyBinder(vault_id=vault_id, contacts=[], medical={}, delegates=[])
        db.add(binder)
        await db.flush()
    return binder


async def _category_exists(db: DbSession, vault_id: UUID, category: DocumentCategory) -> bool:
    doc = await db.scalar(
        select(Document.id)
        .where(
            Document.vault_id == vault_id,
            Document.category == category,
            Document.status != DocumentStatus.pending_upload,
        )
        .limit(1)
    )
    return doc is not None


async def _checklist(db: DbSession, vault_id: UUID, binder: EmergencyBinder) -> list[ChecklistItem]:
    has_insurance = await _category_exists(db, vault_id, DocumentCategory.insurance)
    has_ids = await _category_exists(db, vault_id, DocumentCategory.ids_legal)
    medical = binder.medical or {}
    return [
        ChecklistItem(
            key="contacts",
            label="Emergency contacts",
            done=len(binder.contacts or []) > 0,
            sub=f"{len(binder.contacts or [])} added" if binder.contacts else "add at least one",
        ),
        ChecklistItem(
            key="medical",
            label="Medical information",
            done=bool(medical.get("blood_group")),
            sub="blood group set" if medical.get("blood_group") else "blood group missing",
        ),
        ChecklistItem(
            key="medications",
            label="Current medications",
            done=bool(medical.get("medications")),
            sub="listed" if medical.get("medications") else "not listed",
        ),
        ChecklistItem(
            key="insurance",
            label="Insurance policies",
            done=has_insurance,
            sub="in vault" if has_insurance else "upload a policy",
        ),
        ChecklistItem(
            key="ids",
            label="IDs & legal documents",
            done=has_ids,
            sub="in vault" if has_ids else "upload an ID",
        ),
    ]


async def _active_token(db: DbSession, vault_id: UUID) -> EmergencyToken | None:
    token: EmergencyToken | None = await db.scalar(
        select(EmergencyToken).where(
            EmergencyToken.vault_id == vault_id, EmergencyToken.revoked_at.is_(None)
        )
    )
    return token


@router.get("", response_model=BinderOut)
async def get_binder(db: DbSession, ctx: CurrentVault) -> BinderOut:
    binder = await _get_or_create_binder(db, ctx.vault.id)
    await db.commit()
    token = await _active_token(db, ctx.vault.id)
    scans = (
        await db.scalars(
            select(AuditLog)
            .where(
                AuditLog.entity_type == "vault",
                AuditLog.entity_id == ctx.vault.id,
                AuditLog.action.in_(["emergency.scan", "emergency.access_denied"]),
            )
            .order_by(AuditLog.created_at.desc())
            .limit(10)
        )
    ).all()
    return BinderOut(
        contacts=binder.contacts or [],
        medical=binder.medical or {},
        delegates=binder.delegates or [],
        checklist=await _checklist(db, ctx.vault.id, binder),
        qr_active=token is not None,
        qr_issued_at=token.created_at if token else None,
        access_log=[AccessLogEntry(at=s.created_at, action=s.action) for s in scans],
    )


@router.put("", response_model=BinderOut)
async def update_binder(body: BinderUpdate, db: DbSession, ctx: CurrentVault) -> BinderOut:
    if not ctx.can_write:
        raise ForbiddenError("Your role cannot edit the binder")
    binder = await _get_or_create_binder(db, ctx.vault.id)
    binder.contacts = body.contacts
    binder.medical = body.medical
    binder.delegates = body.delegates
    await audit.record(
        db,
        "emergency.binder_update",
        actor_id=ctx.user.id,
        entity_type="vault",
        entity_id=ctx.vault.id,
    )
    await db.commit()
    return await get_binder(db, ctx)


@router.post("/qr", response_model=QrIssued)
async def issue_qr(body: QrIssue, db: DbSession, ctx: CurrentVault) -> QrIssued:
    if ctx.role not in (VaultRole.owner, VaultRole.admin):
        raise ForbiddenError("Only owners and admins manage emergency access")
    # Reissue = revoke everything outstanding, then mint fresh
    existing = await db.scalars(
        select(EmergencyToken).where(
            EmergencyToken.vault_id == ctx.vault.id, EmergencyToken.revoked_at.is_(None)
        )
    )
    now = datetime.now(UTC)
    for token in existing:
        token.revoked_at = now

    raw = secrets.token_urlsafe(24)
    record = EmergencyToken(
        vault_id=ctx.vault.id,
        token_hash=_hash(raw),
        pin_hash=hash_password(body.pin),
        created_by=ctx.user.id,
    )
    db.add(record)
    await audit.record(
        db,
        "emergency.qr_issued",
        actor_id=ctx.user.id,
        entity_type="vault",
        entity_id=ctx.vault.id,
    )
    await db.commit()
    return QrIssued(token=raw, issued_at=record.created_at or now)


@router.post("/qr/revoke", status_code=204)
async def revoke_qr(db: DbSession, ctx: CurrentVault) -> None:
    if ctx.role not in (VaultRole.owner, VaultRole.admin):
        raise ForbiddenError("Only owners and admins manage emergency access")
    tokens = await db.scalars(
        select(EmergencyToken).where(
            EmergencyToken.vault_id == ctx.vault.id, EmergencyToken.revoked_at.is_(None)
        )
    )
    now = datetime.now(UTC)
    for token in tokens:
        token.revoked_at = now
    await audit.record(
        db,
        "emergency.qr_revoked",
        actor_id=ctx.user.id,
        entity_type="vault",
        entity_id=ctx.vault.id,
    )
    await db.commit()


async def _notify_owners(db: DbSession, vault: Vault, subject: str, body: str) -> None:
    owners = (
        await db.execute(
            select(User)
            .join(VaultMembership, VaultMembership.user_id == User.id)
            .where(
                VaultMembership.vault_id == vault.id,
                VaultMembership.role == VaultRole.owner,
            )
        )
    ).scalars()
    provider = get_email_provider()
    for owner in owners:
        try:
            await anyio.to_thread.run_sync(provider.send, owner.email, subject, body)
        except Exception:
            logger.exception("owner_notification_failed")


@router.post("/access/{token}", response_model=PublicBinder)
async def public_access(token: str, body: PublicAccessRequest, db: DbSession) -> PublicBinder:
    """The PRD emergency journey: QR scan + PIN, no account credentials.
    Every attempt — granted or denied — is audit-logged; owners are notified."""
    record = await db.scalar(
        select(EmergencyToken).where(EmergencyToken.token_hash == _hash(token))
    )
    if record is None or record.revoked_at is not None:
        raise NotFoundError("This emergency link is no longer active")
    vault = await db.get(Vault, record.vault_id)
    if vault is None:
        raise NotFoundError("This emergency link is no longer active")

    if not verify_password(body.pin, record.pin_hash):
        await audit.record(db, "emergency.access_denied", entity_type="vault", entity_id=vault.id)
        await db.commit()
        await _notify_owners(
            db,
            vault,
            "Vaultly: failed emergency binder attempt",
            "Someone scanned your emergency QR but entered a wrong PIN. "
            "If this wasn't expected, revoke the QR in Vaultly → Emergency binder.",
        )
        raise UnauthorizedError("Incorrect PIN")

    binder = await db.get(EmergencyBinder, vault.id)
    insurance_docs = (
        await db.scalars(
            select(Document)
            .where(
                Document.vault_id == vault.id,
                Document.category == DocumentCategory.insurance,
                Document.status != DocumentStatus.pending_upload,
            )
            .limit(10)
        )
    ).all()
    await audit.record(db, "emergency.scan", entity_type="vault", entity_id=vault.id)
    await db.commit()
    await _notify_owners(
        db,
        vault,
        "Vaultly: emergency binder accessed",
        "Your emergency binder was just accessed via QR + PIN. "
        "This access was recorded in the audit log. If this wasn't expected, "
        "revoke the QR in Vaultly → Emergency binder.",
    )

    def _policy(doc: Document) -> dict[str, Any]:
        number = None
        for field in (doc.extracted or {}).get("fields", []):
            if any(k in field.get("label", "").lower() for k in ("policy", "number", "#")):
                number = field.get("value")
                break
        return {
            "provider": (doc.extracted or {}).get("vendor") or doc.title,
            "policy_number": number,
            "title": doc.title,
        }

    return PublicBinder(
        vault_name=vault.name,
        contacts=(binder.contacts if binder else []) or [],
        medical=(binder.medical if binder else {}) or {},
        insurance=[_policy(d) for d in insurance_docs],
        updated_at=binder.updated_at if binder else None,
    )
