import json
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from app.extensions import db
from app.models.notification_setting import NotificationSetting
from app.models.notification_template import NotificationTemplate
from app.models.sms_log import SMSLog
from app.services.settings import get_bool, get_setting

EVENT_TEMPLATES={"repair_created":"{business_name}: Repair job {job_number} has been created for your {device}.","received":"{business_name}: Your {device} {job_number} has been received for repair.","approval_required":"{business_name}: Approval is required for your {device} repair {job_number}. Please contact us.","technician_assigned":"{business_name}: Technician assigned for your {device} repair {job_number}.","repair_ready":"{business_name}: Your {device} repair {job_number} is ready for collection/delivery.","payment_received":"{business_name}: Payment of ₹{amount} received for repair {job_number}. Thank you.","delivered":"{business_name}: Repair {job_number} has been delivered. Thank you for choosing {business_name}."}
def _normalize_mobile(value):
    digits="".join(ch for ch in str(value or "") if ch.isdigit());country="".join(ch for ch in get_setting("default_country_code","91") if ch.isdigit()) or "91"
    if digits.startswith(country) and len(digits)>=10+len(country):return digits
    if len(digits)==10:return country+digits
    return digits
def _smsalert_setting():
    if not get_bool("sms_enabled"):return None
    setting=NotificationSetting.query.filter_by(channel="sms").first()
    if not setting or not setting.enabled:return None
    if (setting.provider or "").strip().lower() not in {"smsalert","smsalert.in","sms alert"}:return None
    if not setting.api_key or not setting.sender_id:return None
    return setting
def send_sms(mobile,text,*,timeout=10,repair_id=None,customer_id=None,event="manual"):
    setting=_smsalert_setting();phone=_normalize_mobile(mobile);signature=get_setting("notification_signature","").strip()
    if signature and not text.rstrip().endswith(signature):text=f"{text.rstrip()} {signature}"
    log=SMSLog(repair_id=repair_id,customer_id=customer_id,event=event,mobile=phone,message=text,provider=(setting.provider if setting else "smsalert.in"),status="skipped",attempts=1);db.session.add(log)
    if not get_bool("sms_enabled"):log.error="SMS is disabled in System Settings";db.session.commit();return {"ok":False,"skipped":True,"reason":log.error}
    if setting is None:log.error="SMSAlert is not enabled/configured";db.session.commit();return {"ok":False,"skipped":True,"reason":log.error}
    if not phone or len(phone)<10:log.error="Invalid mobile number";db.session.commit();return {"ok":False,"skipped":True,"reason":log.error}
    endpoint=(setting.api_url or "https://www.smsalert.co.in/api/push.json").strip();query=urlencode({"apikey":setting.api_key,"sender":setting.sender_id,"mobileno":phone,"text":text});req=Request(f"{endpoint}?{query}",method="POST")
    try:
        with urlopen(req,timeout=timeout) as response:
            payload=response.read().decode("utf-8",errors="replace")
            try:data=json.loads(payload)
            except json.JSONDecodeError:data={"raw":payload}
            log.provider_status=response.status;log.provider_response=json.dumps(data,ensure_ascii=False)[:10000];log.status="sent" if response.status<400 else "failed"
            if log.status=="sent":log.sent_at=datetime.now(timezone.utc)
            db.session.commit();return {"ok":response.status<400,"status_code":response.status,"response":data}
    except Exception as exc:
        log.status="failed";log.error=str(exc);db.session.commit();return {"ok":False,"error":str(exc)}
def notify_customer(event,repair,**values):
    if not get_bool("sms_enabled"):return {"ok":False,"skipped":True,"reason":"SMS disabled"}
    if not getattr(repair,"customer",None):return {"ok":False,"skipped":True,"reason":"No customer"}
    template=NotificationTemplate.query.filter_by(channel="sms",event=event).first()
    if template is not None:
        if not template.enabled:return {"ok":False,"skipped":True,"reason":"Notification template disabled"}
        text_template=template.body
    else:text_template=EVENT_TEMPLATES.get(event)
    if not text_template:return {"ok":False,"skipped":True,"reason":"No template"}
    format_values={"business_name":get_setting("business_name","FixZone"),"job_number":repair.job_number,"device":repair.device,**values}
    try:text=text_template.format(**format_values)
    except (KeyError,ValueError):return {"ok":False,"skipped":True,"reason":"Template variable error"}
    return send_sms(repair.customer.phone,text,repair_id=repair.id,customer_id=repair.customer.id,event=event)
