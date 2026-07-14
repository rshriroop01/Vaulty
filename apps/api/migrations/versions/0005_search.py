"""Search text + FTS index

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents", sa.Column("search_text", sa.String(), nullable=False, server_default="")
    )
    # Backfill everything findable, including extracted field chips
    op.execute(
        """
        UPDATE documents SET search_text = trim(
            title || ' ' || file_name || ' ' ||
            coalesce(extracted->>'vendor', '') || ' ' ||
            coalesce(extracted->>'expiry_date', '') || ' ' ||
            coalesce(extracted->>'document_date', '') || ' ' ||
            coalesce(extracted->>'amount', '') || ' ' ||
            coalesce(
                (SELECT string_agg((f->>'label') || ' ' || (f->>'value'), ' ')
                 FROM jsonb_array_elements(extracted->'fields') AS f),
                ''
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_documents_search_fts ON documents
        USING gin (to_tsvector('english', search_text))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_documents_search_fts")
    op.drop_column("documents", "search_text")
