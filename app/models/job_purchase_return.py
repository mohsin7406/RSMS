from decimal import Decimal

from app.extensions import db


class JobPurchaseReturn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey("job_purchase.id"), nullable=False, index=True)
    quantity = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0"))
    destination = db.Column(db.String(20), nullable=False, index=True)  # Inventory / Supplier
    inventory_part_id = db.Column(db.Integer, db.ForeignKey("part.id"), nullable=True, index=True)
    reason = db.Column(db.String(255), nullable=True)
    processed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)

    purchase = db.relationship(
        "JobPurchase",
        backref=db.backref("returns", lazy=True, cascade="all, delete-orphan"),
    )
    inventory_part = db.relationship("Part")
    processed_by = db.relationship("User", foreign_keys=[processed_by_id])

    @property
    def cost_total(self):
        return self.quantity * self.purchase.unit_cost if self.purchase else Decimal("0")
