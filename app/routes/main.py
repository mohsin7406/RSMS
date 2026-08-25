from flask import Blueprint, redirect, render_template, session, url_for

from app.models import Customer, RepairOrder
from app.security import login_required


main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("main.dashboard"))
    return render_template("index.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    total_customers = Customer.query.count()
    active_repairs = RepairOrder.query.filter(RepairOrder.deleted_at.is_(None))
    total_repairs = active_repairs.count()
    pending_repairs = active_repairs.filter(RepairOrder.status.in_(["Pending", "Received", "Diagnosing", "Waiting Approval", "Approved", "Waiting Parts", "In Progress", "In Repair", "QC", "Ready"])).count()
    recent_repairs = active_repairs.order_by(RepairOrder.created_at.desc()).limit(5).all()

    return render_template(
        "dashboard.html",
        total_customers=total_customers,
        total_repairs=total_repairs,
        pending_repairs=pending_repairs,
        recent_repairs=recent_repairs,
    )
