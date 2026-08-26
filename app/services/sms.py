import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.models.notification_setting import NotificationSetting


EVENT_TEMPLATES = {
    "repair_created": "FixZone: Repair job {job_number} has been created for your {device}.",
    "received": "FixZone: Your {device} {job_number} has been received for repair.",
    "approval_required": "FixZone: Approval is required for your {device} repair {job_number}. Please contact us.",
    "technician_assigned": "FixZone: Technician assigned for your {device} repair {job_number}.",
    "repair_ready": "FixZone: Your {device} repair {job_number} is ready for collection/delivery.",
    "payment_received": "FixZone: Payment of ₹{amount} received for repair {job_number}. Thank you.",
    "delivered": "FixZone: Repair {job_number} has been delivered. Thank you for choosing FixZone.",
}


def _normalize_mobile(value):
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if digits.startswith("91") and len(digits) == 12:
        return digits
    if len(digits) == 10:
        return "91" + digits
    return digits


def _smsalert_setting():
    setting = NotificationSetting.query.filter_by(channel="sms").first()
    if not setting or not setting.enabled:
        return None
    if (setting.provider or "").strip().lower() not in {"smsalert", "smsalert.in", "sms alert"}:
        return None
    if not setting.api_key or not setting.sender_id:
        return None
    return setting


def send_sms(mobile, text, *, timeout=10):
    setting = _smsalert_setting()
    if setting is None:
        return {"ok": False, "skipped": True, "reason": "SMSAlert is not enabled/configured"}

    phone = _normalize_mobile(mobile)
    if not phone or len(phone) < 10:
        return {"ok": False, "skipped": True, "reason": "Invalid mobile number"}

    endpoint = (setting.api_url or "https://www.smsalert.co.in/api/push.json").strip()
    query = urlencode({
        "apikey": setting.api_key,
        "sender": setting.sender_id,
        "mobileno": phone,
        "text": text,
    })
    request = Request(f"{endpoint}?{query}", method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                data = {"raw": payload}
            return {"ok": response.status < 400, "status_code": response.status, "response": data}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def notify_customer(event, repair, **values):
    template = EVENT_TEMPLATES.get(event)
    if not template or not getattr(repair, "customer", None):
        return {"ok": False, "skipped": True, "reason": "No template/customer"}
    phone = getattr(repair.customer, "phone", None)
    text = template.format(job_number=repair.job_number, device=repair.device, **values)
    return send_sms(phone, text)
