from datetime import date
from decimal import Decimal, InvalidOperation
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func
from app.extensions import db
from app.models import AuditEvent, Customer, Expense, Part, PartUsage, Purchase, PurchaseReturn, RepairOrder, StockAllocation, StockMovement, Supplier, SupplierPayment, User
from app.security import current_user_id, permission_required
from app.services.settings import get_bool, get_int, get_options

ops_bp=Blueprint("ops",__name__,url_prefix="/operations")
def D(value):
    try:return Decimal(value or "0")
    except (InvalidOperation,ValueError):return Decimal("0")
def audit(action,entity_type,entity_id,details=""):db.session.add(AuditEvent(user_id=current_user_id(),action=action,entity_type=entity_type,entity_id=entity_id,details=details))
def supplier_totals(supplier):
    purchases=sum((p.total for p in Purchase.query.filter_by(supplier_id=supplier.id).all() if getattr(p,"status","Active")!="Voided"),Decimal("0"));returns=sum((r.total for r in PurchaseReturn.query.join(Purchase).filter(Purchase.supplier_id==supplier.id).all() if getattr(r.purchase,"status","Active")!="Voided"),Decimal("0"));paid=sum((p.amount for p in supplier.payments),Decimal("0"));return purchases,returns,paid,max(purchases-returns-paid,Decimal("0"))

@ops_bp.route("/suppliers")
@permission_required("purchases")
def suppliers():return render_template("operations/suppliers.html",rows=[(s,*supplier_totals(s)) for s in Supplier.query.order_by(Supplier.name).all()])
@ops_bp.route("/suppliers/<int:supplier_id>/payment",methods=["POST"])
@permission_required("purchases")
def supplier_payment(supplier_id):
    supplier=db.session.get(Supplier,supplier_id);amount=D(request.form.get("amount"));method=request.form.get("method","")
    if supplier is None or amount<=0:abort(400)
    if method not in get_options("payment_methods"):flash("Select a valid configured payment method.","error");return redirect(url_for("ops.suppliers"))
    _,_,_,outstanding=supplier_totals(supplier)
    if outstanding<=0:flash("This supplier has no outstanding balance.","error");return redirect(url_for("ops.suppliers"))
    if amount>outstanding:flash(f"Payment cannot exceed supplier outstanding ₹{outstanding:.2f}.","error");return redirect(url_for("ops.suppliers"))
    p=SupplierPayment(supplier_id=supplier.id,amount=amount,payment_date=date.fromisoformat(request.form.get("payment_date") or date.today().isoformat()),method=method,reference=request.form.get("reference"),notes=request.form.get("notes"),created_by=current_user_id());db.session.add(p);audit("supplier_payment","supplier",supplier.id,f"Paid {amount}; previous outstanding {outstanding}");db.session.commit();flash("Supplier payment recorded.","success");return redirect(url_for("ops.suppliers"))

@ops_bp.route("/expenses",methods=["GET","POST"])
@permission_required("expenses")
def expenses():
    if request.method=="POST":
        amount=D(request.form.get("amount"));repair_id=request.form.get("repair_id",type=int);category=request.form.get("category","");method=request.form.get("payment_method","")
        if amount<=0:abort(400)
        if category not in get_options("expense_categories"):flash("Select a valid configured expense category.","error");return redirect(url_for("ops.expenses"))
        if method and method not in get_options("payment_methods"):flash("Select a valid configured payment method.","error");return redirect(url_for("ops.expenses"))
        if repair_id and db.session.get(RepairOrder,repair_id) is None:abort(400)
        expense=Expense(expense_date=date.fromisoformat(request.form.get("expense_date") or date.today().isoformat()),category=category,amount=amount,repair_id=repair_id,description=request.form.get("description") or "Expense",payment_method=method or None,reference=request.form.get("reference"),created_by=current_user_id());db.session.add(expense);db.session.flush();audit("expense_created","expense",expense.id,f"{category} {amount}; repair={repair_id or '-'}");db.session.commit();flash("Expense saved.","success");return redirect(url_for("ops.expenses"))
    return render_template("operations/expenses.html",rows=Expense.query.order_by(Expense.expense_date.desc(),Expense.id.desc()).all(),repairs=RepairOrder.query.filter(RepairOrder.deleted_at.is_(None)).order_by(RepairOrder.id.desc()).limit(200).all(),today=date.today().isoformat())

