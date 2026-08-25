from decimal import Decimal

from app.extensions import db


class StockMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    part_id = db.Column(db.Integer, db.ForeignKey("part.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    movement_type = db.Column(db.String(30), nullable=False, index=True)
    quantity = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0"))
    reference = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)

    part = db.relationship("Part", backref=db.backref("stock_movements", lazy=True))
    user = db.relationship("User")
