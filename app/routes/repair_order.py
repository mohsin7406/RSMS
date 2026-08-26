from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import or_
from app.extensions import db
from app.models import Customer, RepairOrder, RepairAuditLog, Part, PartUsage, StockMovement, User
from app.models.notification_template import NotificationTemplate
from app.models.repair import REPAIR_STATUSES, PAYMENT_STATUSES
from app.models.qc import RepairQC
from app.security import current_user_id, permission_required, role_required
from app.services.settings import format_number, get_bool, get_int, get_options, get_setting

repair_bp=Blueprint("repair",__name__,url_prefix="/repairs")
REPAIR_TRANSITIONS={"Pending":{"Received","Cancelled"},"Received":{"Diagnosing","Cancelled"},"Diagnosing":{"Waiting Approval","Approved","Cancelled"},"Waiting Approval":{"Approved","Cancelled"},"Approved":{"Waiting Parts","In Repair","Cancelled"},"Waiting Parts":{"In Repair","Cancelled"},"In Progress":{"In Repair","QC","Cancelled"},"In Repair":{"QC","Cancelled"},"QC":{"In Repair","Ready","Cancelled"},"Ready":{"Delivered","In Repair"},"Completed":{"Delivered","In Repair"},"Delivered":set(),"Cancelled":set()}
DOORSTEP_STATUSES={"Pending","Approved","Completed","Cancelled"};DOORSTEP_TRANSITIONS={"Pending":{"Approved","Cancelled"},"Approved":{"Cancelled"},"Completed":set(),"Cancelled":set()}
WHATSAPP_WEB_DEFAULT="Hi {customer_name}, your {business_name} repair {job_number} for {device} is currently {status}."
def _audit(repair,action,old_value=None,new_value=None):db.session.add(RepairAuditLog(repair=repair,user_id=current_user_id(),action=action,old_value=old_value,new_value=new_value))
def _money(value):
    try:
        amount=Decimal(value or "0");return amount if amount>=0 else Decimal("0")
    except (InvalidOperation,ValueError):return Decimal("0")
def _repair_values():
    warranty_default=get_int("default_warranty_days",0)
    return {"customer_id":request.form.get("customer_id",type=int),"device":request.form.get("device","").strip(),"brand":request.form.get("brand","").strip() or None,"model":request.form.get("model","").strip() or None,"imei":request.form.get("imei","").strip() or None,"serial_number":request.form.get("serial_number","").strip() or None,"issue_description":request.form.get("issue_description","").strip(),"diagnosis":request.form.get("diagnosis","").strip() or None,"repair_notes":request.form.get("repair_notes","").strip() or None,"status":request.form.get("status","Pending"),"priority":request.form.get("priority","Normal"),"service_type":request.form.get("service_type","Doorstep"),"estimated_amount":_money(request.form.get("estimated_amount")),"final_amount":_money(request.form.get("final_amount")),"amount_paid":_money(request.form.get("amount_paid")),"payment_status":request.form.get("payment_status","Unpaid"),"payment_method":request.form.get("payment_method","").strip() or None,"customer_approved":request.form.get("customer_approved")=="on","warranty_days":max(request.form.get("warranty_days",warranty_default,type=int),0),"assigned_technician_id":request.form.get("assigned_technician_id",type=int)}
def _validate_repair(v):
    if not v["customer_id"] or not v["device"] or not v["issue_description"]:return "Customer, device and issue description are required"
    if v["status"] not in REPAIR_STATUSES:return "Invalid repair status"
    service_types=get_options("service_types")
    if service_types and v["service_type"] not in service_types:return "Invalid service type"
    if v["service_type"]=="Doorstep":
        if v["status"] not in DOORSTEP_STATUSES:return "Doorstep jobs use only Pending, Approved, Completed or Cancelled statuses"
        if v["status"]=="Approved" and get_bool("require_technician_assignment") and not v["assigned_technician_id"]:return "Assign a technician before approving a Doorstep job"
    if v["payment_status"] not in PAYMENT_STATUSES:return "Invalid payment status"
    if v["payment_method"] and v["payment_method"] not in get_options("payment_methods"):return "Invalid payment method"
    if not db.session.get(Customer,v["customer_id"]):return "Selected customer does not exist"
    if v["assigned_technician_id"] is not None and User.query.filter_by(id=v["assigned_technician_id"],role="technician").first() is None:return "Selected technician is invalid"
    payable=v["final_amount"] or v["estimated_amount"]
    if v["amount_paid"]>payable and payable>0 and not get_bool("allow_overpayments"):return "Amount paid cannot exceed payable amount"
    return None
