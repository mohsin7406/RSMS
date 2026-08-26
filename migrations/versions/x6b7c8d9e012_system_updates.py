"""Add system update history.
Revision ID: x6b7c8d9e012
Revises: w5a6b7c8d901
"""
from alembic import op
import sqlalchemy as sa
revision="x6b7c8d9e012"; down_revision="w5a6b7c8d901"; branch_labels=None; depends_on=None

def upgrade():
    op.create_table("system_update",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("version",sa.String(50),nullable=False),sa.Column("previous_version",sa.String(50)),sa.Column("filename",sa.String(255),nullable=False),sa.Column("package_path",sa.String(500),nullable=False),sa.Column("package_sha256",sa.String(64),nullable=False),sa.Column("status",sa.String(30),nullable=False,server_default="Uploaded"),sa.Column("changelog",sa.Text()),sa.Column("details",sa.Text()),sa.Column("backup_path",sa.String(500)),sa.Column("uploaded_by_id",sa.Integer(),sa.ForeignKey("user.id")),sa.Column("uploaded_at",sa.DateTime(),server_default=sa.func.now(),nullable=False),sa.Column("installed_at",sa.DateTime()))
    op.create_index("ix_system_update_version","system_update",["version"]); op.create_index("ix_system_update_status","system_update",["status"]); op.create_index("ix_system_update_uploaded_by_id","system_update",["uploaded_by_id"])

def downgrade():
    op.drop_index("ix_system_update_uploaded_by_id",table_name="system_update"); op.drop_index("ix_system_update_status",table_name="system_update"); op.drop_index("ix_system_update_version",table_name="system_update"); op.drop_table("system_update")
