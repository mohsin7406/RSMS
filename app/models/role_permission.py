from app.extensions import db


class RolePermission(db.Model):
    __tablename__ = "role_permission"

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(30), nullable=False, index=True)
    permission = db.Column(db.String(60), nullable=False, index=True)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("role", "permission", name="uq_role_permission_role_permission"),
    )
