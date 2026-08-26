from datetime import date
from decimal import Decimal,InvalidOperation
from flask import Blueprint,abort,flash,redirect,render_template,request,url_for
from sqlalchemy import func
from app.extensions import db
from app.models import AuditEvent,Customer,Expense,Part,Purchase,PurchaseReturn,RepairOrder,StockAllocation,Supplier,SupplierPayment,User
from app.security import current_user_id,permission_required
ops_bp=Blueprint('ops',__name__,url_prefix='/operations')
def D(v):
 try:return Decimal(v or '0')
 except (InvalidOperation,ValueError):return Decimal('0')
def audit(action,etype,eid,details=''): db.session.add(AuditEvent(user_id=current_user_id(),action=action,entity_type=etype,entity_id=eid,details=details))

@ops_bp.route('/suppliers')
@permission_required('purchases')
def suppliers():
 rows=Supplier.query.order_by(Supplier.name).all(); data=[]
 for s in rows:
  purchases=sum((p.total for p in Purchase.query.filter_by(supplier_id=s.id).all()),Decimal('0')); returns=sum((r.total for r in PurchaseReturn.query.join(Purchase).filter(Purchase.supplier_id==s.id).all()),Decimal('0')); paid=sum((p.amount for p in s.payments),Decimal('0')); data.append((s,purchases,returns,paid,purchases-returns-paid))
 return render_template('operations/suppliers.html',rows=data)

@ops_bp.route('/suppliers/<int:supplier_id>/payment',methods=['POST'])
@permission_required('purchases')
def supplier_payment(supplier_id):
 s=db.session.get(Supplier,supplier_id); amount=D(request.form.get('amount'))
 if not s or amount<=0: abort(400)
 p=SupplierPayment(supplier_id=s.id,amount=amount,payment_date=date.fromisoformat(request.form.get('payment_date') or date.today().isoformat()),method=request.form.get('method'),reference=request.form.get('reference'),notes=request.form.get('notes'),created_by=current_user_id()); db.session.add(p); audit('supplier_payment','supplier',s.id,f'Paid {amount}'); db.session.commit(); flash('Supplier payment recorded.','success'); return redirect(url_for('ops.suppliers'))

@ops_bp.route('/expenses',methods=['GET','POST'])
@permission_required('expenses')
def expenses():
 if request.method=='POST':
  amount=D(request.form.get('amount'))
  if amount<=0: abort(400)
  e=Expense(expense_date=date.fromisoformat(request.form.get('expense_date') or date.today().isoformat()),category=request.form.get('category') or 'Other',amount=amount,repair_id=request.form.get('repair_id',type=int),description=request.form.get('description') or 'Expense',payment_method=request.form.get('payment_method'),reference=request.form.get('reference'),created_by=current_user_id()); db.session.add(e); db.session.flush(); audit('expense_created','expense',e.id,f'{e.category} {amount}'); db.session.commit(); flash('Expense saved.','success'); return redirect(url_for('ops.expenses'))
 return render_template('operations/expenses.html',rows=Expense.query.order_by(Expense.expense_date.desc(),Expense.id.desc()).all(),repairs=RepairOrder.query.filter(RepairOrder.deleted_at.is_(None)).order_by(RepairOrder.id.desc()).limit(200).all(),today=date.today().isoformat())

@ops_bp.route('/stock',methods=['GET','POST'])
@permission_required('inventory')
def stock():
 if request.method=='POST':
  part=db.session.get(Part,request.form.get('part_id',type=int)); repair=db.session.get(RepairOrder,request.form.get('repair_id',type=int)); qty=D(request.form.get('quantity'))
  reserved=db.session.query(func.coalesce(func.sum(StockAllocation.quantity),0)).filter(StockAllocation.part_id==part.id,StockAllocation.status.in_(['Reserved','With Technician'])).scalar() if part else 0
  if not part or not repair or qty<=0 or D(part.quantity)-D(reserved)<qty: flash('Not enough available unreserved stock.','error'); return redirect(url_for('ops.stock'))
  a=StockAllocation(part_id=part.id,repair_id=repair.id,technician_id=request.form.get('technician_id',type=int) or repair.assigned_technician_id,quantity=qty,status='Reserved',notes=request.form.get('notes'),created_by=current_user_id()); db.session.add(a); db.session.flush(); audit('stock_reserved','stock_allocation',a.id,f'{part.name} x {qty} for {repair.job_number}'); db.session.commit(); return redirect(url_for('ops.stock'))
 return render_template('operations/stock.html',rows=StockAllocation.query.order_by(StockAllocation.id.desc()).all(),parts=Part.query.filter_by(active=True).all(),repairs=RepairOrder.query.filter(RepairOrder.deleted_at.is_(None)).order_by(RepairOrder.id.desc()).limit(200).all(),techs=User.query.filter_by(role='technician').all())

@ops_bp.route('/stock/<int:allocation_id>/<status>',methods=['POST'])
@permission_required('inventory')
def stock_status(allocation_id,status):
 if status not in ['With Technician','Used','Returned']: abort(400)
 a=db.session.get(StockAllocation,allocation_id)
 if not a: abort(404)
 if status=='Used' and a.status!='Used':
  if D(a.part.quantity)<D(a.quantity): flash('Physical stock is insufficient.','error'); return redirect(url_for('ops.stock'))
  a.part.quantity-=a.quantity
 a.status=status; audit('stock_allocation_status','stock_allocation',a.id,status); db.session.commit(); return redirect(url_for('ops.stock'))

@ops_bp.route('/customers/<int:customer_id>/history')
@permission_required('customers')
def customer_history(customer_id):
 c=db.session.get(Customer,customer_id)
 if not c: abort(404)
 return render_template('operations/customer_history.html',customer=c,repairs=RepairOrder.query.filter_by(customer_id=c.id).order_by(RepairOrder.id.desc()).all())

@ops_bp.route('/audit')
@permission_required('audit')
def audit_log(): return render_template('operations/audit.html',rows=AuditEvent.query.order_by(AuditEvent.id.desc()).limit(500).all())

@ops_bp.route('/executive-report')
@permission_required('reports')
def executive_report():
 revenue=D(db.session.query(func.coalesce(func.sum(RepairOrder.amount_paid),0)).scalar()); expenses=D(db.session.query(func.coalesce(func.sum(Expense.amount),0)).scalar()); supplier_paid=D(db.session.query(func.coalesce(func.sum(SupplierPayment.amount),0)).scalar()); open_jobs=RepairOrder.query.filter(RepairOrder.deleted_at.is_(None),~RepairOrder.status.in_(['Delivered','Cancelled'])).count(); unpaid=RepairOrder.query.filter(RepairOrder.deleted_at.is_(None),RepairOrder.payment_status!='Paid').count(); low=Part.query.filter(Part.active.is_(True),Part.quantity<=Part.reorder_level).count()
 return render_template('operations/report.html',revenue=revenue,expenses=expenses,supplier_paid=supplier_paid,net=revenue-expenses,open_jobs=open_jobs,unpaid=unpaid,low=low)
