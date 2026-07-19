"""live property intelligence

Revision ID: 20260719_0004
Revises: 202607190003
"""
from alembic import op
import sqlalchemy as sa
revision = "20260719_0004"
down_revision = "202607190003"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("properties") as batch:
        batch.add_column(sa.Column("hoa", sa.Numeric(14, 2), nullable=True))
        batch.add_column(sa.Column("year_built", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("parcel_id", sa.String(150), nullable=True))
        batch.add_column(sa.Column("listing_status", sa.String(100), nullable=True))
        batch.add_column(sa.Column("pipeline_state", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("provider_errors", sa.JSON(), nullable=False, server_default="{}"))
    with op.batch_alter_table("comparable_properties") as batch:
        batch.add_column(sa.Column("distance_miles", sa.Float(), nullable=True))
        batch.add_column(sa.Column("sale_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("price_per_square_foot", sa.Numeric(12, 2), nullable=True))
        batch.add_column(sa.Column("source", sa.String(255), nullable=False, server_default="Unavailable"))
        batch.add_column(sa.Column("confidence", sa.Float(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("verification_status", sa.String(20), nullable=False, server_default="unavailable"))
        batch.add_column(sa.Column("last_updated", sa.DateTime(timezone=True), nullable=True))

def downgrade():
    with op.batch_alter_table("comparable_properties") as batch:
        for col in ("last_updated", "verification_status", "confidence", "source", "price_per_square_foot", "sale_date", "distance_miles"): batch.drop_column(col)
    with op.batch_alter_table("properties") as batch:
        for col in ("provider_errors", "pipeline_state", "listing_status", "parcel_id", "year_built", "hoa"): batch.drop_column(col)
