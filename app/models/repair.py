from decimal import Decimal

from app.extensions import db
from app.models.customer import Customer


REPAIR_STATUSES = (
    "Pending",
    "Received",
    "Diagnosing",
    "Waiting Approval",
    "Approved",
    "Waiting Parts",
    "In Progress",
    "In Repair",
    "QC",
    "Ready",
    "Completed",
    "Delivered",
    "Cancelled",
)

PAYMENT_STATUSES = ("Unpaid", "Partially Paid", "Paid", "Refunded")


class RepairOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False, index=True)
    assigned_technician_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)

    device = db.Column(db.String(100), nullable=False, index=True)
    brand = db.Column(db.String(50), nullable=True, index=True)
    model = db.Column(db.String(100), nullable=True)
    imei = db.Column(db.String(20), nullable=True, index=True)
    serial_number = db.Column(db.String(100), nullable=True, index=True)
    issue_description = db.Column(db.Text, nullable=False)
    diagnosis = db.Column(db.Text, nullable=True)
    repair_notes = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(50), nullable=False, default="Pending", index=True)
    priority = db.Column(db.String(20), nullable=False, default="Normal", index=True)
    service_type = db.Column(db.String(30), nullable=False, default="In-Shop")

    estimated_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    final_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    amount_paid = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    payment_status = db.Column(db.String(30), nullable=False, default="Unpaid", index=True)
    payment_method = db.Column(db.String(30), nullable=True)

    customer_approved = db.Column(db.Boolean, nullable=False, default=False)
    warranty_days = db.Column(db.Integer, nullable=False, default=0)
    delivered_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)

    customer = db.relationship("Customer", backref=db.backref("repair_orders", lazy=True))
    assigned_technician = db.relationship("User", foreign_keys=[assigned_technician_id])

    def __repr__(self):
        return f"<RepairOrder {self.job_number}>"
