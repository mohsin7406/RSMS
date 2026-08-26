from decimal import Decimal

from app.extensions import db


class RepairExtraCharge(db.Model):
    __tablename__ = "repair_extra_charge"

    id = db.Column(db.Integer, primary_key=True)
    repair_id = db.Column(db.Integer, db.ForeignKey("repair_order.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    description = db.Column(db.String(255), nullable=False)
    added_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)

    repair = db.relationship("RepairOrder", backref=db.backref("extra_charges", lazy=True, cascade="all, delete-orphan"))
    added_by = db.relationship("User", foreign_keys=[added_by_id])
