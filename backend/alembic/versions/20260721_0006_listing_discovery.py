"""add listing discovery

Revision ID: 20260721_0006
Revises: 20260720_0005
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa
revision = "20260721_0006"
down_revision = "20260720_0005"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("discovered_listings", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("provider_listing_id", sa.String(255), nullable=False), sa.Column("listing_source", sa.String(100), nullable=False), sa.Column("listing_url", sa.String(2000)), sa.Column("address", sa.String(500), nullable=False), sa.Column("city", sa.String(100), nullable=False), sa.Column("state", sa.String(2), nullable=False), sa.Column("postal_code", sa.String(20)), sa.Column("county", sa.String(150)), sa.Column("asking_price", sa.Numeric(14, 2)), sa.Column("acreage", sa.Float()), sa.Column("bedrooms", sa.Float()), sa.Column("bathrooms", sa.Float()), sa.Column("property_type", sa.String(100)), sa.Column("photo_url", sa.String(2000)), sa.Column("listing_date", sa.DateTime(timezone=True)), sa.Column("is_watchlisted", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
def downgrade(): op.drop_table("discovered_listings")
