from app.extensions import db


QC_STATUSES = ("Pending", "Passed", "Failed", "Waived")


class RepairQC(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    repair_id = db.Column(db.Integer, db.ForeignKey("repair_order.id"), unique=True, nullable=False, index=True)

    # Legacy/general QC fields retained for compatibility.
    status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    checklist = db.Column(db.JSON, nullable=False, default=dict)
    notes = db.Column(db.Text, nullable=True)
    tested_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    tested_at = db.Column(db.DateTime, nullable=True)

    # QC before repair work starts.
    before_status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    before_checklist = db.Column(db.JSON, nullable=False, default=dict)
    before_notes = db.Column(db.Text, nullable=True)
    before_tested_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    before_tested_at = db.Column(db.DateTime, nullable=True)
    before_photos = db.Column(db.JSON, nullable=False, default=list)

    # QC after repair work is completed.
    after_status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    after_checklist = db.Column(db.JSON, nullable=False, default=dict)
    after_notes = db.Column(db.Text, nullable=True)
    after_tested_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    after_tested_at = db.Column(db.DateTime, nullable=True)
    after_photos = db.Column(db.JSON, nullable=False, default=list)

    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    repair = db.relationship("RepairOrder", backref=db.backref("qc", uselist=False))
    tested_by = db.relationship("User", foreign_keys=[tested_by_id])
    before_tested_by = db.relationship("User", foreign_keys=[before_tested_by_id])
    after_tested_by = db.relationship("User", foreign_keys=[after_tested_by_id])
