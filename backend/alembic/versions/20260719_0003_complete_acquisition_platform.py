"""complete acquisition platform

Revision ID: 202607190003
Revises: 202607190002
Create Date: 2026-07-19 03:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "202607190003"
down_revision: Union[str, None] = "202607190002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = [
        sa.Column("status", sa.String(30), nullable=False, server_default="New"),
        sa.Column("listing_source", sa.String(100)),
        sa.Column("listing_url", sa.String(2000)),
        sa.Column("mls_number", sa.String(100)),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("county", sa.String(150)),
        sa.Column("acreage", sa.Float()),
        sa.Column("bedrooms", sa.Float()),
        sa.Column("bathrooms", sa.Float()),
        sa.Column("square_feet", sa.Integer()),
        sa.Column("asking_price", sa.Numeric(14, 2)),
        sa.Column("annual_taxes", sa.Numeric(14, 2)),
        sa.Column("images", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("description", sa.Text()),
        sa.Column("agent", sa.JSON()),
        sa.Column("enrichment_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("underwriting_output", sa.JSON()),
        sa.Column("underwriting_assumptions", sa.JSON()),
        sa.Column("overall_score", sa.Float()),
        sa.Column("buy_score", sa.Float()),
        sa.Column("airbnb_score", sa.Float()),
        sa.Column("wedding_score", sa.Float()),
        sa.Column("personal_use_score", sa.Float()),
        sa.Column("confidence_score", sa.Float()),
    ]
    for column in columns:
        op.add_column("properties", column)

    op.create_table(
        "property_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("stored_filename", sa.String(500), nullable=False),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("content_type", sa.String(255)),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_table(
        "property_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_table(
        "property_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("assignee", sa.String(255)),
        sa.Column("due_date", sa.Date()),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("property_tasks")
    op.drop_table("property_notes")
    op.drop_table("property_documents")
    for name in [
        "confidence_score", "personal_use_score", "wedding_score", "airbnb_score", "buy_score",
        "overall_score", "underwriting_assumptions", "underwriting_output", "enrichment_data", "agent",
        "description", "images", "annual_taxes", "asking_price", "square_feet", "bathrooms", "bedrooms",
        "acreage", "county", "longitude", "latitude", "mls_number", "listing_url", "listing_source", "status",
    ]:
        op.drop_column("properties", name)
