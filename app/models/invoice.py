from decimal import Decimal

from app.extensions import db


INVOICE_STATUSES = ("Draft", "Issued", "Partially Paid", "Paid", "Cancelled")


class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    repair_id = db.Column(db.Integer, db.ForeignKey("repair_order.id"), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False, index=True)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    discount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    tax = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    total = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    status = db.Column(db.String(30), nullable=False, default="Draft", index=True)
    issued_at = db.Column(db.DateTime, nullable=True)
    due_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    repair = db.relationship("RepairOrder", backref=db.backref("invoice", uselist=False))
    customer = db.relationship("Customer")
