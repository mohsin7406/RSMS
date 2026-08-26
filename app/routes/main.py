from decimal import Decimal
from datetime import datetime, timezone
from flask import Blueprint, g, redirect, render_template, session, url_for
from sqlalchemy import func
from app.extensions import db
from app.models import Booking, Expense, Lead, Part, RepairOrder, Supplier, SupplierPayment
from app.security import login_required
main_bp=Blueprint("main",__name__)
def D(value): return Decimal(value or 0)
@main_bp.route("/")
def home():
    if session.get("user_id"): return redirect(url_for("main.dashboard"))
    return render_template("index.html")
@main_bp.route("/dashboard")
@login_required
def dashboard():
    if g.current_user and g.current_user.role=="technician": return redirect(url_for("technician.dashboard"))
    active_repairs=RepairOrder.query.filter(RepairOrder.deleted_at.is_(None)); open_jobs=active_repairs.filter(~RepairOrder.status.in_(["Delivered","Completed","Cancelled"])).count(); completed_unpaid=active_repairs.filter(RepairOrder.status.in_(["Ready","Completed"]),RepairOrder.payment_status!="Paid").count(); open_leads=Lead.query.filter(Lead.status.in_(["New","Contacted","Follow Up"])).count(); active_bookings=Booking.query.filter(~Booking.status.in_(["Completed","Cancelled"])).count(); collections=D(db.session.query(func.coalesce(func.sum(RepairOrder.amount_paid),0)).scalar()); expenses=D(db.session.query(func.coalesce(func.sum(Expense.amount),0)).scalar()); low_stock=Part.query.filter(Part.active.is_(True),Part.quantity<=Part.reorder_level).count()
    supplier_outstanding=Decimal("0")
    for supplier in Supplier.query.all():
        purchase_total=sum((p.net_total for p in getattr(supplier,"purchases",[]) if getattr(p,"status","Active")!="Voided"),Decimal("0")) if hasattr(supplier,"purchases") else Decimal("0")
        if not purchase_total:
            from app.models import Purchase
            purchase_total=sum((p.net_total for p in Purchase.query.filter_by(supplier_id=supplier.id).all()),Decimal("0"))
        paid=sum((payment.amount for payment in supplier.payments),Decimal("0")); supplier_outstanding+=max(purchase_total-paid,Decimal("0"))
    unassigned=active_repairs.filter(RepairOrder.status=="Pending",RepairOrder.assigned_technician_id.is_(None)).count(); qc_attention=active_repairs.filter(RepairOrder.status.in_(["Approved","In Progress"])).count(); unpaid_amount=sum((max(D(r.final_amount)-D(r.amount_paid),Decimal("0")) for r in active_repairs.filter(RepairOrder.payment_status!="Paid").all()),Decimal("0")); pending_expenses=Expense.query.filter_by(status="Pending").count() if hasattr(Expense,"status") else 0; followups=Lead.query.filter(Lead.status.in_(["New","Contacted","Follow Up"])).order_by(Lead.updated_at.asc() if hasattr(Lead,"updated_at") else Lead.created_at.asc()).limit(5).all(); upcoming=Booking.query.filter(~Booking.status.in_(["Completed","Cancelled"])).order_by(Booking.scheduled_at.asc()).limit(5).all(); recent_repairs=active_repairs.order_by(RepairOrder.created_at.desc()).limit(8).all()
    return render_template("dashboard.html",open_jobs=open_jobs,completed_unpaid=completed_unpaid,open_leads=open_leads,active_bookings=active_bookings,collections=collections,expenses=expenses,low_stock=low_stock,supplier_outstanding=supplier_outstanding,recent_repairs=recent_repairs,unassigned=unassigned,qc_attention=qc_attention,unpaid_amount=unpaid_amount,pending_expenses=pending_expenses,followups=followups,upcoming=upcoming)
