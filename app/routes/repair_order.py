from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from app.extensions import db
from app.models import Customer, RepairOrder
from app.models.repair import REPAIR_STATUSES, PAYMENT_STATUSES
from app.security import login_required, role_required

repair_bp = Blueprint("repair", __name__, url_prefix="/repairs")


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
    if not Customer.query.get(values["customer_id"]):
        return "Selected customer does not exist"
    if values["amount_paid"] > values["final_amount"] and values["final_amount"] > 0:
        return "Amount paid cannot exceed final amount"
    return None


def _new_job_number():
    prefix = datetime.utcnow().strftime("JOB-%Y%m%d")
    latest = RepairOrder.query.filter(RepairOrder.job_number.like(f"{prefix}-%")).order_by(RepairOrder.id.desc()).first()
    sequence = int(latest.job_number.rsplit("-", 1)[-1]) + 1 if latest and latest.job_number.rsplit("-", 1)[-1].isdigit() else 1
    return f"{prefix}-{sequence:04d}"


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
    repairs = query.order_by(RepairOrder.created_at.desc()).all()
    return render_template("repairs/list.html", repairs=repairs)


@repair_bp.route("/add", methods=["GET", "POST"])
@role_required("admin", "staff")
def add_repair():
    customers = Customer.query.order_by(Customer.name.asc()).all()
    if request.method == "POST":
        values = _repair_values()
        error = _validate_repair(values)
        if error:
            flash(error, "error")
            return render_template("repairs/form.html", customers=customers, action="Add")
        values["job_number"] = _new_job_number()
        repair = RepairOrder(**values)
        db.session.add(repair)
        db.session.commit()
        flash(f"Repair order {repair.job_number} created", "success")
        return redirect(url_for("repair.view_repair", id=repair.id))
    return render_template("repairs/form.html", customers=customers, action="Add")


@repair_bp.route("/edit/<int:id>", methods=["GET", "POST"])
@role_required("admin", "staff")
def edit_repair(id):
    repair = RepairOrder.query.get_or_404(id)
    customers = Customer.query.order_by(Customer.name.asc()).all()
    if request.method == "POST":
        values = _repair_values()
        error = _validate_repair(values)
        if error:
            flash(error, "error")
            return render_template("repairs/form.html", repair=repair, customers=customers, action="Edit")
        for key, value in values.items():
            setattr(repair, key, value)
        db.session.commit()
        flash("Repair order updated", "success")
        return redirect(url_for("repair.view_repair", id=id))
    return render_template("repairs/form.html", repair=repair, customers=customers, action="Edit")


@repair_bp.route("/delete/<int:id>", methods=["POST"])
@role_required("admin")
def delete_repair(id):
    repair = RepairOrder.query.get_or_404(id)
    repair.deleted_at = datetime.utcnow()
    db.session.commit()
    flash("Repair order archived", "success")
    return redirect(url_for("repair.list_repairs"))


@repair_bp.route("/view/<int:id>")
@login_required
def view_repair(id):
    repair = RepairOrder.query.filter(RepairOrder.id == id, RepairOrder.deleted_at.is_(None)).first_or_404()
    return render_template("repairs/detail.html", repair=repair)


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
    if new_status not in REPAIR_STATUSES:
        flash("Invalid repair status", "error")
        return redirect(url_for("repair.view_repair", id=id))
    repair.status = new_status
    if new_status == "Delivered" and repair.delivered_at is None:
        repair.delivered_at = datetime.utcnow()
    db.session.commit()
    flash("Repair order status updated", "success")
    return redirect(url_for("repair.view_repair", id=id))


@repair_bp.route("/search", methods=["GET"])
@login_required
def search_repairs():
    return redirect(url_for("repair.list_repairs", q=request.args.get("q", "").strip()))
