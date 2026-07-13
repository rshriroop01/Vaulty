"""Auth + tenancy: users, vaults, vault_memberships, user_sessions

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("totp_secret", sa.String(64), nullable=True),
        *_timestamps(),
    )
    op.create_table(
        "vaults",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False, server_default="free"),
        *_timestamps(),
    )
    op.create_table(
        "vault_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "vault_id",
            sa.Uuid(),
            sa.ForeignKey("vaults.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        *_timestamps(),
        sa.UniqueConstraint("vault_id", "user_id"),
    )
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )


def downgrade() -> None:
    op.drop_table("user_sessions")
    op.drop_table("vault_memberships")
    op.drop_table("vaults")
    op.drop_table("users")
