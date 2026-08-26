import json
import re
from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from flask import Blueprint, jsonify, request
from app.extensions import db, limiter
from app.models import Lead, WebhookLog
from app.services.settings import get_bool, get_int, get_setting

lead_webhook_bp=Blueprint("lead_webhook",__name__,url_prefix="/api/webhooks/leads")
FIELD_DEFAULTS={"name":"name","phone":"contact_number","device":"device","issue":"issue","area":"area","email":"email","service_type":"service_type","source":"source","source_url":"source_url","event_status":"status"}
def _field(data,target):
    incoming=get_setting(f"lead_webhook_field_{target}",FIELD_DEFAULTS[target]).strip() or FIELD_DEFAULTS[target]
    return data.get(incoming)
def _phone(value):
    digits=re.sub(r"\D","",str(value or ""))
    if len(digits)==12 and digits.startswith("91"): digits=digits[2:]
    if len(digits)==11 and digits.startswith("0"): digits=digits[1:]
    return digits
def _payload():
    if request.is_json:return request.get_json(silent=True) or {}
    return request.form.to_dict(flat=True)
def _log(data,lead,result,code,message):
    safe={k:v for k,v in data.items() if k.lower() not in {"token","webhook_token","secret","api_key"}}
    row=WebhookLog(endpoint="elementor",event_status=str(_field(data,"event_status") or "")[:40],phone=_phone(_field(data,"phone")),source_url=_field(data,"source_url"),lead_id=lead.id if lead else None,result=result,response_code=code,payload=json.dumps(safe,ensure_ascii=False)[:12000],message=message); db.session.add(row); db.session.commit()
def _authorized(data):
    configured=get_setting("lead_webhook_secret","")
    if not configured:return False
    supplied=request.headers.get("X-RSMS-Webhook-Token") or data.get("webhook_token") or request.args.get("token") or ""
    return bool(supplied and compare_digest(str(supplied),str(configured)))
@lead_webhook_bp.route("/elementor",methods=["POST"])
@limiter.limit("60 per minute")
def elementor():
    data=_payload()
    if not get_bool("lead_webhook_enabled",False): _log(data,None,"disabled",503,"Lead webhook is disabled"); return jsonify(ok=False,error="webhook_disabled"),503
    if not _authorized(data): _log(data,None,"unauthorized",401,"Invalid webhook token"); return jsonify(ok=False,error="unauthorized"),401
    name=str(_field(data,"name") or "").strip(); phone=_phone(_field(data,"phone")); device=str(_field(data,"device") or "").strip() or None; issue=str(_field(data,"issue") or "").strip() or None; area=str(_field(data,"area") or "").strip() or None; email=str(_field(data,"email") or "").strip().lower() or None; source_url=str(_field(data,"source_url") or "").strip() or None; incoming_service=str(_field(data,"service_type") or "").strip(); incoming_source=str(_field(data,"source") or "").strip(); event=str(_field(data,"event_status") or "").strip().lower()
    pending_name=get_setting("lead_webhook_pending_status","pending_otp").strip().lower(); verified_name=get_setting("lead_webhook_verified_status","verified").strip().lower()
    if event not in {pending_name,verified_name}: _log(data,None,"rejected",400,"Unknown webhook status"); return jsonify(ok=False,error="invalid_status"),400
    if not name or len(phone)<10: _log(data,None,"rejected",400,"Name and valid contact number are required"); return jsonify(ok=False,error="missing_required_fields"),400
    window=max(get_int("lead_webhook_duplicate_window_minutes",120),1); cutoff=datetime.now(timezone.utc)-timedelta(minutes=window); query=Lead.query.filter(Lead.phone==phone,Lead.created_at>=cutoff)
    if source_url:query=query.filter(Lead.source_url==source_url)
    lead=query.order_by(Lead.created_at.desc()).first(); result="updated" if lead else "created"
    if lead is None:
        lead=Lead(name=name,phone=phone,email=email,device=device,issue=issue,area=area,source=incoming_source or get_setting("lead_webhook_default_source","Website") or "Website",source_url=source_url,service_type=incoming_service or get_setting("lead_webhook_default_service_type","Doorstep") or "Doorstep",status="New"); db.session.add(lead); db.session.flush()
    else:
        lead.name=name or lead.name; lead.email=email or lead.email; lead.device=device or lead.device; lead.issue=issue or lead.issue; lead.area=area or lead.area; lead.source_url=source_url or lead.source_url
        if incoming_service:lead.service_type=incoming_service
        if incoming_source:lead.source=incoming_source
    lead.otp_status=event
    if event==verified_name:lead.otp_verified_at=datetime.now(timezone.utc)
    db.session.commit(); _log(data,lead,result,200,f"Lead {result}; OTP status {event}"); return jsonify(ok=True,lead_id=lead.id,result=result,otp_status=lead.otp_status,verified=bool(lead.otp_verified_at)),200
