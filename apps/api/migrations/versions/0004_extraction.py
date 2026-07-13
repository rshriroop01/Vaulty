"""Extraction results on documents

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("extracted", JSONB, nullable=True))
    op.add_column("documents", sa.Column("expiry_date", sa.Date(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("extraction_requested_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "extraction_requested_at")
    op.drop_column("documents", "expiry_date")
    op.drop_column("documents", "extracted")
