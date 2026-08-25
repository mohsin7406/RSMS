from app.extensions import db


class RepairAuditLog(db.Model):
    __tablename__ = "repair_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    repair_id = db.Column(db.Integer, db.ForeignKey("repair_order.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    action = db.Column(db.String(50), nullable=False, index=True)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)

    repair = db.relationship("RepairOrder", backref=db.backref("audit_logs", lazy="dynamic", cascade="all, delete-orphan"))
    user = db.relationship("User")
