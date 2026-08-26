from app.extensions import db


class PartUsageReturn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usage_id = db.Column(db.Integer, db.ForeignKey("part_usage.id"), nullable=False, index=True)
    quantity = db.Column(db.Numeric(12, 2), nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    processed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)

    usage = db.relationship(
        "PartUsage",
        backref=db.backref("returns", lazy=True, cascade="all, delete-orphan"),
    )
    processed_by = db.relationship("User", foreign_keys=[processed_by_id])
