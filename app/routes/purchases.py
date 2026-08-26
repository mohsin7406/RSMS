from datetime import date
from decimal import Decimal, InvalidOperation
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func
from app.extensions import db
from app.models import Part, Purchase, PurchaseItem, PurchaseReturn, StockMovement, Supplier
from app.security import current_user_id, role_required

purchases_bp=Blueprint("purchases",__name__,url_prefix="/purchases")
def dec(v):
    try: return Decimal(v or "0")
    except (InvalidOperation,ValueError): return Decimal("0")

@purchases_bp.route("/")
@role_required("admin","manager")
def index(): return render_template("purchases/list.html",purchases=Purchase.query.order_by(Purchase.purchase_date.desc(),Purchase.id.desc()).all())

@purchases_bp.route("/new",methods=["GET","POST"])
@role_required("admin","manager")
def create():
    suppliers=Supplier.query.filter_by(active=True).order_by(Supplier.name).all(); parts=Part.query.filter_by(active=True).order_by(Part.name).all()
    if request.method=="POST":
        supplier=db.session.get(Supplier,request.form.get("supplier_id",type=int)); purchase_date=request.form.get("purchase_date") or date.today().isoformat(); lines=[]
        for pid,q,c in zip(request.form.getlist("part_id"),request.form.getlist("quantity"),request.form.getlist("unit_cost")):
            part=db.session.get(Part,int(pid)) if pid else None; qty=dec(q); cost=dec(c)
            if part and qty>0 and cost>=0: lines.append((part,qty,cost))
        if not supplier or not lines:
            flash("Select a supplier and add at least one valid part line.","error"); return render_template("purchases/form.html",suppliers=suppliers,parts=parts,today=date.today().isoformat())
        number=f"PUR-{date.today().strftime('%Y%m%d')}-{(Purchase.query.count()+1):04d}"; purchase=Purchase(purchase_number=number,supplier_id=supplier.id,bill_number=request.form.get("bill_number","").strip() or None,purchase_date=date.fromisoformat(purchase_date),notes=request.form.get("notes","").strip() or None,created_by=current_user_id()); db.session.add(purchase); db.session.flush()
        for part,qty,cost in lines:
            db.session.add(PurchaseItem(purchase_id=purchase.id,part_id=part.id,quantity=qty,unit_cost=cost)); part.quantity+=qty; part.cost_price=cost; part.supplier=supplier.name; db.session.add(StockMovement(part_id=part.id,user_id=current_user_id(),movement_type="IN",quantity=qty,reference=number,notes=f"Supplier purchase {supplier.name}"))
        db.session.commit(); flash(f"Purchase {number} saved and stock updated.","success"); return redirect(url_for("purchases.view",purchase_id=purchase.id))
    return render_template("purchases/form.html",suppliers=suppliers,parts=parts,today=date.today().isoformat())

@purchases_bp.route("/<int:purchase_id>")
@role_required("admin","manager")
def view(purchase_id):
    row=db.session.get(Purchase,purchase_id)
    if row is None: abort(404)
    returned={i.id: dec(db.session.query(func.coalesce(func.sum(PurchaseReturn.quantity),0)).filter(PurchaseReturn.purchase_item_id==i.id).scalar()) for i in row.items}
    return render_template("purchases/view.html",purchase=row,returned=returned)

@purchases_bp.route("/<int:purchase_id>/return",methods=["POST"])
@role_required("admin","manager")
def return_item(purchase_id):
    purchase=db.session.get(Purchase,purchase_id); item=db.session.get(PurchaseItem,request.form.get("purchase_item_id",type=int)); qty=dec(request.form.get("quantity")); reason=request.form.get("reason","").strip()
    if not purchase or not item or item.purchase_id!=purchase.id: abort(404)
    already=dec(db.session.query(func.coalesce(func.sum(PurchaseReturn.quantity),0)).filter(PurchaseReturn.purchase_item_id==item.id).scalar()); available=item.quantity-already
    if qty<=0 or qty>available:
        flash(f"Return quantity must be between 0 and {available}.","error"); return redirect(url_for("purchases.view",purchase_id=purchase.id))
    if not reason:
        flash("Return reason is required.","error"); return redirect(url_for("purchases.view",purchase_id=purchase.id))
    if item.part.quantity<qty:
        flash("Cannot return this quantity because current inventory stock is lower.","error"); return redirect(url_for("purchases.view",purchase_id=purchase.id))
    number=f"RET-{date.today().strftime('%Y%m%d')}-{(PurchaseReturn.query.count()+1):04d}"; ret=PurchaseReturn(return_number=number,purchase_id=purchase.id,purchase_item_id=item.id,quantity=qty,unit_cost=item.unit_cost,reason=reason,created_by=current_user_id()); db.session.add(ret); item.part.quantity-=qty; db.session.add(StockMovement(part_id=item.part_id,user_id=current_user_id(),movement_type="RETURN_TO_SUPPLIER",quantity=qty,reference=number,notes=f"Return to {purchase.supplier.name}: {reason}")); db.session.commit(); flash(f"{number} created. Inventory reduced by {qty}.","success"); return redirect(url_for("purchases.view",purchase_id=purchase.id))
