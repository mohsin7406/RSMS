from flask import Blueprint, flash, redirect, render_template, request, url_for
from app.extensions import db
from app.models import QCChecklistItem, SettingOption, SystemSetting
from app.security import permission_required

settings_bp=Blueprint("system_settings",__name__,url_prefix="/system-settings")
SETTING_GROUPS={
"business":["business_name","business_tagline","business_phone","business_email","business_address","business_gstin","currency","timezone","date_format"],
"invoice":["invoice_terms","invoice_footer","invoice_prefix","payment_prefix","purchase_prefix","job_prefix","tax_enabled","default_tax_percent","default_warranty_days"],
"repair":["require_technician_assignment","require_qc_before","require_qc_after","require_payment_before_close","require_invoice_before_close","allow_qc_na","qc_failed_notes_required","qc_before_photo_required","qc_after_photo_required","qc_min_photos","qc_max_photos"],
"leads":["default_followup_days","booking_duration_minutes","booking_start_time","booking_end_time","service_area_notes"],
"inventory":["default_low_stock_threshold","allow_negative_stock","reservation_expiry_hours","technician_stock_enabled"],
"finance":["allow_partial_payments","allow_overpayments","refund_requires_manager","expense_approval_required"],
"notifications":["default_country_code","whatsapp_enabled","sms_enabled","notification_signature"],
"security":["session_timeout_minutes","max_login_attempts","audit_retention_days"],
"system":["pagination_size","max_upload_mb","allowed_image_extensions","maintenance_mode","data_retention_days"]}
SETTING_KEYS=tuple(k for values in SETTING_GROUPS.values() for k in values)
OPTION_GROUPS={"payment_methods":"Payment Methods","service_types":"Service Types","lead_sources":"Lead Sources","expense_categories":"Expense Categories","cancellation_reasons":"Cancellation Reasons","stock_adjustment_reasons":"Stock Adjustment Reasons"}
DEFAULTS={"business_name":"FixZone","currency":"INR","timezone":"Asia/Kolkata","date_format":"DD/MM/YYYY","invoice_prefix":"INV","payment_prefix":"PAY","purchase_prefix":"PUR","job_prefix":"JOB","default_warranty_days":"180","tax_enabled":"0","default_tax_percent":"0","require_technician_assignment":"1","require_qc_before":"1","require_qc_after":"1","require_payment_before_close":"1","require_invoice_before_close":"1","allow_qc_na":"1","qc_failed_notes_required":"1","qc_before_photo_required":"0","qc_after_photo_required":"0","qc_min_photos":"0","qc_max_photos":"10","default_followup_days":"1","booking_duration_minutes":"60","booking_start_time":"09:00","booking_end_time":"20:00","default_low_stock_threshold":"2","allow_negative_stock":"0","reservation_expiry_hours":"24","technician_stock_enabled":"1","allow_partial_payments":"1","allow_overpayments":"0","refund_requires_manager":"1","expense_approval_required":"0","default_country_code":"91","whatsapp_enabled":"1","sms_enabled":"1","session_timeout_minutes":"480","max_login_attempts":"5","audit_retention_days":"365","pagination_size":"50","max_upload_mb":"8","allowed_image_extensions":"jpg,jpeg,png,webp","maintenance_mode":"0","data_retention_days":"2555"}

def setting_value(key,default=""):
 row=SystemSetting.query.filter_by(key=key).first(); return row.value if row and row.value is not None else DEFAULTS.get(key,default)
def all_settings(): return {key:setting_value(key) for key in SETTING_KEYS}
def option_values(group,active_only=True):
 q=SettingOption.query.filter_by(group=group)
 if active_only:q=q.filter_by(active=True)
 return q.order_by(SettingOption.sort_order,SettingOption.id).all()

@settings_bp.route("/",methods=["GET","POST"])
@permission_required("system_settings")
def index():
 if request.method=="POST":
  for key in SETTING_KEYS:
   if key in request.form:
    value=request.form.get(key,"").strip()
   elif key in {"tax_enabled","require_technician_assignment","require_qc_before","require_qc_after","require_payment_before_close","require_invoice_before_close","allow_qc_na","qc_failed_notes_required","qc_before_photo_required","qc_after_photo_required","allow_negative_stock","technician_stock_enabled","allow_partial_payments","allow_overpayments","refund_requires_manager","expense_approval_required","whatsapp_enabled","sms_enabled","maintenance_mode"}: value="0"
   else: continue
   row=SystemSetting.query.filter_by(key=key).first()
   if row is None: row=SystemSetting(key=key); db.session.add(row)
   row.value=value
  db.session.commit(); flash("System settings saved","success"); return redirect(url_for("system_settings.index",tab=request.form.get("tab","business")))
 items=QCChecklistItem.query.order_by(QCChecklistItem.sort_order,QCChecklistItem.id).all(); options={g:option_values(g,False) for g in OPTION_GROUPS}
 return render_template("system_settings/index.html",settings=all_settings(),qc_items=items,options=options,option_groups=OPTION_GROUPS,tab=request.args.get("tab","business"))

