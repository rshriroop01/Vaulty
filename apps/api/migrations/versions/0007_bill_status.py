"""Medical bill status tracking

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("bill_status", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "bill_status")
