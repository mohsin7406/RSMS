from app.extensions import db


BOOKING_STATUSES = ("Scheduled", "Confirmed", "Assigned", "On The Way", "Started", "Completed", "Cancelled", "Rescheduled")


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False, index=True)
    technician_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    repair_id = db.Column(db.Integer, db.ForeignKey("repair_order.id"), nullable=True, index=True)
    service_type = db.Column(db.String(30), nullable=False, default="Doorstep")
    scheduled_at = db.Column(db.DateTime, nullable=False, index=True)
    address = db.Column(db.Text, nullable=True)
    area = db.Column(db.String(120), nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="Scheduled", index=True)
    cancellation_reason = db.Column(db.String(160), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    customer = db.relationship("Customer")
    technician = db.relationship("User", foreign_keys=[technician_id])
    repair = db.relationship("RepairOrder")
