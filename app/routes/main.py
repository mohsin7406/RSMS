from decimal import Decimal
from flask import Blueprint, g, redirect, render_template, session, url_for
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models import Booking, Expense, Lead, Part, Purchase, PurchaseItem, PurchaseReturn, RepairOrder, SupplierPayment
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
    active_repairs=RepairOrder.query.filter(RepairOrder.deleted_at.is_(None))
    open_jobs=active_repairs.filter(~RepairOrder.status.in_(["Delivered","Completed","Cancelled"])).count()
    completed_unpaid=active_repairs.filter(RepairOrder.status.in_(["Ready","Completed"]),RepairOrder.payment_status!="Paid").count()
    open_leads=Lead.query.filter(Lead.status.in_(["New","Contacted","Follow Up"])).count()
    active_bookings=Booking.query.filter(~Booking.status.in_(["Completed","Cancelled"])).count()
    collections=D(db.session.query(func.coalesce(func.sum(RepairOrder.amount_paid),0)).scalar())
    expenses=D(db.session.query(func.coalesce(func.sum(Expense.amount),0)).scalar())
    low_stock=Part.query.filter(Part.active.is_(True),Part.quantity<=Part.reorder_level).count()
    # Aggregate supplier liability in SQL rather than loading every supplier/purchase/payment.
    purchased=D(db.session.query(func.coalesce(func.sum(PurchaseItem.quantity*PurchaseItem.unit_cost),0)).join(Purchase,Purchase.id==PurchaseItem.purchase_id).filter(Purchase.status!="Voided").scalar())
    returned=D(db.session.query(func.coalesce(func.sum(PurchaseReturn.quantity*PurchaseReturn.unit_cost),0)).join(Purchase,Purchase.id==PurchaseReturn.purchase_id).filter(Purchase.status!="Voided").scalar())
    supplier_paid=D(db.session.query(func.coalesce(func.sum(SupplierPayment.amount),0)).scalar())
    supplier_outstanding=max(purchased-returned-supplier_paid,Decimal("0"))
    unassigned=active_repairs.filter(RepairOrder.status=="Pending",RepairOrder.assigned_technician_id.is_(None)).count()
    qc_attention=active_repairs.filter(RepairOrder.status.in_(["Approved","In Progress"])).count()
    # Outstanding can be computed entirely by SQL; avoid loading every unpaid RepairOrder.
    unpaid_amount=D(db.session.query(func.coalesce(func.sum(func.max(func.coalesce(RepairOrder.final_amount,0)-func.coalesce(RepairOrder.amount_paid,0),0)),0)).filter(RepairOrder.deleted_at.is_(None),RepairOrder.payment_status!="Paid").scalar())
    pending_expenses=Expense.query.filter_by(status="Pending").count()
    followups=Lead.query.filter(Lead.status.in_(["New","Contacted","Follow Up"])).order_by(Lead.updated_at.asc() if hasattr(Lead,"updated_at") else Lead.created_at.asc()).limit(5).all()
    upcoming=Booking.query.options(joinedload(Booking.customer)).filter(~Booking.status.in_(["Completed","Cancelled"])).order_by(Booking.scheduled_at.asc()).limit(5).all()
    recent_repairs=active_repairs.options(joinedload(RepairOrder.customer)).order_by(RepairOrder.created_at.desc()).limit(8).all()
    return render_template("dashboard.html",open_jobs=open_jobs,completed_unpaid=completed_unpaid,open_leads=open_leads,active_bookings=active_bookings,collections=collections,expenses=expenses,low_stock=low_stock,supplier_outstanding=supplier_outstanding,recent_repairs=recent_repairs,unassigned=unassigned,qc_attention=qc_attention,unpaid_amount=unpaid_amount,pending_expenses=pending_expenses,followups=followups,upcoming=upcoming)
