from app.extensions import db


PHOTO_TYPES = ("Before", "During", "After", "Other")


class RepairPhoto(db.Model):
    __tablename__ = "repair_photos"

    id = db.Column(db.Integer, primary_key=True)
    repair_id = db.Column(db.Integer, db.ForeignKey("repair_order.id"), nullable=False, index=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    photo_type = db.Column(db.String(20), nullable=False, default="Other")
    file_path = db.Column(db.String(500), nullable=False)
    caption = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)

    repair = db.relationship("RepairOrder", backref=db.backref("photos", lazy=True, cascade="all, delete-orphan"))
    uploaded_by = db.relationship("User")
