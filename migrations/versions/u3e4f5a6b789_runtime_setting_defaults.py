"""Normalize runtime service type defaults.
Revision ID: u3e4f5a6b789
Revises: t2d3e4f5a678
"""
from alembic import op
import sqlalchemy as sa
revision="u3e4f5a6b789";down_revision="t2d3e4f5a678";branch_labels=None;depends_on=None

def upgrade():
    conn=op.get_bind()
    for idx,value in enumerate(["Doorstep","In-Shop","Pickup/Drop"]):
        conn.execute(sa.text("INSERT OR IGNORE INTO setting_option (`group`, value, label, sort_order, active) VALUES ('service_types', :value, :value, :sort_order, 1)"),{"value":value,"sort_order":(idx+1)*10})
    conn.execute(sa.text("UPDATE setting_option SET active=0 WHERE `group`='service_types' AND value='In Store'"))

def downgrade():
    conn=op.get_bind();conn.execute(sa.text("DELETE FROM setting_option WHERE `group`='service_types' AND value IN ('In-Shop','Pickup/Drop')"));conn.execute(sa.text("UPDATE setting_option SET active=1 WHERE `group`='service_types' AND value='In Store'"))
