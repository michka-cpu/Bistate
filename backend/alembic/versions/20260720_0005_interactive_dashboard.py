"""interactive dashboard persistence

Revision ID: 20260720_0005
Revises: 20260719_0004
"""
from alembic import op
import sqlalchemy as sa
revision = "20260720_0005"
down_revision = "20260719_0004"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("properties") as batch:
        batch.add_column(sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table("property_activity_events", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False), sa.Column("event_type", sa.String(80), nullable=False), sa.Column("message", sa.Text(), nullable=False), sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
def downgrade():
    op.drop_table("property_activity_events")
    with op.batch_alter_table("properties") as batch:
        batch.drop_column("is_pinned"); batch.drop_column("is_favorite")
