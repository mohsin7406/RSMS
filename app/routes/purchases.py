from datetime import date
from decimal import Decimal, InvalidOperation
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from app.extensions import db
from app.models import Part, Purchase, PurchaseItem, StockMovement, Supplier
from app.security import current_user_id, role_required

purchases_bp=Blueprint("purchases",__name__,url_prefix="/purchases")

def dec(v):
    try: return Decimal(v or "0")
    except (InvalidOperation,ValueError): return Decimal("0")

@purchases_bp.route("/")
@role_required("admin","manager")
def index():
    rows=Purchase.query.order_by(Purchase.purchase_date.desc(),Purchase.id.desc()).all()
    return render_template("purchases/list.html",purchases=rows)

@purchases_bp.route("/new",methods=["GET","POST"])
@role_required("admin","manager")
def create():
    suppliers=Supplier.query.filter_by(active=True).order_by(Supplier.name).all(); parts=Part.query.filter_by(active=True).order_by(Part.name).all()
    if request.method=="POST":
        supplier=db.session.get(Supplier,request.form.get("supplier_id",type=int)); purchase_date=request.form.get("purchase_date") or date.today().isoformat()
        part_ids=request.form.getlist("part_id"); quantities=request.form.getlist("quantity"); costs=request.form.getlist("unit_cost")
        lines=[]
        for pid,q,c in zip(part_ids,quantities,costs):
            part=db.session.get(Part,int(pid)) if pid else None; qty=dec(q); cost=dec(c)
            if part and qty>0 and cost>=0: lines.append((part,qty,cost))
        if not supplier or not lines:
            flash("Select a supplier and add at least one valid part line.","error"); return render_template("purchases/form.html",suppliers=suppliers,parts=parts,today=date.today().isoformat())
        number=f"PUR-{date.today().strftime('%Y%m%d')}-{(Purchase.query.count()+1):04d}"
        purchase=Purchase(purchase_number=number,supplier_id=supplier.id,bill_number=request.form.get("bill_number","").strip() or None,purchase_date=date.fromisoformat(purchase_date),notes=request.form.get("notes","").strip() or None,created_by=current_user_id()); db.session.add(purchase); db.session.flush()
        for part,qty,cost in lines:
            db.session.add(PurchaseItem(purchase_id=purchase.id,part_id=part.id,quantity=qty,unit_cost=cost)); part.quantity+=qty; part.cost_price=cost; part.supplier=supplier.name; db.session.add(StockMovement(part_id=part.id,user_id=current_user_id(),movement_type="IN",quantity=qty,reference=number,notes=f"Supplier purchase {supplier.name}"))
        db.session.commit(); flash(f"Purchase {number} saved and stock updated.","success"); return redirect(url_for("purchases.view",purchase_id=purchase.id))
    return render_template("purchases/form.html",suppliers=suppliers,parts=parts,today=date.today().isoformat())

@purchases_bp.route("/<int:purchase_id>")
@role_required("admin","manager")
def view(purchase_id):
    row=db.session.get(Purchase,purchase_id)
    if row is None: abort(404)
    return render_template("purchases/view.html",purchase=row)
