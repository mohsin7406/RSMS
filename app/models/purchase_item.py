from decimal import Decimal
from app.extensions import db


class PurchaseItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey("purchase.id"), nullable=False, index=True)
    part_id = db.Column(db.Integer, db.ForeignKey("part.id"), nullable=False, index=True)
    quantity = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0"))
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0"))
    purchase = db.relationship("Purchase", backref=db.backref("items", lazy=True, cascade="all, delete-orphan"))
    part = db.relationship("Part")

    @property
    def total(self):
        return self.quantity * self.unit_cost
