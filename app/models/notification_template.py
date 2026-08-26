from app.extensions import db


class NotificationTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.String(20), nullable=False, default="sms")
    event = db.Column(db.String(80), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    body = db.Column(db.Text, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("channel", "event", name="uq_notification_template_channel_event"),
    )
