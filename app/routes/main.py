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
    total_repairs = RepairOrder.query.count()
    pending_repairs = RepairOrder.query.filter_by(status="Pending").count()
    recent_repairs = RepairOrder.query.order_by(RepairOrder.created_at.desc()).limit(5).all()

    return render_template(
        "dashboard.html",
        total_customers=total_customers,
        total_repairs=total_repairs,
        pending_repairs=pending_repairs,
        recent_repairs=recent_repairs,
    )
