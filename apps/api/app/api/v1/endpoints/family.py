import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import anyio.to_thread
import structlog
from fastapi import APIRouter
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from app.api.deps import ACCESS_LEVELS, CurrentUser, CurrentVault, DbSession
from app.core import audit
from app.core.config import get_settings
from app.core.errors import AppError, ForbiddenError, NotFoundError, PlanUpgradeRequiredError
from app.models import User, Vault, VaultInvite, VaultMembership, VaultPlan, VaultRole
from app.services.email import get_email_provider

router = APIRouter()
logger = structlog.get_logger("family")

MAX_MEMBERS = 6  # family plan ceiling (PRD)
INVITE_TTL_DAYS = 7
INVITABLE_ROLES = {"admin", "member", "emergency"}


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class MemberOut(BaseModel):
    membership_id: UUID
    user_id: UUID
    name: str
    email: str
    role: str
    category_access: dict[str, str] | None
    is_me: bool


class InviteOut(BaseModel):
    id: UUID
    email: str
    role: str
    expires_at: datetime


class MembersResponse(BaseModel):
    vault_name: str
    members: list[MemberOut]
    pending_invites: list[InviteOut]


class InviteCreate(BaseModel):
    email: EmailStr
    role: str = Field(default="member")


class MemberPatch(BaseModel):
    role: str | None = None
    category_access: dict[str, str] | None = None


class InviteInfo(BaseModel):
    vault_name: str
    invited_by: str
    role: str
    email: str


@router.get("/members", response_model=MembersResponse)
async def list_members(db: DbSession, ctx: CurrentVault) -> MembersResponse:
    rows = (
        await db.execute(
            select(VaultMembership, User)
            .join(User, User.id == VaultMembership.user_id)
            .where(VaultMembership.vault_id == ctx.vault.id)
            .order_by(VaultMembership.created_at)
        )
    ).all()
    invites = (
        await db.scalars(
            select(VaultInvite).where(
                VaultInvite.vault_id == ctx.vault.id,
                VaultInvite.accepted_at.is_(None),
                VaultInvite.expires_at > datetime.now(UTC),
            )
        )
    ).all()
    return MembersResponse(
        vault_name=ctx.vault.name,
        members=[
            MemberOut(
                membership_id=m.id,
                user_id=u.id,
                name=u.name,
                email=u.email,
                role=m.role.value,
                category_access=m.category_access,
                is_me=u.id == ctx.user.id,
            )
            for m, u in rows
        ],
        pending_invites=[
            InviteOut(id=i.id, email=i.email, role=i.role, expires_at=i.expires_at) for i in invites
        ],
    )


@router.post("/invites", response_model=InviteOut, status_code=201)
async def create_invite(body: InviteCreate, db: DbSession, ctx: CurrentVault) -> InviteOut:
    if ctx.role not in (VaultRole.owner, VaultRole.admin):
        raise ForbiddenError("Only owners and admins can invite")
    if ctx.vault.plan != VaultPlan.family:
        raise PlanUpgradeRequiredError(
            "Adding members requires the Family plan — upgrade to invite people to your vault."
        )
    if body.role not in INVITABLE_ROLES:
        raise AppError(f"Role must be one of {sorted(INVITABLE_ROLES)}")

    email = body.email.lower()
    member_count = (
        await db.scalar(select(func.count()).where(VaultMembership.vault_id == ctx.vault.id))
    ) or 0
    if member_count >= MAX_MEMBERS:
        raise AppError(f"Vaults support up to {MAX_MEMBERS} members")
    existing_user = await db.scalar(select(User).where(User.email == email))
    if existing_user is not None:
        already = await db.scalar(
            select(VaultMembership).where(
                VaultMembership.vault_id == ctx.vault.id,
                VaultMembership.user_id == existing_user.id,
            )
        )
        if already is not None:
            raise AppError("That person is already a member")

    raw_token = secrets.token_urlsafe(24)
    invite = VaultInvite(
        vault_id=ctx.vault.id,
        email=email,
        role=body.role,
        token_hash=_hash(raw_token),
        invited_by=ctx.user.id,
        expires_at=datetime.now(UTC) + timedelta(days=INVITE_TTL_DAYS),
    )
    db.add(invite)
    await db.flush()
    await audit.record(
        db,
        "family.invite",
        actor_id=ctx.user.id,
        entity_type="invite",
        entity_id=invite.id,
        email=email,
        role=body.role,
    )
    await db.commit()

    link = f"{get_settings().frontend_url}/invite/{raw_token}"
    try:
        await anyio.to_thread.run_sync(
            get_email_provider().send,
            email,
            f"{ctx.user.name} invited you to {ctx.vault.name} on Vaultly",
            f"{ctx.user.name} invited you to join “{ctx.vault.name}” as {body.role}.\n\n"
            f"Accept the invitation: {link}\n\n"
            f"This link expires in {INVITE_TTL_DAYS} days.\n— Vaultly",
        )
    except Exception:
        logger.exception("invite_email_failed", invite_id=str(invite.id))
    return InviteOut(id=invite.id, email=email, role=invite.role, expires_at=invite.expires_at)


