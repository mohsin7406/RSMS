from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy import or_

from app.extensions import db
from app.models import Customer, RepairOrder, RepairAuditLog, Part, PartUsage, StockMovement, User
from app.models.notification_template import NotificationTemplate
from app.models.repair import REPAIR_STATUSES, PAYMENT_STATUSES
from app.models.qc import RepairQC
from app.security import current_user_id, login_required, role_required

repair_bp = Blueprint("repair", __name__, url_prefix="/repairs")

REPAIR_TRANSITIONS = {
    "Pending": {"Received", "Cancelled"},
    "Received": {"Diagnosing", "Cancelled"},
    "Diagnosing": {"Waiting Approval", "Approved", "Cancelled"},
    "Waiting Approval": {"Approved", "Cancelled"},
    "Approved": {"Waiting Parts", "In Repair", "Cancelled"},
    "Waiting Parts": {"In Repair", "Cancelled"},
    "In Progress": {"In Repair", "QC", "Cancelled"},
    "In Repair": {"QC", "Cancelled"},
    "QC": {"In Repair", "Ready", "Cancelled"},
    "Ready": {"Delivered", "In Repair"},
    "Completed": {"Delivered", "In Repair"},
    "Delivered": set(),
    "Cancelled": set(),
}

WHATSAPP_WEB_DEFAULT = (
    "Hi {customer_name}, your FixZone repair {job_number} for {device} "
    "is currently {status}."
)


def _audit(repair, action, old_value=None, new_value=None):
    db.session.add(
        RepairAuditLog(
            repair=repair,
            user_id=current_user_id(),
            action=action,
            old_value=old_value,
            new_value=new_value,
        )
    )


def _money(value):
    try:
        amount = Decimal(value or "0")
        return amount if amount >= 0 else Decimal("0")
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _repair_values():
    return {
        "customer_id": request.form.get("customer_id", type=int),
        "device": request.form.get("device", "").strip(),
        "brand": request.form.get("brand", "").strip() or None,
        "model": request.form.get("model", "").strip() or None,
        "imei": request.form.get("imei", "").strip() or None,
        "serial_number": request.form.get("serial_number", "").strip() or None,
        "issue_description": request.form.get("issue_description", "").strip(),
        "diagnosis": request.form.get("diagnosis", "").strip() or None,
        "repair_notes": request.form.get("repair_notes", "").strip() or None,
        "status": request.form.get("status", "Pending"),
        "priority": request.form.get("priority", "Normal"),
        "service_type": request.form.get("service_type", "In-Shop"),
        "estimated_amount": _money(request.form.get("estimated_amount")),
        "final_amount": _money(request.form.get("final_amount")),
        "amount_paid": _money(request.form.get("amount_paid")),
        "payment_status": request.form.get("payment_status", "Unpaid"),
        "payment_method": request.form.get("payment_method", "").strip() or None,
        "customer_approved": request.form.get("customer_approved") == "on",
        "warranty_days": max(request.form.get("warranty_days", 0, type=int), 0),
        "assigned_technician_id": request.form.get("assigned_technician_id", type=int),
    }


def _validate_repair(values):
    if not values["customer_id"] or not values["device"] or not values["issue_description"]:
        return "Customer, device and issue description are required"
    if values["status"] not in REPAIR_STATUSES:
        return "Invalid repair status"
    if values["payment_status"] not in PAYMENT_STATUSES:
        return "Invalid payment status"
    if not db.session.get(Customer, values["customer_id"]):
        return "Selected customer does not exist"
    if values["assigned_technician_id"] is not None:
        technician = User.query.filter_by(id=values["assigned_technician_id"], role="technician").first()
        if technician is None:
            return "Selected technician is invalid"
    if values["amount_paid"] > values["final_amount"] and values["final_amount"] > 0:
        return "Amount paid cannot exceed final amount"
    return None


def _new_job_number():
    prefix = datetime.now(timezone.utc).strftime("JOB-%Y%m%d")
    latest = RepairOrder.query.filter(RepairOrder.job_number.like(f"{prefix}-%")).order_by(RepairOrder.id.desc()).first()
    sequence = int(latest.job_number.rsplit("-", 1)[-1]) + 1 if latest and latest.job_number.rsplit("-", 1)[-1].isdigit() else 1
    return f"{prefix}-{sequence:04d}"


def _delivery_allowed(repair):
    if repair.status == "Delivered":
        return True, None
    if repair.status != "Ready":
        return False, "Repair must be Ready before delivery"
    qc = RepairQC.query.filter_by(repair_id=repair.id).first()
    if qc is None or qc.after_status not in {"Passed", "Waived"}:
        return False, "QC After Repair must be passed or waived before delivery"
    if repair.final_amount > 0 and repair.payment_status != "Paid":
        return False, "Invoice must be fully paid before delivery"
    return True, None


