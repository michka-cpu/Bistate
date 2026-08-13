"""add listing_data provenance store

Revision ID: 20260723_0008
Revises: 20260722_0007
"""
from alembic import op
import sqlalchemy as sa

revision = "20260723_0008"
down_revision = "20260722_0007"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("properties") as batch:
        # Per-field listing facts with provenance/retrieval status, kept distinct from
        # enrichment_data (public/property enrichment) and underwriting_output (derived).
        batch.add_column(sa.Column("listing_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))


def downgrade():
    with op.batch_alter_table("properties") as batch:
        batch.drop_column("listing_data")
