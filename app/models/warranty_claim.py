from datetime import datetime

from app.extensions import db


WARRANTY_STATUSES = ("Open", "Approved", "Rejected", "Resolved", "Closed")


class WarrantyClaim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    repair_id = db.Column(db.Integer, db.ForeignKey("repair_order.id"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="Open", index=True)
    issue = db.Column(db.Text, nullable=False)
    resolution = db.Column(db.Text, nullable=True)
    opened_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    handled_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)

    repair = db.relationship("RepairOrder", backref=db.backref("warranty_claims", lazy=True))
    customer = db.relationship("Customer")
    handled_by = db.relationship("User")
