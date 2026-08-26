from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func
from app.extensions import db
from app.models import AuditEvent, Part, Purchase, PurchaseItem, PurchaseReturn, StockMovement, Supplier
from app.security import current_user_id, permission_required, role_required
from app.services.settings import format_number, get_bool

purchases_bp=Blueprint("purchases",__name__,url_prefix="/purchases")
def dec(value):
    try:return Decimal(value or "0")
    except (InvalidOperation,ValueError):return Decimal("0")
def audit(action,entity_id,details=""):db.session.add(AuditEvent(user_id=current_user_id(),action=action,entity_type="purchase",entity_id=entity_id,details=details))
def _purchase_number():return format_number("purchase_prefix","PUR",Purchase,"purchase_number",datetime.now(timezone.utc))

def _return_number():
    today=date.today().strftime("%Y%m%d"); latest=PurchaseReturn.query.filter(PurchaseReturn.return_number.like(f"RET-{today}-%")).order_by(PurchaseReturn.id.desc()).first(); seq=int(latest.return_number.rsplit("-",1)[-1])+1 if latest else 1; return f"RET-{today}-{seq:04d}"

@purchases_bp.route("/")
@permission_required("purchases")
def index():return render_template("purchases/list.html",purchases=Purchase.query.order_by(Purchase.purchase_date.desc(),Purchase.id.desc()).all())
@purchases_bp.route("/new",methods=["GET","POST"])
@permission_required("purchases")
def create():
    suppliers=Supplier.query.filter_by(active=True).order_by(Supplier.name).all();parts=Part.query.filter_by(active=True).order_by(Part.name).all()
    if request.method=="POST":
        supplier=db.session.get(Supplier,request.form.get("supplier_id",type=int));purchase_date=request.form.get("purchase_date") or date.today().isoformat();lines=[]
        for pid,qv,cv in zip(request.form.getlist("part_id"),request.form.getlist("quantity"),request.form.getlist("unit_cost")):
            part=db.session.get(Part,int(pid)) if pid else None;qty=dec(qv);cost=dec(cv)
            if part and part.active and qty>0 and cost>=0:lines.append((part,qty,cost))
        if not supplier or not supplier.active or not lines:flash("Select an active supplier and add at least one valid part line.","error");return render_template("purchases/form.html",suppliers=suppliers,parts=parts,today=date.today().isoformat())
        number=_purchase_number();purchase=Purchase(purchase_number=number,supplier_id=supplier.id,bill_number=request.form.get("bill_number","").strip() or None,purchase_date=date.fromisoformat(purchase_date),notes=request.form.get("notes","").strip() or None,status="Active",created_by=current_user_id());db.session.add(purchase);db.session.flush()
        for part,qty,cost in lines:
            db.session.add(PurchaseItem(purchase_id=purchase.id,part_id=part.id,quantity=qty,unit_cost=cost));part.quantity+=qty;part.cost_price=cost;part.supplier=supplier.name;db.session.add(StockMovement(part_id=part.id,user_id=current_user_id(),movement_type="IN",quantity=qty,reference=number,notes=f"Supplier purchase {supplier.name}"))
        audit("purchase_created",purchase.id,f"{number}; supplier={supplier.name}; total={purchase.total}");db.session.commit();flash(f"Purchase {number} saved and stock updated.","success");return redirect(url_for("purchases.view",purchase_id=purchase.id))
    return render_template("purchases/form.html",suppliers=suppliers,parts=parts,today=date.today().isoformat())
@purchases_bp.route("/<int:purchase_id>")
@permission_required("purchases")
def view(purchase_id):
    row=db.session.get(Purchase,purchase_id)
    if row is None:abort(404)
    returned={item.id:dec(db.session.query(func.coalesce(func.sum(PurchaseReturn.quantity),0)).filter(PurchaseReturn.purchase_item_id==item.id).scalar()) for item in row.items};return render_template("purchases/view.html",purchase=row,returned=returned)
@purchases_bp.route("/<int:purchase_id>/return",methods=["POST"])
@role_required("admin","manager")
def return_item(purchase_id):
    purchase=db.session.get(Purchase,purchase_id);item=db.session.get(PurchaseItem,request.form.get("purchase_item_id",type=int));qty=dec(request.form.get("quantity"));reason=request.form.get("reason","").strip()
    if not purchase or purchase.status=="Voided" or not item or item.purchase_id!=purchase.id:abort(404)
    already=dec(db.session.query(func.coalesce(func.sum(PurchaseReturn.quantity),0)).filter(PurchaseReturn.purchase_item_id==item.id).scalar());available=item.quantity-already
    if qty<=0 or qty>available:flash(f"Return quantity must be between 0 and {available}.","error");return redirect(url_for("purchases.view",purchase_id=purchase.id))
    if not reason:flash("Return reason is required.","error");return redirect(url_for("purchases.view",purchase_id=purchase.id))
    if item.part.quantity<qty and not get_bool("allow_negative_stock"):flash("Cannot return this quantity because current inventory stock is lower.","error");return redirect(url_for("purchases.view",purchase_id=purchase.id))
    number=_return_number();ret=PurchaseReturn(return_number=number,purchase_id=purchase.id,purchase_item_id=item.id,quantity=qty,unit_cost=item.unit_cost,reason=reason,created_by=current_user_id());db.session.add(ret);item.part.quantity-=qty;db.session.add(StockMovement(part_id=item.part_id,user_id=current_user_id(),movement_type="RETURN_TO_SUPPLIER",quantity=qty,reference=number,notes=f"Return to {purchase.supplier.name}: {reason}"));audit("purchase_return",purchase.id,f"{number}; {item.part.name} x {qty}; {reason}");db.session.commit();flash(f"{number} created. Inventory reduced by {qty}.","success");return redirect(url_for("purchases.view",purchase_id=purchase.id))
@purchases_bp.route("/<int:purchase_id>/void",methods=["POST"])
@role_required("admin","manager")
def void_purchase(purchase_id):
    purchase=db.session.get(Purchase,purchase_id)
    if purchase is None:abort(404)
    if purchase.status=="Voided":flash("Purchase is already voided.","error");return redirect(url_for("purchases.view",purchase_id=purchase.id))
    reason=request.form.get("reason","").strip()
    if not reason:flash("Void reason is required.","error");return redirect(url_for("purchases.view",purchase_id=purchase.id))
    reversals=[]
    for item in purchase.items:
        returned=dec(db.session.query(func.coalesce(func.sum(PurchaseReturn.quantity),0)).filter(PurchaseReturn.purchase_item_id==item.id).scalar());net=max(item.quantity-returned,Decimal("0"))
        if item.part.quantity<net and not get_bool("allow_negative_stock"):flash(f"Cannot void purchase because {item.part.name} only has {item.part.quantity} in stock but {net} must be reversed.","error");return redirect(url_for("purchases.view",purchase_id=purchase.id))
        reversals.append((item,net))
    for item,qty in reversals:
        if qty>0:item.part.quantity-=qty;db.session.add(StockMovement(part_id=item.part_id,user_id=current_user_id(),movement_type="PURCHASE_VOID",quantity=qty,reference=purchase.purchase_number,notes=f"Purchase void: {reason}"))
    purchase.status="Voided";purchase.void_reason=reason;purchase.voided_by=current_user_id();purchase.voided_at=datetime.now(timezone.utc);audit("purchase_voided",purchase.id,f"{purchase.purchase_number}; {reason}");db.session.commit();flash("Purchase voided and remaining received stock reversed.","success");return redirect(url_for("purchases.view",purchase_id=purchase.id))
