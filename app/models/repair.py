from app.extensions import db
from app.models.customer import Customer


class RepairOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False, index=True)
    device = db.Column(db.String(100), nullable=False, index=True)
    issue_description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), nullable=False, default="Pending", index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)

    customer = db.relationship("Customer", backref=db.backref("repair_orders", lazy=True))
