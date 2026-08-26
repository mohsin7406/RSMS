from app.models import SettingOption, SystemSetting

DEFAULTS={"business_name":"FixZone","business_tagline":"Mobile Repair at Your Doorstep","currency":"INR","timezone":"Asia/Kolkata","date_format":"DD/MM/YYYY","invoice_prefix":"INV","payment_prefix":"PAY","purchase_prefix":"PUR","job_prefix":"JOB","default_warranty_days":"180","tax_enabled":"0","default_tax_percent":"0","require_technician_assignment":"1","require_qc_before":"1","require_qc_after":"1","require_payment_before_close":"1","require_invoice_before_close":"1","allow_qc_na":"1","qc_failed_notes_required":"1","qc_before_photo_required":"0","qc_after_photo_required":"0","qc_min_photos":"0","qc_max_photos":"10","default_followup_days":"1","booking_duration_minutes":"60","booking_start_time":"09:00","booking_end_time":"20:00","default_low_stock_threshold":"2","allow_negative_stock":"0","reservation_expiry_hours":"24","technician_stock_enabled":"1","allow_partial_payments":"1","allow_overpayments":"0","refund_requires_manager":"1","expense_approval_required":"0","default_country_code":"91","whatsapp_enabled":"1","sms_enabled":"1","session_timeout_minutes":"480","max_login_attempts":"5","audit_retention_days":"365","pagination_size":"50","max_upload_mb":"8","allowed_image_extensions":"jpg,jpeg,png,webp","maintenance_mode":"0","data_retention_days":"2555"}
OPTION_DEFAULTS={"payment_methods":["Cash","UPI","Card","Bank Transfer","Other"],"service_types":["Doorstep","In-Shop","Pickup/Drop"],"lead_sources":["Website","Phone","WhatsApp","Google","Referral","Walk-in","Other"],"expense_categories":["Petrol","Porter","Technician Travel","Advertising","Office","Job Expense","Miscellaneous"],"cancellation_reasons":["Customer Cancelled","No Response","Price Issue","Duplicate","Out of Service Area","Part Unavailable","Other"],"stock_adjustment_reasons":["Physical Count","Damaged","Lost","Correction","Return","Other"]}

def get_setting(key,default=None):
    row=SystemSetting.query.filter_by(key=key).first()
    if row and row.value is not None:return row.value
    return DEFAULTS.get(key,"" if default is None else default)
def get_bool(key,default=False):return str(get_setting(key,"1" if default else "0")).strip().lower() in {"1","true","yes","on"}
def get_int(key,default=0):
    try:return int(get_setting(key,default))
    except (TypeError,ValueError):return default
def get_decimal(key,default="0"):
    from decimal import Decimal,InvalidOperation
    try:return Decimal(str(get_setting(key,default)))
    except (InvalidOperation,TypeError,ValueError):return Decimal(str(default))
def get_options(group,active_only=True,values_only=True):
    q=SettingOption.query.filter_by(group=group)
    if active_only:q=q.filter_by(active=True)
    rows=q.order_by(SettingOption.sort_order,SettingOption.id).all()
    if not rows and values_only:return list(OPTION_DEFAULTS.get(group,[]))
    return [r.value for r in rows] if values_only else rows
def option_allowed(group,value):return bool(value) and value in get_options(group)
def format_number(prefix_key,fallback_prefix,model,field,now):
    prefix=(get_setting(prefix_key,fallback_prefix) or fallback_prefix).strip().upper();today=now.strftime("%Y%m%d");stem=f"{prefix}-{today}";latest=model.query.filter(getattr(model,field).like(f"{stem}-%")).order_by(model.id.desc()).first();sequence=int(getattr(latest,field).rsplit("-",1)[-1])+1 if latest and getattr(latest,field).rsplit("-",1)[-1].isdigit() else 1;return f"{stem}-{sequence:04d}"
