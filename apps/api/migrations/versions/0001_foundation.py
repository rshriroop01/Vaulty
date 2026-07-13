"""Foundation tables: audit_log, feature_flags

Revision ID: 0001
Revises:
Create Date: 2026-07-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("context", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False, index=True
        ),
    )
    op.create_table(
        "feature_flags",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("feature_flags")
    op.drop_table("audit_log")
