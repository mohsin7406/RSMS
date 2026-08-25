from decimal import Decimal

from app.extensions import db


class Part(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    brand = db.Column(db.String(80), nullable=True)
    model = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(80), nullable=True, index=True)
    quantity = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0"))
    reorder_level = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0"))
    cost_price = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0"))
    selling_price = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0"))
    supplier = db.Column(db.String(150), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    def __repr__(self):
        return f"<Part {self.sku}>"
