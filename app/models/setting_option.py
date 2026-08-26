from app.extensions import db


class SettingOption(db.Model):
    __tablename__ = "setting_option"

    id = db.Column(db.Integer, primary_key=True)
    group = db.Column(db.String(50), nullable=False, index=True)
    value = db.Column(db.String(120), nullable=False)
    label = db.Column(db.String(160), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=100)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("group", "value", name="uq_setting_option_group_value"),
    )
