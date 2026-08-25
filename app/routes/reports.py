from datetime import datetime, timedelta
from decimal import Decimal

from flask import Blueprint, render_template, request
from sqlalchemy import func

from app.extensions import db
from app.models import RepairOrder, Invoice, Payment, Part, PartUsage, User, Customer
from app.security import role_required

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


def _date_range():
    end = datetime.utcnow()
    start_raw = request.args.get("start")
    end_raw = request.args.get("end")
    try:
        start = datetime.strptime(start_raw, "%Y-%m-%d") if start_raw else end - timedelta(days=30)
        finish = datetime.strptime(end_raw, "%Y-%m-%d") + timedelta(days=1) if end_raw else end
    except ValueError:
        start = end - timedelta(days=30)
        finish = end
    return start, finish


@reports_bp.route("/")
@role_required("admin", "staff")
def dashboard():
    start, end = _date_range()
    repairs = RepairOrder.query.filter(RepairOrder.deleted_at.is_(None), RepairOrder.created_at >= start, RepairOrder.created_at < end)
    invoice_q = Invoice.query.filter(Invoice.created_at >= start, Invoice.created_at < end)
    payment_q = Payment.query.filter(Payment.created_at >= start, Payment.created_at < end)

    invoice_total = db.session.query(func.coalesce(func.sum(Invoice.total), 0)).filter(Invoice.created_at >= start, Invoice.created_at < end).scalar() or 0
    payment_total = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(Payment.payment_type == "Payment", Payment.created_at >= start, Payment.created_at < end).scalar() or 0
    refund_total = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(Payment.payment_type == "Refund", Payment.created_at >= start, Payment.created_at < end).scalar() or 0
    parts_cost = db.session.query(func.coalesce(func.sum(PartUsage.quantity * PartUsage.unit_cost), 0)).filter(PartUsage.created_at >= start, PartUsage.created_at < end).scalar() or 0
    parts_revenue = db.session.query(func.coalesce(func.sum(PartUsage.quantity * PartUsage.unit_price), 0)).filter(PartUsage.created_at >= start, PartUsage.created_at < end).scalar() or 0

    status_counts = dict(db.session.query(RepairOrder.status, func.count(RepairOrder.id)).filter(RepairOrder.deleted_at.is_(None)).group_by(RepairOrder.status).all())
    technician_counts = dict(db.session.query(User.email, func.count(RepairOrder.id)).join(RepairOrder, RepairOrder.assigned_technician_id == User.id).filter(RepairOrder.deleted_at.is_(None), RepairOrder.created_at >= start, RepairOrder.created_at < end).group_by(User.email).all())
    low_stock = Part.query.filter(Part.active.is_(True), Part.quantity <= Part.reorder_level).order_by(Part.quantity.asc()).all()

    gross_profit = Decimal(str(parts_revenue)) - Decimal(str(parts_cost))
    return render_template(
        "reports/dashboard.html",
        start=start, end=end, repair_count=repairs.count(), invoice_count=invoice_q.count(),
        customer_count=Customer.query.count(), invoice_total=Decimal(str(invoice_total)),
        payment_total=Decimal(str(payment_total)), refund_total=Decimal(str(refund_total)),
        parts_cost=Decimal(str(parts_cost)), parts_revenue=Decimal(str(parts_revenue)), gross_profit=gross_profit,
        outstanding=Decimal(str(invoice_total)) - Decimal(str(payment_total)) + Decimal(str(refund_total)),
        status_counts=status_counts, technician_counts=technician_counts, low_stock=low_stock,
    )


@reports_bp.route("/repairs")
@role_required("admin", "staff")
def repair_report():
    start, end = _date_range()
    repairs = RepairOrder.query.filter(RepairOrder.deleted_at.is_(None), RepairOrder.created_at >= start, RepairOrder.created_at < end).order_by(RepairOrder.created_at.desc()).all()
    return render_template("reports/repairs.html", repairs=repairs, start=start, end=end)