def _new_job_number():return format_number("job_prefix","JOB",RepairOrder,"job_number",datetime.now(timezone.utc))
def _delivery_allowed(repair):
    if repair.status=="Delivered":return True,None
    if repair.status!="Ready":return False,"Repair must be Ready before delivery"
    qc=RepairQC.query.filter_by(repair_id=repair.id).first()
    if get_bool("require_qc_after") and (qc is None or qc.after_status not in {"Passed","Waived"}):return False,"QC After Repair must be passed or waived before delivery"
    if get_bool("require_invoice_before_close") and not repair.invoice:return False,"Create the invoice before delivery"
    if get_bool("require_payment_before_close") and repair.final_amount>0 and repair.payment_status!="Paid":return False,"Repair must be fully paid before delivery"
    return True,None
def _whatsapp_message(repair):
    if not get_bool("whatsapp_enabled"):return ""
    template=NotificationTemplate.query.filter_by(channel="whatsapp_web",event="repair_message").first();body=template.body if template and template.enabled and template.body else WHATSAPP_WEB_DEFAULT;values={"customer_name":repair.customer.name,"business_name":get_setting("business_name","FixZone"),"job_number":repair.job_number,"device":repair.device,"status":repair.status,"amount":f"{repair.final_amount:.2f}","amount_paid":f"{repair.amount_paid:.2f}","payment_status":repair.payment_status}
    try:return body.format(**values)
    except (KeyError,ValueError):return WHATSAPP_WEB_DEFAULT.format(**values)

@repair_bp.route("/")
@repair_bp.route("/list")
@permission_required("repairs_view")
def list_repairs():
    q=request.args.get("q","").strip();status=request.args.get("status","");query=RepairOrder.query.filter(RepairOrder.deleted_at.is_(None)).join(Customer)
    if g.current_user and g.current_user.role=="technician":query=query.filter(RepairOrder.assigned_technician_id==g.current_user.id)
    if q:query=query.filter(or_(Customer.name.ilike(f"%{q}%"),RepairOrder.job_number.ilike(f"%{q}%"),RepairOrder.device.ilike(f"%{q}%"),RepairOrder.imei.ilike(f"%{q}%")))
    if status:
        if status not in REPAIR_STATUSES:flash("Invalid status filter","error")
        else:query=query.filter(RepairOrder.status==status)
    return render_template("repairs/list.html",repairs=query.order_by(RepairOrder.created_at.desc()).all())
@repair_bp.route("/add",methods=["GET","POST"])
@permission_required("repairs_manage")
def add_repair():
    customers=Customer.query.order_by(Customer.name).all();technicians=User.query.filter_by(role="technician").order_by(User.email).all()
    if request.method=="POST":
        values=_repair_values();error=_validate_repair(values)
        if error:flash(error,"error");return render_template("repairs/form.html",customers=customers,technicians=technicians,action="Add")
        values["job_number"]=_new_job_number();repair=RepairOrder(**values);db.session.add(repair);db.session.flush();_audit(repair,"created",None,repair.job_number);db.session.commit();flash(f"Repair order {repair.job_number} created","success");return redirect(url_for("repair.view_repair",id=repair.id))
    return render_template("repairs/form.html",customers=customers,technicians=technicians,action="Add")
