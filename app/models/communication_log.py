from datetime import datetime, timezone

from app.extensions import db


class CommunicationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.String(20), nullable=False, index=True)
    action = db.Column(db.String(30), nullable=False, default="opened")
    repair_id = db.Column(db.Integer, db.ForeignKey("repair_order.id"), nullable=True, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    mobile = db.Column(db.String(30), nullable=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    repair = db.relationship("RepairOrder")
    customer = db.relationship("Customer")
    user = db.relationship("User")
