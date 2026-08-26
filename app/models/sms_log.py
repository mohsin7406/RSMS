from datetime import datetime, timezone

from app.extensions import db


class SMSLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    repair_id = db.Column(db.Integer, db.ForeignKey("repair_order.id"), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=True)
    event = db.Column(db.String(80), nullable=False)
    mobile = db.Column(db.String(30), nullable=True)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    provider = db.Column(db.String(50), nullable=True)
    provider_status = db.Column(db.Integer, nullable=True)
    provider_response = db.Column(db.Text, nullable=True)
    error = db.Column(db.Text, nullable=True)
    attempts = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    sent_at = db.Column(db.DateTime, nullable=True)
