from app.extensions import db


class WebhookLog(db.Model):
    __tablename__ = "webhook_log"

    id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.String(100), nullable=False, index=True)
    event_status = db.Column(db.String(40), nullable=True, index=True)
    phone = db.Column(db.String(30), nullable=True, index=True)
    source_url = db.Column(db.Text, nullable=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("lead.id"), nullable=True, index=True)
    result = db.Column(db.String(30), nullable=False, index=True)
    response_code = db.Column(db.Integer, nullable=False)
    payload = db.Column(db.Text, nullable=True)
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)

    lead = db.relationship("Lead")
