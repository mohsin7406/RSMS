from app.extensions import db


LEAD_STATUSES = ("New", "Contacted", "Follow Up", "Booked", "Not Interested", "Lost")


class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=True)
    device = db.Column(db.String(100), nullable=True)
    issue = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(50), nullable=True, index=True)
    source_url = db.Column(db.Text, nullable=True)
    otp_status = db.Column(db.String(30), nullable=True, index=True)
    otp_verified_at = db.Column(db.DateTime, nullable=True)
    area = db.Column(db.String(120), nullable=True, index=True)
    service_type = db.Column(db.String(30), nullable=False, default="Doorstep")
    status = db.Column(db.String(30), nullable=False, default="New", index=True)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=True, index=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id])
    customer = db.relationship("Customer")
    booking = db.relationship("Booking", foreign_keys=[booking_id])
    contacts = db.relationship("LeadContact", back_populates="lead", cascade="all, delete-orphan", order_by="LeadContact.contacted_at.desc()")
