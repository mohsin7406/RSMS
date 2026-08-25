from decimal import Decimal

from app.extensions import db


class PartUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    repair_id = db.Column(db.Integer, db.ForeignKey("repair_order.id"), nullable=False, index=True)
    part_id = db.Column(db.Integer, db.ForeignKey("part.id"), nullable=False, index=True)
    quantity = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("1"))
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0"))
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0"))
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    repair = db.relationship("RepairOrder", backref=db.backref("parts_used", lazy=True, cascade="all, delete-orphan"))
    part = db.relationship("Part")

    @property
    def cost_total(self):
        return self.quantity * self.unit_cost

    @property
    def sale_total(self):
        return self.quantity * self.unit_price
