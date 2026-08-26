from decimal import Decimal
from app.extensions import db


class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    purchase_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"), nullable=False, index=True)
    bill_number = db.Column(db.String(100), nullable=True, index=True)
    purchase_date = db.Column(db.Date, nullable=False, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    supplier = db.relationship("Supplier")
    creator = db.relationship("User")

    @property
    def total(self):
        return sum((line.quantity * line.unit_cost for line in self.items), Decimal("0"))
