from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models.notification_setting import NotificationSetting
from app.security import role_required

notifications_bp = Blueprint("notifications", __name__, url_prefix="/settings/notifications")


@notifications_bp.route("/", methods=["GET", "POST"])
@role_required("admin")
def settings():
    sms = NotificationSetting.query.filter_by(channel="sms").first()
    whatsapp = NotificationSetting.query.filter_by(channel="whatsapp").first()
    if request.method == "POST":
        for channel in ("sms", "whatsapp"):
            setting = sms if channel == "sms" else whatsapp
            if setting is None:
                setting = NotificationSetting(channel=channel)
                db.session.add(setting)
            setting.enabled = request.form.get(f"{channel}_enabled") == "on"
            setting.provider = request.form.get(f"{channel}_provider", "").strip() or None
            setting.api_url = request.form.get(f"{channel}_api_url", "").strip() or None
            setting.api_key = request.form.get(f"{channel}_api_key", "").strip() or setting.api_key
            setting.sender_id = request.form.get(f"{channel}_sender_id", "").strip() or None
            setting.account_id = request.form.get(f"{channel}_account_id", "").strip() or None
            setting.phone_number_id = request.form.get(f"{channel}_phone_number_id", "").strip() or None
            setting.access_token = request.form.get(f"{channel}_access_token", "").strip() or setting.access_token
        db.session.commit()
        flash("Notification settings saved", "success")
        return redirect(url_for("notifications.settings"))
    return render_template("settings/notifications.html", sms=sms, whatsapp=whatsapp)
