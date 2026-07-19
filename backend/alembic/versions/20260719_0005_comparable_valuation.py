"""comparable valuation attributes

Revision ID: 20260719_0005
Revises: 20260719_0004
"""
from alembic import op
import sqlalchemy as sa
revision = "20260719_0005"
down_revision = "20260719_0004"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("comparable_properties") as batch:
        batch.add_column(sa.Column("acreage", sa.Float()))
        batch.add_column(sa.Column("bedrooms", sa.Float()))
        batch.add_column(sa.Column("bathrooms", sa.Float()))
        batch.add_column(sa.Column("year_built", sa.Integer()))
        batch.add_column(sa.Column("latitude", sa.Float()))
        batch.add_column(sa.Column("longitude", sa.Float()))
        batch.add_column(sa.Column("price_per_acre", sa.Numeric(12, 2)))
        batch.add_column(sa.Column("similarity_score", sa.Float()))

def downgrade():
    with op.batch_alter_table("comparable_properties") as batch:
        for column in ("similarity_score", "price_per_acre", "longitude", "latitude", "year_built", "bathrooms", "bedrooms", "acreage"): batch.drop_column(column)
