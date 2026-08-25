from app.extensions import db


class ServiceConfirmation(db.Model):
    __tablename__ = "service_confirmations"

    id = db.Column(db.Integer, primary_key=True)
    repair_id = db.Column(db.Integer, db.ForeignKey("repair_order.id"), unique=True, nullable=False, index=True)
    public_token = db.Column(db.String(96), unique=True, nullable=True, index=True)
    confirmation_type = db.Column(db.String(30), nullable=False, default="Customer Approval")
    customer_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    otp_verified = db.Column(db.Boolean, nullable=False, default=False)
    otp_hash = db.Column(db.String(255), nullable=True)
    otp_expires_at = db.Column(db.DateTime, nullable=True)
    otp_attempts = db.Column(db.Integer, nullable=False, default=0)
    confirmation_note = db.Column(db.Text, nullable=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    confirmed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    repair = db.relationship(
        "RepairOrder",
        backref=db.backref("service_confirmation", uselist=False, cascade="all, delete-orphan"),
    )
    confirmed_by = db.relationship("User")