def _whatsapp_message(repair):
    template = NotificationTemplate.query.filter_by(channel="whatsapp_web", event="repair_message").first()
    body = template.body if template and template.enabled and template.body else WHATSAPP_WEB_DEFAULT
    values = {
        "customer_name": repair.customer.name,
        "job_number": repair.job_number,
        "device": repair.device,
        "status": repair.status,
        "amount": f"{repair.final_amount:.2f}",
        "amount_paid": f"{repair.amount_paid:.2f}",
        "payment_status": repair.payment_status,
    }
    try:
        return body.format(**values)
    except (KeyError, ValueError):
        return WHATSAPP_WEB_DEFAULT.format(**values)


@repair_bp.route("/")
@repair_bp.route("/list")
@login_required
def list_repairs():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    query = RepairOrder.query.filter(RepairOrder.deleted_at.is_(None)).join(Customer)
    if q:
        query = query.filter(or_(Customer.name.ilike(f"%{q}%"), RepairOrder.job_number.ilike(f"%{q}%"), RepairOrder.device.ilike(f"%{q}%"), RepairOrder.imei.ilike(f"%{q}%")))
    if status:
        if status not in REPAIR_STATUSES:
            flash("Invalid status filter", "error")
        else:
            query = query.filter(RepairOrder.status == status)
    return render_template("repairs/list.html", repairs=query.order_by(RepairOrder.created_at.desc()).all())


@repair_bp.route("/add", methods=["GET", "POST"])
@role_required("admin", "staff")
def add_repair():
    customers = Customer.query.order_by(Customer.name.asc()).all()
    technicians = User.query.filter_by(role="technician").order_by(User.email.asc()).all()
    if request.method == "POST":
        values = _repair_values()
        error = _validate_repair(values)
        if error:
            flash(error, "error")
            return render_template("repairs/form.html", customers=customers, technicians=technicians, action="Add")
        values["job_number"] = _new_job_number()
        repair = RepairOrder(**values)
        db.session.add(repair)
        db.session.flush()
        _audit(repair, "created", None, repair.job_number)
        db.session.commit()
        flash(f"Repair order {repair.job_number} created", "success")
        return redirect(url_for("repair.view_repair", id=repair.id))
    return render_template("repairs/form.html", customers=customers, technicians=technicians, action="Add")


@repair_bp.route("/edit/<int:id>", methods=["GET", "POST"])
@role_required("admin", "staff")
def edit_repair(id):
    repair = db.session.get(RepairOrder, id)
    if repair is None:
        from flask import abort
        abort(404)
    customers = Customer.query.order_by(Customer.name.asc()).all()
    technicians = User.query.filter_by(role="technician").order_by(User.email.asc()).all()
    if request.method == "POST":
        values = _repair_values()
        error = _validate_repair(values)
        if error:
            flash(error, "error")
            return render_template("repairs/form.html", repair=repair, customers=customers, technicians=technicians, action="Edit")
        for key, value in values.items():
            old = getattr(repair, key)
            if old != value:
                _audit(repair, key, str(old), str(value))
                setattr(repair, key, value)
        db.session.commit()
        flash("Repair order updated", "success")
        return redirect(url_for("repair.view_repair", id=id))
    return render_template("repairs/form.html", repair=repair, customers=customers, technicians=technicians, action="Edit")


@repair_bp.route("/delete/<int:id>", methods=["POST"])
@role_required("admin")
def delete_repair(id):
    repair = RepairOrder.query.get_or_404(id)
    repair.deleted_at = datetime.now(timezone.utc)
    _audit(repair, "archived", None, repair.deleted_at.isoformat())
    db.session.commit()
    flash("Repair order archived", "success")
    return redirect(url_for("repair.list_repairs"))


@repair_bp.route("/view/<int:id>")
@login_required
def view_repair(id):
    repair = RepairOrder.query.filter(RepairOrder.id == id, RepairOrder.deleted_at.is_(None)).first_or_404()
    if g.current_user and g.current_user.role == "technician" and repair.assigned_technician_id != g.current_user.id:
        return ("Forbidden", 403)
    qc = RepairQC.query.filter_by(repair_id=repair.id).first()
    return render_template("repairs/detail.html", repair=repair, qc=qc, whatsapp_message=_whatsapp_message(repair))


@repair_bp.route("/audit/<int:id>")
@role_required("admin", "staff")
def repair_audit(id):
    repair = RepairOrder.query.get_or_404(id)
    logs = repair.audit_logs.order_by(RepairAuditLog.created_at.desc()).all()
    return render_template("repairs/audit.html", repair=repair, logs=logs)


