from flask import Blueprint, render_template, request

from app.models.sms_log import SMSLog
from app.security import role_required

sms_logs_bp = Blueprint("sms_logs", __name__, url_prefix="/settings/sms-logs")


@sms_logs_bp.get("/")
@role_required("admin")
def list_logs():
    status = request.args.get("status", "").strip()
    query = SMSLog.query.order_by(SMSLog.created_at.desc())
    if status in {"sent", "failed", "skipped"}:
        query = query.filter_by(status=status)
    return render_template("settings/sms_logs.html", logs=query.limit(200).all(), status=status)
