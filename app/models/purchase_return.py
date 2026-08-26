from decimal import Decimal
from app.extensions import db


class PurchaseReturn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    return_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey("purchase.id"), nullable=False, index=True)
    purchase_item_id = db.Column(db.Integer, db.ForeignKey("purchase_item.id"), nullable=False, index=True)
    quantity = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0"))
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0"))
    reason = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)
    purchase = db.relationship("Purchase", backref=db.backref("returns", lazy=True))
    purchase_item = db.relationship("PurchaseItem", backref=db.backref("returns", lazy=True))
    creator = db.relationship("User")

    @property
    def total(self):
        return self.quantity * self.unit_cost
