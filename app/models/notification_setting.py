from app.extensions import db


class NotificationSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.String(20), nullable=False, unique=True)
    enabled = db.Column(db.Boolean, nullable=False, default=False)
    provider = db.Column(db.String(50), nullable=True)
    api_url = db.Column(db.String(500), nullable=True)
    api_key = db.Column(db.Text, nullable=True)
    sender_id = db.Column(db.String(100), nullable=True)
    account_id = db.Column(db.String(200), nullable=True)
    phone_number_id = db.Column(db.String(200), nullable=True)
    access_token = db.Column(db.Text, nullable=True)
