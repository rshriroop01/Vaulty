"""Seed the M8 AI assistant feature flag

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

# There's no separate seed script in this repo (migration 0001 defines
# feature_flags with no seed rows) — this migration is the seeding mechanism,
# so `make upgrade` turns the assistant on for local dev out of the box. Ops
# can flip it back off per-environment via the feature_flags table directly.
feature_flags = sa.table(
    "feature_flags",
    sa.column("key", sa.String),
    sa.column("enabled", sa.Boolean),
    sa.column("description", sa.String),
)


def upgrade() -> None:
    op.bulk_insert(
        feature_flags,
        [
            {
                "key": "assistant",
                "enabled": True,
                "description": "M8 AI assistant — Claude-backed Q&A over the vault corpus",
            }
        ],
    )


def downgrade() -> None:
    op.execute(feature_flags.delete().where(feature_flags.c.key == "assistant"))