@repair_bp.route("/edit/<int:id>",methods=["GET","POST"])
@permission_required("repairs_manage")
def edit_repair(id):
    repair=db.session.get(RepairOrder,id)
    if repair is None:abort(404)
    if g.current_user and g.current_user.role=="technician":return ("Forbidden",403)
    customers=Customer.query.order_by(Customer.name).all();technicians=User.query.filter_by(role="technician").order_by(User.email).all()
    if request.method=="POST":
        values=_repair_values();error=_validate_repair(values)
        if error:flash(error,"error");return render_template("repairs/form.html",repair=repair,customers=customers,technicians=technicians,action="Edit")
        for key,value in values.items():
            old=getattr(repair,key)
            if old!=value:_audit(repair,key,str(old),str(value));setattr(repair,key,value)
        db.session.commit();flash("Repair order updated","success");return redirect(url_for("repair.view_repair",id=id))
    return render_template("repairs/form.html",repair=repair,customers=customers,technicians=technicians,action="Edit")
@repair_bp.route("/delete/<int:id>",methods=["POST"])
@role_required("admin")
def delete_repair(id):
    repair=db.session.get(RepairOrder,id)
    if repair is None:abort(404)
    repair.deleted_at=datetime.now(timezone.utc);_audit(repair,"archived",None,repair.deleted_at.isoformat());db.session.commit();flash("Repair order archived","success");return redirect(url_for("repair.list_repairs"))
@repair_bp.route("/view/<int:id>")
@permission_required("repairs_view")
def view_repair(id):
    repair=RepairOrder.query.filter(RepairOrder.id==id,RepairOrder.deleted_at.is_(None)).first_or_404()
    if g.current_user and g.current_user.role=="technician" and repair.assigned_technician_id!=g.current_user.id:return ("Forbidden",403)
    qc=RepairQC.query.filter_by(repair_id=repair.id).first();return render_template("repairs/detail.html",repair=repair,qc=qc,whatsapp_message=_whatsapp_message(repair))
@repair_bp.route("/audit/<int:id>")
@permission_required("audit")
def repair_audit(id):
    repair=db.session.get(RepairOrder,id)
    if repair is None:abort(404)
    return render_template("repairs/audit.html",repair=repair,logs=repair.audit_logs.order_by(RepairAuditLog.created_at.desc()).all())
@repair_bp.route("/customer/<int:customer_id>")
@permission_required("repairs_view")
def repairs_by_customer(customer_id):
    customer=db.session.get(Customer,customer_id)
    if customer is None:abort(404)
    query=RepairOrder.query.filter_by(customer_id=customer_id).filter(RepairOrder.deleted_at.is_(None))
    if g.current_user and g.current_user.role=="technician":query=query.filter(RepairOrder.assigned_technician_id==g.current_user.id)
    return render_template("repairs/customer_repairs.html",customer=customer,repairs=query.order_by(RepairOrder.created_at.desc()).all())
@repair_bp.route("/status/<status>")
@permission_required("repairs_view")
def repairs_by_status(status):
    if status not in REPAIR_STATUSES:flash("Invalid status filter","error");return redirect(url_for("repair.list_repairs"))
    query=RepairOrder.query.filter_by(status=status).filter(RepairOrder.deleted_at.is_(None))
    if g.current_user and g.current_user.role=="technician":query=query.filter(RepairOrder.assigned_technician_id==g.current_user.id)
    return render_template("repairs/status_repairs.html",status=status,repairs=query.order_by(RepairOrder.created_at.desc()).all())
