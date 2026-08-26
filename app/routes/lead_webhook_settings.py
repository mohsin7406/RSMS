import secrets
from flask import Blueprint, flash, redirect, render_template, request, url_for
from app.extensions import db
from app.models import SystemSetting, WebhookLog
from app.security import permission_required
from app.services.settings import get_setting

lead_webhook_settings_bp=Blueprint("lead_webhook_settings",__name__,url_prefix="/system-settings/lead-webhook")
KEYS=("lead_webhook_enabled","lead_webhook_secret","lead_webhook_default_source","lead_webhook_default_service_type","lead_webhook_duplicate_window_minutes","lead_webhook_pending_status","lead_webhook_verified_status")
DEFAULTS={"lead_webhook_enabled":"0","lead_webhook_secret":"","lead_webhook_default_source":"Website","lead_webhook_default_service_type":"Doorstep","lead_webhook_duplicate_window_minutes":"120","lead_webhook_pending_status":"pending_otp","lead_webhook_verified_status":"verified"}

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
            _save(key,value)
        db.session.commit(); flash("Lead webhook settings saved","success"); return redirect(url_for("lead_webhook_settings.index"))
    settings={k:_value(k) for k in KEYS}; logs=WebhookLog.query.order_by(WebhookLog.created_at.desc()).limit(50).all()
    return render_template("system_settings/lead_webhook.html",settings=settings,logs=logs)

@lead_webhook_settings_bp.route("/generate-secret",methods=["POST"])
@permission_required("system_settings")
def generate_secret():
    secret=secrets.token_urlsafe(32); _save("lead_webhook_secret",secret); db.session.commit(); flash("New webhook secret generated. Update your website plugin before sending new leads.","success"); return redirect(url_for("lead_webhook_settings.index"))