@repair_bp.route("/customer/<int:customer_id>")
@login_required
def repairs_by_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    repairs = RepairOrder.query.filter_by(customer_id=customer_id).filter(RepairOrder.deleted_at.is_(None)).order_by(RepairOrder.created_at.desc()).all()
    return render_template("repairs/customer_repairs.html", customer=customer, repairs=repairs)


@repair_bp.route("/status/<status>")
@login_required
def repairs_by_status(status):
    if status not in REPAIR_STATUSES:
        flash("Invalid repair status", "error")
        return redirect(url_for("repair.list_repairs"))
    repairs = RepairOrder.query.filter_by(status=status).filter(RepairOrder.deleted_at.is_(None)).order_by(RepairOrder.created_at.desc()).all()
    return render_template("repairs/status_repairs.html", status=status, repairs=repairs)


@repair_bp.route("/update_status/<int:id>", methods=["POST"])
@role_required("admin", "staff", "technician")
def update_repair_status(id):
    repair = RepairOrder.query.filter(RepairOrder.id == id, RepairOrder.deleted_at.is_(None)).first_or_404()
    new_status = request.form.get("status", "")
    if g.current_user and g.current_user.role == "technician" and repair.assigned_technician_id != g.current_user.id:
        return ("Forbidden", 403)
    if new_status not in REPAIR_STATUSES:
        flash("Invalid repair status", "error")
        return redirect(url_for("repair.view_repair", id=id))
    if new_status != repair.status and new_status not in REPAIR_TRANSITIONS.get(repair.status, set()):
        flash(f"Invalid status transition: {repair.status} → {new_status}", "error")
        return redirect(url_for("repair.view_repair", id=id))

    qc = RepairQC.query.filter_by(repair_id=repair.id).first()
    if new_status == "In Repair" and (qc is None or qc.before_status not in {"Passed", "Waived"}):
        flash("QC Before Repair must be passed or waived before repair work can start", "error")
        return redirect(url_for("repair.view_repair", id=id))
    if new_status == "Ready" and (qc is None or qc.after_status not in {"Passed", "Waived"}):
        flash("QC After Repair must be passed or waived before the repair can be marked Ready", "error")
        return redirect(url_for("repair.view_repair", id=id))
    if new_status == "Delivered":
        allowed, reason = _delivery_allowed(repair)
        if not allowed:
            flash(reason, "error")
            return redirect(url_for("repair.view_repair", id=id))
    old_status = repair.status
    if old_status == new_status:
        flash("Repair order is already in this status", "success")
        return redirect(url_for("repair.view_repair", id=id))
    repair.status = new_status
    if new_status == "Delivered" and repair.delivered_at is None:
        repair.delivered_at = datetime.now(timezone.utc)
    _audit(repair, "status_changed", old_status, new_status)
    db.session.commit()
    flash("Repair order status updated", "success")
    return redirect(url_for("repair.view_repair", id=id))


@repair_bp.route("/<int:repair_id>/parts/add", methods=["POST"])
@role_required("admin", "staff", "technician")
def add_part_to_repair(repair_id):
    repair = RepairOrder.query.filter(RepairOrder.id == repair_id, RepairOrder.deleted_at.is_(None)).first_or_404()
    if g.current_user and g.current_user.role == "technician" and repair.assigned_technician_id != g.current_user.id:
        return ("Forbidden", 403)
    part = Part.query.filter_by(id=request.form.get("part_id", type=int), active=True).with_for_update().first_or_404()
    quantity = _money(request.form.get("quantity"))
    if quantity <= 0:
        flash("Quantity must be greater than zero", "error")
        return redirect(url_for("repair.view_repair", id=repair_id))
    if part.quantity < quantity:
        flash(f"Insufficient stock for {part.name}", "error")
        return redirect(url_for("repair.view_repair", id=repair_id))
    unit_cost = part.cost_price
    unit_price = _money(request.form.get("unit_price")) or part.selling_price
    try:
        part.quantity -= quantity
        db.session.add(PartUsage(repair_id=repair.id, part_id=part.id, quantity=quantity, unit_cost=unit_cost, unit_price=unit_price))
        db.session.add(StockMovement(part_id=part.id, user_id=current_user_id(), movement_type="OUT", quantity=quantity, reference=repair.job_number, notes="Used on repair"))
        _audit(repair, "part_added", None, f"{part.sku} x {quantity}")
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    flash(f"{part.name} added to {repair.job_number}", "success")
    return redirect(url_for("repair.view_repair", id=repair_id))


@repair_bp.route("/search", methods=["GET"])
@login_required
def search_repairs():
    return redirect(url_for("repair.list_repairs", q=request.args.get("q", "").strip()))