async def _valid_invite(db: DbSession, token: str) -> VaultInvite:
    invite = await db.scalar(select(VaultInvite).where(VaultInvite.token_hash == _hash(token)))
    if (
        invite is None
        or invite.accepted_at is not None
        or invite.expires_at.replace(tzinfo=UTC) < datetime.now(UTC)
    ):
        raise NotFoundError("This invitation is invalid or has expired")
    return invite


@router.get("/invites/{token}", response_model=InviteInfo)
async def invite_info(token: str, db: DbSession) -> InviteInfo:
    """Public: what the invite lands on before signing in."""
    invite = await _valid_invite(db, token)
    vault = await db.get(Vault, invite.vault_id)
    inviter = await db.get(User, invite.invited_by)
    return InviteInfo(
        vault_name=vault.name if vault else "a vault",
        invited_by=inviter.name if inviter else "A Vaultly user",
        role=invite.role,
        email=invite.email,
    )


@router.post("/invites/{token}/accept", status_code=204)
async def accept_invite(token: str, db: DbSession, user: CurrentUser) -> None:
    invite = await _valid_invite(db, token)
    existing = await db.scalar(
        select(VaultMembership).where(
            VaultMembership.vault_id == invite.vault_id,
            VaultMembership.user_id == user.id,
        )
    )
    if existing is not None:
        raise AppError("You are already a member of this vault")
    db.add(VaultMembership(vault_id=invite.vault_id, user_id=user.id, role=VaultRole(invite.role)))
    invite.accepted_at = datetime.now(UTC)
    await audit.record(
        db,
        "family.join",
        actor_id=user.id,
        entity_type="vault",
        entity_id=invite.vault_id,
        role=invite.role,
    )
    await db.commit()


@router.patch("/members/{membership_id}", response_model=MemberOut)
async def patch_member(
    membership_id: UUID, body: MemberPatch, db: DbSession, ctx: CurrentVault
) -> MemberOut:
    if ctx.role != VaultRole.owner:
        raise ForbiddenError("Only the owner can change roles and access")
    membership = await db.get(VaultMembership, membership_id)
    if membership is None or membership.vault_id != ctx.vault.id:
        raise NotFoundError("Member not found")
    if membership.user_id == ctx.user.id:
        raise AppError("You cannot change your own membership")

    if body.role is not None:
        if body.role not in INVITABLE_ROLES:
            raise AppError(f"Role must be one of {sorted(INVITABLE_ROLES)}")
        membership.role = VaultRole(body.role)
    if body.category_access is not None:
        for level in body.category_access.values():
            if level not in ACCESS_LEVELS:
                raise AppError(f"Access must be one of {list(ACCESS_LEVELS)}")
        membership.category_access = body.category_access

    await audit.record(
        db,
        "family.member_update",
        actor_id=ctx.user.id,
        entity_type="membership",
        entity_id=membership.id,
        role=membership.role.value,
    )
    await db.commit()
    member_user = await db.get(User, membership.user_id)
    return MemberOut(
        membership_id=membership.id,
        user_id=membership.user_id,
        name=member_user.name if member_user else "",
        email=member_user.email if member_user else "",
        role=membership.role.value,
        category_access=membership.category_access,
        is_me=False,
    )


@router.delete("/members/{membership_id}", status_code=204)
async def remove_member(membership_id: UUID, db: DbSession, ctx: CurrentVault) -> None:
    if ctx.role != VaultRole.owner:
        raise ForbiddenError("Only the owner can remove members")
    membership = await db.get(VaultMembership, membership_id)
    if membership is None or membership.vault_id != ctx.vault.id:
        raise NotFoundError("Member not found")
    if membership.user_id == ctx.user.id:
        raise AppError("You cannot remove yourself")
    await db.delete(membership)
    await audit.record(
        db,
        "family.member_removed",
        actor_id=ctx.user.id,
        entity_type="membership",
        entity_id=membership_id,
    )
    await db.commit()
