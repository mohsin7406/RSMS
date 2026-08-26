from app.extensions import db


class SystemUpdate(db.Model):
    __tablename__ = "system_update"

    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(50), nullable=False, index=True)
    previous_version = db.Column(db.String(50), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    package_sha256 = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="Uploaded", index=True)
    changelog = db.Column(db.Text, nullable=True)
    details = db.Column(db.Text, nullable=True)
    backup_path = db.Column(db.String(500), nullable=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    uploaded_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    installed_at = db.Column(db.DateTime, nullable=True)

    uploaded_by = db.relationship("User")
