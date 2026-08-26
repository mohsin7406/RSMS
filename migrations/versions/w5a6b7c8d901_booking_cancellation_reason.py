"""Add booking cancellation reason.
Revision ID: w5a6b7c8d901
Revises: v4f5a6b7c890
"""
from alembic import op
import sqlalchemy as sa

revision = "w5a6b7c8d901"
down_revision = "v4f5a6b7c890"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("booking", sa.Column("cancellation_reason", sa.String(length=160), nullable=True))


def downgrade():
    with op.batch_alter_table("booking") as batch_op:
        batch_op.drop_column("cancellation_reason")
