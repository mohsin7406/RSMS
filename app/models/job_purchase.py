from decimal import Decimal

from app.extensions import db


class JobPurchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    repair_id = db.Column(db.Integer, db.ForeignKey("repair_order.id"), nullable=False, index=True)
    item_name = db.Column(db.String(160), nullable=False)
    quantity = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("1"))
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0"))
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0"))
    supplier = db.Column(db.String(160), nullable=True)
    reference = db.Column(db.String(160), nullable=True)
    added_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)

    repair = db.relationship(
        "RepairOrder",
        backref=db.backref("job_purchases", lazy=True, cascade="all, delete-orphan"),
    )
    added_by = db.relationship("User", foreign_keys=[added_by_id])

    @property
    def cost_total(self):
        return self.quantity * self.unit_cost

    @property
    def sale_total(self):
        return self.quantity * self.unit_price
