from app.extensions import db


class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=True)
    whatsapp = db.Column(db.String(30), nullable=True)
    gstin = db.Column(db.String(30), nullable=True)
    address = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)
