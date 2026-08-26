import secrets
from flask import Blueprint, flash, redirect, render_template, request, url_for
from app.extensions import db
from app.models import SystemSetting, WebhookLog
from app.security import permission_required
from app.services.settings import get_setting

lead_webhook_settings_bp=Blueprint("lead_webhook_settings",__name__,url_prefix="/system-settings/lead-webhook")
BASE_KEYS=("lead_webhook_enabled","lead_webhook_secret","lead_webhook_default_source","lead_webhook_default_service_type","lead_webhook_duplicate_window_minutes","lead_webhook_pending_status","lead_webhook_verified_status")
FIELD_KEYS=("name","phone","device","issue","area","email","service_type","source","source_url","event_status")
KEYS=BASE_KEYS+tuple(f"lead_webhook_field_{key}" for key in FIELD_KEYS)
DEFAULTS={"lead_webhook_enabled":"0","lead_webhook_secret":"","lead_webhook_default_source":"Website","lead_webhook_default_service_type":"Doorstep","lead_webhook_duplicate_window_minutes":"120","lead_webhook_pending_status":"pending_otp","lead_webhook_verified_status":"verified","lead_webhook_field_name":"name","lead_webhook_field_phone":"contact_number","lead_webhook_field_device":"device","lead_webhook_field_issue":"issue","lead_webhook_field_area":"area","lead_webhook_field_email":"email","lead_webhook_field_service_type":"service_type","lead_webhook_field_source":"source","lead_webhook_field_source_url":"source_url","lead_webhook_field_event_status":"status"}
FIELD_LABELS={"name":"Lead Name","phone":"Phone / Contact Number","device":"Device / Model","issue":"Issue","area":"Area","email":"Email","service_type":"Service Type","source":"Lead Source","source_url":"Source URL","event_status":"OTP / Event Status"}

def _value(key): return get_setting(key,DEFAULTS.get(key,""))
def _save(key,value):
    row=SystemSetting.query.filter_by(key=key).first()
    if row is None: row=SystemSetting(key=key); db.session.add(row)
    row.value=value

@lead_webhook_settings_bp.route("/",methods=["GET","POST"])
@permission_required("system_settings")
def index():
    if request.method=="POST":
        _save("lead_webhook_enabled","1" if request.form.get("lead_webhook_enabled")=="1" else "0")
        for key in KEYS[1:]:
            value=request.form.get(key,"").strip()
            if key=="lead_webhook_secret" and not value: continue
            if key.startswith("lead_webhook_field_") and not value: continue
            _save(key,value)
        db.session.commit(); flash("Lead webhook settings saved","success"); return redirect(url_for("lead_webhook_settings.index"))
    settings={k:_value(k) for k in KEYS}; logs=WebhookLog.query.order_by(WebhookLog.created_at.desc()).limit(50).all()
    return render_template("system_settings/lead_webhook.html",settings=settings,logs=logs,field_keys=FIELD_KEYS,field_labels=FIELD_LABELS)

@lead_webhook_settings_bp.route("/generate-secret",methods=["POST"])
@permission_required("system_settings")
def generate_secret():
    secret=secrets.token_urlsafe(32); _save("lead_webhook_secret",secret); db.session.commit(); flash("New webhook secret generated. Copy it to your website plugin.","success"); return redirect(url_for("lead_webhook_settings.index",show_secret="1"))
