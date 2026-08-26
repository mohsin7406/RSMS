from decimal import Decimal

from flask import Blueprint, render_template, request
from sqlalchemy.orm import joinedload

from app.models import RepairOrder
from app.security import permission_required

profitability_bp = Blueprint("profitability", __name__, url_prefix="/reports")


@profitability_bp.route("/profitability")
@permission_required("reports")
def profitability():
    query = RepairOrder.query.options(joinedload(RepairOrder.customer), joinedload(RepairOrder.assigned_technician)).filter(RepairOrder.deleted_at.is_(None))
    status = request.args.get("status", "")
    if status:
        query = query.filter(RepairOrder.status == status)

    rows = []
    totals = {"revenue": Decimal("0"), "parts_cost": Decimal("0"), "parts_revenue": Decimal("0"), "expenses": Decimal("0"), "profit": Decimal("0")}
    for repair in query.order_by(RepairOrder.created_at.desc()).all():
        invoice = repair.invoice
        revenue = Decimal(invoice.total if invoice else repair.final_amount or 0)
        inventory_cost = sum((usage.net_cost_total for usage in repair.parts_used), Decimal("0"))
        inventory_revenue = sum((usage.net_sale_total for usage in repair.parts_used), Decimal("0"))
        purchase_cost = sum((purchase.net_cost_total for purchase in repair.job_purchases), Decimal("0"))
        purchase_revenue = sum((purchase.net_sale_total for purchase in repair.job_purchases), Decimal("0"))
        expense_total = sum((expense.amount for expense in repair.expenses), Decimal("0"))
        parts_cost = inventory_cost + purchase_cost
        parts_revenue = inventory_revenue + purchase_revenue
        profit = revenue - parts_cost - expense_total
        rows.append({"repair": repair, "revenue": revenue, "parts_cost": parts_cost, "parts_revenue": parts_revenue, "expenses": expense_total, "profit": profit})
        totals["revenue"] += revenue
        totals["parts_cost"] += parts_cost
        totals["parts_revenue"] += parts_revenue
        totals["expenses"] += expense_total
        totals["profit"] += profit

    return render_template("reports/profitability.html", rows=rows, totals=totals)