@ops_bp.route("/stock",methods=["GET","POST"])
@permission_required("inventory")
def stock():
    if request.method=="POST":
        part=db.session.get(Part,request.form.get("part_id",type=int));repair=db.session.get(RepairOrder,request.form.get("repair_id",type=int));qty=D(request.form.get("quantity"));reserved=D(db.session.query(func.coalesce(func.sum(StockAllocation.quantity),0)).filter(StockAllocation.part_id==part.id,StockAllocation.status.in_(["Reserved","With Technician"])).scalar()) if part else Decimal("0")
        available=D(part.quantity)-reserved if part else Decimal("0")
        if not part or not repair or repair.deleted_at is not None or qty<=0 or (available<qty and not get_bool("allow_negative_stock")):flash("Not enough available unreserved stock.","error");return redirect(url_for("ops.stock"))
        technician_id=request.form.get("technician_id",type=int) or repair.assigned_technician_id
        if technician_id and not User.query.filter_by(id=technician_id,role="technician").first():flash("Selected technician is invalid.","error");return redirect(url_for("ops.stock"))
        if technician_id and not get_bool("technician_stock_enabled"):flash("Technician stock is disabled in System Settings.","error");return redirect(url_for("ops.stock"))
        allocation=StockAllocation(part_id=part.id,repair_id=repair.id,technician_id=technician_id,quantity=qty,status="Reserved",notes=request.form.get("notes"),created_by=current_user_id());db.session.add(allocation);db.session.flush();audit("stock_reserved","stock_allocation",allocation.id,f"{part.name} x {qty} for {repair.job_number}");db.session.commit();flash(f"Stock reserved for job. Reservation policy: {get_int('reservation_expiry_hours',24)} hours.","success");return redirect(url_for("ops.stock"))
    return render_template("operations/stock.html",rows=StockAllocation.query.order_by(StockAllocation.id.desc()).all(),parts=Part.query.filter_by(active=True).all(),repairs=RepairOrder.query.filter(RepairOrder.deleted_at.is_(None)).order_by(RepairOrder.id.desc()).limit(200).all(),techs=User.query.filter_by(role="technician").all())
@ops_bp.route("/stock/<int:allocation_id>/<status>",methods=["POST"])
@permission_required("inventory")
def stock_status(allocation_id,status):
    allocation=db.session.get(StockAllocation,allocation_id)
    if allocation is None:abort(404)
    transitions={"Reserved":{"With Technician","Used","Returned"},"With Technician":{"Used","Returned"},"Used":set(),"Returned":set()}
    if status not in transitions.get(allocation.status,set()):flash(f"Invalid stock transition: {allocation.status} → {status}","error");return redirect(url_for("ops.stock"))
    if status=="Used":
        if D(allocation.part.quantity)<D(allocation.quantity) and not get_bool("allow_negative_stock"):flash("Physical stock is insufficient.","error");return redirect(url_for("ops.stock"))
        allocation.part.quantity-=allocation.quantity;db.session.add(PartUsage(repair_id=allocation.repair_id,part_id=allocation.part_id,quantity=allocation.quantity,unit_cost=allocation.part.cost_price,unit_price=allocation.part.selling_price));db.session.add(StockMovement(part_id=allocation.part_id,user_id=current_user_id(),movement_type="OUT",quantity=allocation.quantity,reference=allocation.repair.job_number,notes="Reserved/technician stock used on repair"))
    old=allocation.status;allocation.status=status;audit("stock_allocation_status","stock_allocation",allocation.id,f"{old} → {status}");db.session.commit();flash(f"Stock allocation marked {status}.","success");return redirect(url_for("ops.stock"))

@ops_bp.route("/customers/<int:customer_id>/history")
@permission_required("customers")
def customer_history(customer_id):
    customer=db.session.get(Customer,customer_id)
    if not customer:abort(404)
    return render_template("operations/customer_history.html",customer=customer,repairs=RepairOrder.query.filter_by(customer_id=customer.id).order_by(RepairOrder.id.desc()).all())
@ops_bp.route("/audit")
@permission_required("audit")
def audit_log():return render_template("operations/audit.html",rows=AuditEvent.query.order_by(AuditEvent.id.desc()).limit(get_int("pagination_size",50)*10).all())
@ops_bp.route("/executive-report")
@permission_required("reports")
def executive_report():
    collections=D(db.session.query(func.coalesce(func.sum(RepairOrder.amount_paid),0)).scalar());operating_expenses=D(db.session.query(func.coalesce(func.sum(Expense.amount),0)).scalar());supplier_paid=D(db.session.query(func.coalesce(func.sum(SupplierPayment.amount),0)).scalar());repairs=RepairOrder.query.filter(RepairOrder.deleted_at.is_(None)).all();material_cost=sum((usage.net_cost_total for repair in repairs for usage in repair.parts_used),Decimal("0"))+sum((purchase.net_cost_total for repair in repairs for purchase in repair.job_purchases),Decimal("0"));supplier_outstanding=sum((supplier_totals(s)[3] for s in Supplier.query.all()),Decimal("0"));open_jobs=RepairOrder.query.filter(RepairOrder.deleted_at.is_(None),~RepairOrder.status.in_(["Delivered","Completed","Cancelled"])).count();unpaid=RepairOrder.query.filter(RepairOrder.deleted_at.is_(None),RepairOrder.payment_status!="Paid",~RepairOrder.status.in_(["Cancelled"])).count();low=Part.query.filter(Part.active.is_(True),Part.quantity<=Part.reorder_level).count();return render_template("operations/report.html",revenue=collections,expenses=operating_expenses,supplier_paid=supplier_paid,material_cost=material_cost,supplier_outstanding=supplier_outstanding,net=collections-material_cost-operating_expenses,open_jobs=open_jobs,unpaid=unpaid,low=low)
