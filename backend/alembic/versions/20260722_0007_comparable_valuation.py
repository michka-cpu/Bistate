"""add comparable valuation fields

Revision ID: 20260722_0007
Revises: 20260721_0006
"""
from alembic import op
import sqlalchemy as sa
revision = "20260722_0007"
down_revision = "20260721_0006"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("properties") as batch:
        batch.add_column(sa.Column("property_type", sa.String(100)))
        batch.add_column(sa.Column("valuation_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    with op.batch_alter_table("comparable_properties") as batch:
        batch.add_column(sa.Column("property_type", sa.String(100)))
        batch.add_column(sa.Column("bedrooms", sa.Float()))
        batch.add_column(sa.Column("bathrooms", sa.Float()))
        batch.add_column(sa.Column("acreage", sa.Float()))
        batch.add_column(sa.Column("similarity_score", sa.Float()))
        batch.add_column(sa.Column("adjustments", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch.add_column(sa.Column("provenance", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
def downgrade():
    with op.batch_alter_table("comparable_properties") as batch:
        batch.drop_column("provenance"); batch.drop_column("adjustments"); batch.drop_column("similarity_score"); batch.drop_column("acreage"); batch.drop_column("bathrooms"); batch.drop_column("bedrooms"); batch.drop_column("property_type")
    with op.batch_alter_table("properties") as batch:
        batch.drop_column("valuation_data"); batch.drop_column("property_type")
