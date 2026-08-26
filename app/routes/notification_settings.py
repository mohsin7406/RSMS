from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models.notification_setting import NotificationSetting
from app.models.notification_template import NotificationTemplate
from app.security import role_required
from app.services.smsalert import SMSAlertError, send_sms

notifications_bp = Blueprint("notifications", __name__, url_prefix="/settings/notifications")

TEMPLATE_EVENTS = (
    ("repair_created", "Repair Created"),
    ("received", "Repair Received"),
    ("approval_required", "Approval Required"),
    ("technician_assigned", "Technician Assigned"),
    ("repair_ready", "Repair Ready"),
    ("payment_received", "Payment Received"),
    ("delivered", "Delivered"),
)


@notifications_bp.route("/", methods=["GET", "POST"])
@role_required("admin")
def settings():
    sms = NotificationSetting.query.filter_by(channel="sms").first()
    whatsapp = NotificationSetting.query.filter_by(channel="whatsapp").first()
    templates = {
        event: NotificationTemplate.query.filter_by(channel="sms", event=event).first()
        for event, _label in TEMPLATE_EVENTS
    }
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

        for event, _label in TEMPLATE_EVENTS:
            template = templates[event]
            if template is None:
                template = NotificationTemplate(channel="sms", event=event, body="")
                db.session.add(template)
            template.enabled = request.form.get(f"template_{event}_enabled") == "on"
            body = request.form.get(f"template_{event}_body", "").strip()
            if body:
                template.body = body

        db.session.commit()
        flash("Notification settings saved", "success")
        return redirect(url_for("notifications.settings"))
    return render_template(
        "settings/notifications.html",
        sms=sms,
        whatsapp=whatsapp,
        templates=templates,
        template_events=TEMPLATE_EVENTS,
    )


@notifications_bp.post("/test-sms")
@role_required("admin")
def test_sms():
    setting = NotificationSetting.query.filter_by(channel="sms").first()
    mobile = request.form.get("mobile", "").strip()
    text = request.form.get("text", "RSMS SMS test").strip()

    if not setting or not setting.enabled:
        flash("SMS is not enabled", "error")
        return redirect(url_for("notifications.settings"))
    if not setting.provider or setting.provider.lower() != "smsalert.in":
        flash("SMS provider must be SMSAlert.in", "error")
        return redirect(url_for("notifications.settings"))

    try:
        result = send_sms(
            api_key=setting.api_key or "",
            sender=setting.sender_id or "",
            mobile=mobile,
            text=text,
            api_url=setting.api_url,
        )
    except SMSAlertError as exc:
        flash(str(exc), "error")
        return redirect(url_for("notifications.settings"))

    flash(f"SMSAlert request accepted (HTTP {result.status_code})", "success")
    return redirect(url_for("notifications.settings"))