@settings_bp.route("/option/add",methods=["POST"])
@permission_required("system_settings")
def add_option():
 group=request.form.get("group",""); label=request.form.get("label","").strip(); value=request.form.get("value","").strip() or label
 if group not in OPTION_GROUPS or not label: flash("Enter a valid option","error"); return redirect(url_for("system_settings.index",tab="options"))
 if SettingOption.query.filter_by(group=group,value=value).first(): flash("That option already exists","error"); return redirect(url_for("system_settings.index",tab="options"))
 max_order=db.session.query(db.func.max(SettingOption.sort_order)).filter_by(group=group).scalar() or 0; db.session.add(SettingOption(group=group,value=value,label=label,sort_order=max_order+10)); db.session.commit(); flash("Option added","success"); return redirect(url_for("system_settings.index",tab="options"))
@settings_bp.route("/option/<int:item_id>/edit",methods=["POST"])
@permission_required("system_settings")
def edit_option(item_id):
 item=db.session.get(SettingOption,item_id)
 if not item:return ("Not Found",404)
 item.label=request.form.get("label",item.label).strip() or item.label; item.sort_order=request.form.get("sort_order",item.sort_order,type=int); db.session.commit(); flash("Option updated","success"); return redirect(url_for("system_settings.index",tab="options"))
@settings_bp.route("/option/<int:item_id>/toggle",methods=["POST"])
@permission_required("system_settings")
def toggle_option(item_id):
 item=db.session.get(SettingOption,item_id)
 if not item:return ("Not Found",404)
 item.active=not item.active; db.session.commit(); flash("Option status updated","success"); return redirect(url_for("system_settings.index",tab="options"))
@settings_bp.route("/option/<int:item_id>/delete",methods=["POST"])
@permission_required("system_settings")
def delete_option(item_id):
 item=db.session.get(SettingOption,item_id)
 if not item:return ("Not Found",404)
 db.session.delete(item); db.session.commit(); flash("Option deleted. Existing historical records are unchanged.","success"); return redirect(url_for("system_settings.index",tab="options"))

@settings_bp.route("/qc/add",methods=["POST"])
@permission_required("system_settings")
def add_qc_item():
 label=request.form.get("label","").strip(); stage=request.form.get("stage","both")
 if stage not in {"before","after","both"}:stage="both"
 if not label:flash("QC checklist label is required","error");return redirect(url_for("system_settings.index",tab="qc"))
 max_order=db.session.query(db.func.max(QCChecklistItem.sort_order)).scalar() or 0; db.session.add(QCChecklistItem(label=label,stage=stage,sort_order=max_order+10,active=True)); db.session.commit(); flash("QC checklist item added","success"); return redirect(url_for("system_settings.index",tab="qc"))
@settings_bp.route("/qc/<int:item_id>/edit",methods=["POST"])
@permission_required("system_settings")
def edit_qc_item(item_id):
 item=db.session.get(QCChecklistItem,item_id)
 if not item:return ("Not Found",404)
 label=request.form.get("label","").strip();stage=request.form.get("stage","both")
 if not label or stage not in {"before","after","both"}:flash("Enter a valid QC label and stage","error");return redirect(url_for("system_settings.index",tab="qc"))
 item.label=label;item.stage=stage;item.sort_order=request.form.get("sort_order",item.sort_order,type=int);db.session.commit();flash("QC checklist item updated","success");return redirect(url_for("system_settings.index",tab="qc"))
@settings_bp.route("/qc/<int:item_id>/toggle",methods=["POST"])
@permission_required("system_settings")
def toggle_qc_item(item_id):
 item=db.session.get(QCChecklistItem,item_id)
 if not item:return ("Not Found",404)
 item.active=not item.active;db.session.commit();flash("QC checklist status updated","success");return redirect(url_for("system_settings.index",tab="qc"))
@settings_bp.route("/qc/<int:item_id>/delete",methods=["POST"])
@permission_required("system_settings")
def delete_qc_item(item_id):
 item=db.session.get(QCChecklistItem,item_id)
 if not item:return ("Not Found",404)
 db.session.delete(item);db.session.commit();flash("QC checklist item deleted. Historical completed QC records remain unchanged.","success");return redirect(url_for("system_settings.index",tab="qc"))
