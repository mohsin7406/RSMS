from decimal import Decimal

from flask import Blueprint, render_template, request
from sqlalchemy.orm import joinedload

from app.models import Invoice, RepairOrder
from app.security import role_required

profitability_bp = Blueprint("profitability", __name__, url_prefix="/reports")


@profitability_bp.route("/profitability")
@role_required("admin", "staff")
def profitability():
    query = RepairOrder.query.options(
        joinedload(RepairOrder.customer),
        joinedload(RepairOrder.assigned_technician),
    ).filter(RepairOrder.deleted_at.is_(None))
    status = request.args.get("status", "")
    if status:
        query = query.filter(RepairOrder.status == status)

    repairs = []
    totals = {"revenue": Decimal("0"), "parts_cost": Decimal("0"), "profit": Decimal("0")}
    for repair in query.order_by(RepairOrder.created_at.desc()).all():
        invoice = repair.invoice
        revenue = Decimal(invoice.total if invoice else repair.final_amount or 0)
        parts_cost = repair.parts_cost
        profit = revenue - parts_cost
        repairs.append({"repair": repair, "revenue": revenue, "parts_cost": parts_cost, "profit": profit})
        totals["revenue"] += revenue
        totals["parts_cost"] += parts_cost
        totals["profit"] += profit

    return render_template("reports/profitability.html", rows=repairs, totals=totals)
