import enum
from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class VaultPlan(enum.StrEnum):
    free = "free"
    premium = "premium"
    family = "family"


class VaultRole(enum.StrEnum):
    """Matches the role dropdown in design screen 2i."""

    owner = "owner"
    admin = "admin"
    member = "member"
    emergency = "emergency"  # emergency-only access


class Vault(Base, TimestampMixin):
    """The unit of ownership. A personal account is a vault with one member;
    the Family plan is the same vault with more members (see ARCHITECTURE.md #3)."""

    __tablename__ = "vaults"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    plan: Mapped[VaultPlan] = mapped_column(
        Enum(VaultPlan, name="vault_plan", native_enum=False, length=20),
        default=VaultPlan.free,
    )

    memberships: Mapped[list["VaultMembership"]] = relationship(back_populates="vault")


class VaultMembership(Base, TimestampMixin):
    __tablename__ = "vault_memberships"
    __table_args__ = (UniqueConstraint("vault_id", "user_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    vault_id: Mapped[UUID] = mapped_column(ForeignKey("vaults.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[VaultRole] = mapped_column(
        Enum(VaultRole, name="vault_role", native_enum=False, length=20),
        default=VaultRole.member,
    )

    vault: Mapped[Vault] = relationship(back_populates="memberships")
