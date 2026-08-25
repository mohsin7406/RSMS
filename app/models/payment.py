from decimal import Decimal

from app.extensions import db


PAYMENT_METHODS = ("Cash", "UPI", "Card", "Bank Transfer", "Other")
PAYMENT_TYPES = ("Payment", "Refund")


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payment_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    repair_id = db.Column(db.Integer, db.ForeignKey("repair_order.id"), nullable=False, index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoice.id"), nullable=True, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    payment_method = db.Column(db.String(30), nullable=False)
    payment_type = db.Column(db.String(20), nullable=False, default="Payment")
    reference = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    received_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)

    repair = db.relationship("RepairOrder", backref=db.backref("payments", lazy=True))
    invoice = db.relationship("Invoice", backref=db.backref("payments", lazy=True))
    received_by = db.relationship("User")