@repair_bp.route("/update_status/<int:id>",methods=["POST"])
@permission_required("repairs_manage")
def update_repair_status(id):
    repair=RepairOrder.query.filter(RepairOrder.id==id,RepairOrder.deleted_at.is_(None)).first_or_404();new_status=request.form.get("status","")
    if g.current_user and g.current_user.role=="technician" and repair.assigned_technician_id!=g.current_user.id:return ("Forbidden",403)
    if new_status not in REPAIR_STATUSES:flash("Invalid repair status","error");return redirect(url_for("repair.view_repair",id=id))
    if repair.service_type=="Doorstep":
        if new_status not in DOORSTEP_STATUSES:flash("Doorstep jobs use Pending, Approved, Completed or Cancelled statuses","error");return redirect(url_for("repair.view_repair",id=id))
        if new_status=="Approved" and get_bool("require_technician_assignment") and not repair.assigned_technician_id:flash("Assign a technician before approving a Doorstep job","error");return redirect(url_for("repair.view_repair",id=id))
        if new_status!=repair.status and new_status not in DOORSTEP_TRANSITIONS.get(repair.status,set()):flash(f"Invalid Doorstep status transition: {repair.status} → {new_status}","error");return redirect(url_for("repair.view_repair",id=id))
    elif new_status!=repair.status and new_status not in REPAIR_TRANSITIONS.get(repair.status,set()):flash(f"Invalid status transition: {repair.status} → {new_status}","error");return redirect(url_for("repair.view_repair",id=id))
    qc=RepairQC.query.filter_by(repair_id=repair.id).first()
    if repair.service_type!="Doorstep":
        if new_status=="In Repair" and get_bool("require_qc_before") and (qc is None or qc.before_status not in {"Passed","Waived"}):flash("QC Before Repair must be passed or waived before repair work can start","error");return redirect(url_for("repair.view_repair",id=id))
        if new_status=="Ready" and get_bool("require_qc_after") and (qc is None or qc.after_status not in {"Passed","Waived"}):flash("QC After Repair must be passed or waived before the repair can be marked Ready","error");return redirect(url_for("repair.view_repair",id=id))
        if new_status=="Delivered":
            allowed,reason=_delivery_allowed(repair)
            if not allowed:flash(reason,"error");return redirect(url_for("repair.view_repair",id=id))
    old=repair.status
    if old==new_status:flash("Repair order is already in this status","success");return redirect(url_for("repair.view_repair",id=id))
    repair.status=new_status
    if new_status=="Delivered" and repair.delivered_at is None:repair.delivered_at=datetime.now(timezone.utc)
    _audit(repair,"status_changed",old,new_status);db.session.commit();flash("Repair order status updated","success");return redirect(url_for("repair.view_repair",id=id))
@repair_bp.route("/<int:repair_id>/parts/add",methods=["POST"])
@permission_required("repairs_manage")
def add_part_to_repair(repair_id):
    repair=RepairOrder.query.filter(RepairOrder.id==repair_id,RepairOrder.deleted_at.is_(None)).first_or_404()
    if g.current_user and g.current_user.role=="technician" and repair.assigned_technician_id!=g.current_user.id:return ("Forbidden",403)
    part=Part.query.filter_by(id=request.form.get("part_id",type=int),active=True).with_for_update().first_or_404();quantity=_money(request.form.get("quantity"))
    if quantity<=0:flash("Quantity must be greater than zero","error");return redirect(url_for("repair.view_repair",id=repair_id))
    if part.quantity<quantity and not get_bool("allow_negative_stock"):flash(f"Insufficient stock for {part.name}","error");return redirect(url_for("repair.view_repair",id=repair_id))
    unit_cost=part.cost_price;unit_price=_money(request.form.get("unit_price")) or part.selling_price
    try:
        part.quantity-=quantity;db.session.add(PartUsage(repair_id=repair.id,part_id=part.id,quantity=quantity,unit_cost=unit_cost,unit_price=unit_price));db.session.add(StockMovement(part_id=part.id,user_id=current_user_id(),movement_type="OUT",quantity=quantity,reference=repair.job_number,notes="Used on repair"));_audit(repair,"part_added",None,f"{part.sku} x {quantity}");db.session.commit()
    except Exception:
        db.session.rollback();raise
    flash(f"{part.name} added to {repair.job_number}","success");return redirect(url_for("repair.view_repair",id=repair_id))
@repair_bp.route("/search",methods=["GET"])
@permission_required("repairs_view")
def search_repairs():return redirect(url_for("repair.list_repairs",q=request.args.get("q","").strip()))
