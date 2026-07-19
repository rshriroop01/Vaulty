"""Family sharing + emergency binder

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vault_memberships", sa.Column("category_access", JSONB, nullable=True))
    op.create_table(
        "vault_invites",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "vault_id",
            sa.Uuid(),
            sa.ForeignKey("vaults.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("invited_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "emergency_binders",
        sa.Column(
            "vault_id",
            sa.Uuid(),
            sa.ForeignKey("vaults.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("contacts", JSONB, nullable=False, server_default="[]"),
        sa.Column("medical", JSONB, nullable=False, server_default="{}"),
        sa.Column("delegates", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "emergency_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "vault_id",
            sa.Uuid(),
            sa.ForeignKey("vaults.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("pin_hash", sa.String(255), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("emergency_tokens")
    op.drop_table("emergency_binders")
    op.drop_table("vault_invites")
    op.drop_column("vault_memberships", "category_access")
