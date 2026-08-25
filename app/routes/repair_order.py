from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from app.extensions import db
from app.models import Customer, RepairOrder
from app.security import login_required, role_required


repair_bp = Blueprint("repair", __name__, url_prefix="/repairs")
REPAIR_STATUSES = {"Pending", "In Progress", "Completed"}


def _repair_values():
    status = request.form.get("status", "Pending")
    return {
        "customer_id": request.form.get("customer_id", type=int),
        "device": request.form.get("device", "").strip(),
        "issue_description": request.form.get("issue_description", "").strip(),
        "status": status,
    }


def _validate_repair(values):
    if not values["customer_id"] or not values["device"] or not values["issue_description"]:
        return "Customer, device and issue description are required"
    if values["status"] not in REPAIR_STATUSES:
        return "Invalid repair status"
    if not Customer.query.get(values["customer_id"]):
        return "Selected customer does not exist"
    return None


@repair_bp.route("/")
@repair_bp.route("/list")
@login_required
def list_repairs():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    query = RepairOrder.query.join(Customer)

    if q:
        query = query.filter(or_(Customer.name.ilike(f"%{q}%"), RepairOrder.device.ilike(f"%{q}%")))
    if status:
        if status not in REPAIR_STATUSES:
            flash("Invalid status filter", "error")
            status = ""
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

        repair = RepairOrder(**values)
        db.session.add(repair)
        db.session.commit()
        flash("Repair order created", "success")
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

        repair.customer_id = values["customer_id"]
        repair.device = values["device"]
        repair.issue_description = values["issue_description"]
        repair.status = values["status"]
        db.session.commit()
        flash("Repair order updated", "success")
        return redirect(url_for("repair.view_repair", id=id))

    return render_template("repairs/form.html", repair=repair, customers=customers, action="Edit")


@repair_bp.route("/delete/<int:id>", methods=["POST"])
@role_required("admin")
def delete_repair(id):
    repair = RepairOrder.query.get_or_404(id)
    db.session.delete(repair)
    db.session.commit()
    flash("Repair order deleted", "success")
    return redirect(url_for("repair.list_repairs"))


@repair_bp.route("/view/<int:id>")
@login_required
def view_repair(id):
    repair = RepairOrder.query.get_or_404(id)
    return render_template("repairs/detail.html", repair=repair)


@repair_bp.route("/customer/<int:customer_id>")
@login_required
def repairs_by_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    repairs = RepairOrder.query.filter_by(customer_id=customer_id).order_by(RepairOrder.created_at.desc()).all()
    return render_template("repairs/customer_repairs.html", customer=customer, repairs=repairs)


@repair_bp.route("/status/<status>")
@login_required
def repairs_by_status(status):
    if status not in REPAIR_STATUSES:
        flash("Invalid repair status", "error")
        return redirect(url_for("repair.list_repairs"))
    repairs = RepairOrder.query.filter_by(status=status).order_by(RepairOrder.created_at.desc()).all()
    return render_template("repairs/status_repairs.html", status=status, repairs=repairs)


@repair_bp.route("/update_status/<int:id>", methods=["POST"])
@role_required("admin", "staff", "technician")
def update_repair_status(id):
    repair = RepairOrder.query.get_or_404(id)
    new_status = request.form.get("status", "")
    if new_status not in REPAIR_STATUSES:
        flash("Invalid repair status", "error")
        return redirect(url_for("repair.view_repair", id=id))

    repair.status = new_status
    db.session.commit()
    flash("Repair order status updated", "success")
    return redirect(url_for("repair.view_repair", id=id))


@repair_bp.route("/search", methods=["GET"])
@login_required
def search_repairs():
    return redirect(url_for("repair.list_repairs", q=request.args.get("q", "").strip()))
