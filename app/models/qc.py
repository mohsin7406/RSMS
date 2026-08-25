from app.extensions import db


QC_STATUSES = ("Pending", "Passed", "Failed", "Waived")


class RepairQC(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    repair_id = db.Column(db.Integer, db.ForeignKey("repair_order.id"), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    checklist = db.Column(db.JSON, nullable=False, default=dict)
    notes = db.Column(db.Text, nullable=True)
    tested_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    tested_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    repair = db.relationship("RepairOrder", backref=db.backref("qc", uselist=False))
    tested_by = db.relationship("User")
