from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from app.extensions import db
from app.models import InventoryCategory, JobPurchase, JobPurchaseReturn, Part, StockMovement, Supplier
from app.security import current_user_id, permission_required, role_required

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


def _decimal(value):
    try:
        amount = Decimal(value or "0")
        return amount if amount >= 0 else Decimal("0")
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _masters():
    return (InventoryCategory.query.filter_by(active=True).order_by(InventoryCategory.name).all(), Supplier.query.filter_by(active=True).order_by(Supplier.name).all())

@inventory_bp.route("/")
@permission_required("inventory")
def list_parts():
    query = Part.query.filter_by(active=True); search = request.args.get("q", "").strip(); stock = request.args.get("stock", "").strip()
    if search:
        term=f"%{search}%"; query=query.filter(or_(Part.sku.ilike(term),Part.name.ilike(term),Part.brand.ilike(term),Part.model.ilike(term),Part.category.ilike(term),Part.supplier.ilike(term)))
    parts=query.order_by(Part.name.asc()).all()
    if stock=="low": parts=[p for p in parts if p.quantity<=p.reorder_level]
    elif stock=="out": parts=[p for p in parts if p.quantity<=0]
    low_stock=[p for p in Part.query.filter_by(active=True).all() if p.quantity<=p.reorder_level]
    return render_template("inventory/list.html",parts=parts,low_stock=low_stock,search=search,stock_filter=stock)

@inventory_bp.route("/report")
@permission_required("inventory")
def inventory_report():
    parts=Part.query.filter_by(active=True).order_by(Part.name.asc()).all(); low_stock=[p for p in parts if p.quantity<=p.reorder_level]
    totals={"skus":len(parts),"units":sum((p.quantity for p in parts),Decimal("0")),"cost_value":sum((p.quantity*p.cost_price for p in parts),Decimal("0")),"retail_value":sum((p.quantity*p.selling_price for p in parts),Decimal("0")),"low_stock":len(low_stock)}
    movements=StockMovement.query.order_by(StockMovement.created_at.desc()).limit(100).all(); pending_job_purchases=[p for p in JobPurchase.query.order_by(JobPurchase.created_at.desc()).all() if p.remaining_quantity>0]; returns=JobPurchaseReturn.query.order_by(JobPurchaseReturn.created_at.desc()).limit(100).all()
    return render_template("inventory/report.html",parts=parts,low_stock=low_stock,totals=totals,movements=movements,pending_job_purchases=pending_job_purchases,returns=returns,returned_to_inventory=sum((r.quantity for r in returns if r.destination=="Inventory"),Decimal("0")),returned_to_supplier=sum((r.quantity for r in returns if r.destination=="Supplier"),Decimal("0")))

def _part_values(part):
    part.name=request.form.get("name","").strip(); part.brand=request.form.get("brand","").strip() or None; part.model=request.form.get("model","").strip() or None; part.category=request.form.get("category","").strip() or None; part.reorder_level=_decimal(request.form.get("reorder_level")); part.cost_price=_decimal(request.form.get("cost_price")); part.selling_price=_decimal(request.form.get("selling_price")); part.supplier=request.form.get("supplier","").strip() or None

@inventory_bp.route("/add",methods=["GET","POST"])
@permission_required("inventory")
def add_part():
    categories,suppliers=_masters()
    if request.method=="POST":
        sku=request.form.get("sku","").strip(); name=request.form.get("name","").strip()
        if not sku or not name: flash("SKU and part name are required","error"); return render_template("inventory/form.html",part=None,categories=categories,suppliers=suppliers)
        if Part.query.filter_by(sku=sku).first(): flash("SKU already exists","error"); return render_template("inventory/form.html",part=None,categories=categories,suppliers=suppliers)
        part=Part(sku=sku,name=name,quantity=_decimal(request.form.get("quantity"))); _part_values(part); db.session.add(part); db.session.flush()
        if part.quantity: db.session.add(StockMovement(part_id=part.id,user_id=current_user_id(),movement_type="IN",quantity=part.quantity,reference="OPENING",notes="Opening stock"))
        db.session.commit(); flash("Part added","success"); return redirect(url_for("inventory.list_parts"))
    return render_template("inventory/form.html",part=None,categories=categories,suppliers=suppliers)

@inventory_bp.route("/edit/<int:part_id>",methods=["GET","POST"])
@permission_required("inventory")
def edit_part(part_id):
    part=db.session.get(Part,part_id); categories,suppliers=_masters()
    if part is None or not part.active: abort(404)
    if request.method=="POST":
        sku=request.form.get("sku","").strip(); name=request.form.get("name","").strip(); duplicate=Part.query.filter(Part.sku==sku,Part.id!=part.id).first()
        if not sku or not name: flash("SKU and part name are required","error"); return render_template("inventory/form.html",part=part,categories=categories,suppliers=suppliers)
        if duplicate: flash("SKU already exists","error"); return render_template("inventory/form.html",part=part,categories=categories,suppliers=suppliers)
        part.sku=sku; _part_values(part); db.session.commit(); flash("Part details updated","success"); return redirect(url_for("inventory.list_parts"))
    return render_template("inventory/form.html",part=part,categories=categories,suppliers=suppliers)

@inventory_bp.route("/delete/<int:part_id>",methods=["POST"])
@role_required("admin","manager")
def delete_part(part_id):
    part=db.session.get(Part,part_id)
    if part is None or not part.active: abort(404)
    if part.quantity>0: flash("Part still has stock. Reduce or transfer stock to zero before deleting it.","error"); return redirect(url_for("inventory.list_parts"))
    part.active=False; db.session.commit(); flash(f"{part.name} removed from active inventory. Its history has been preserved.","success"); return redirect(url_for("inventory.list_parts"))

@inventory_bp.route("/stock/<int:part_id>",methods=["POST"])
@permission_required("inventory")
def adjust_stock(part_id):
    part=db.session.get(Part,part_id)
    if part is None or not part.active: abort(404)
    quantity=_decimal(request.form.get("quantity")); movement_type=request.form.get("movement_type","ADJUSTMENT")
    if quantity<=0 or movement_type not in {"IN","OUT","ADJUSTMENT"}: flash("Invalid stock adjustment","error"); return redirect(url_for("inventory.list_parts"))
    if movement_type=="OUT" and part.quantity<quantity: flash("Insufficient stock","error"); return redirect(url_for("inventory.list_parts"))
    part.quantity = part.quantity-quantity if movement_type=="OUT" else part.quantity+quantity
    db.session.add(StockMovement(part_id=part.id,user_id=current_user_id(),movement_type=movement_type,quantity=quantity,reference=request.form.get("reference","").strip() or None,notes=request.form.get("notes","").strip() or None)); db.session.commit(); flash("Stock updated","success"); return redirect(url_for("inventory.list_parts"))

@inventory_bp.route("/masters",methods=["GET"])
@role_required("admin","manager")
def masters():
    return render_template("inventory/masters.html",categories=InventoryCategory.query.order_by(InventoryCategory.active.desc(),InventoryCategory.name).all(),suppliers=Supplier.query.order_by(Supplier.active.desc(),Supplier.name).all())

@inventory_bp.route("/categories/save",methods=["POST"])
@role_required("admin","manager")
def save_category():
    name=request.form.get("name","").strip(); category_id=request.form.get("id",type=int); row=db.session.get(InventoryCategory,category_id) if category_id else None
    if not name: flash("Category name is required","error")
    elif InventoryCategory.query.filter(InventoryCategory.name==name, InventoryCategory.id!=(row.id if row else 0)).first(): flash("Category already exists","error")
    else:
        if row: row.name=name; row.active=True
        else: db.session.add(InventoryCategory(name=name))
        db.session.commit(); flash("Category saved","success")
    return redirect(url_for("inventory.masters"))

@inventory_bp.route("/categories/<int:category_id>/toggle",methods=["POST"])
@role_required("admin","manager")
def toggle_category(category_id):
    row=db.session.get(InventoryCategory,category_id)
    if row is None: abort(404)
    row.active=not row.active; db.session.commit(); flash("Category status updated","success"); return redirect(url_for("inventory.masters"))

@inventory_bp.route("/suppliers/save",methods=["POST"])
@role_required("admin","manager")
def save_supplier():
    supplier_id=request.form.get("id",type=int); row=db.session.get(Supplier,supplier_id) if supplier_id else None; name=request.form.get("name","").strip()
    if not name: flash("Supplier name is required","error"); return redirect(url_for("inventory.masters"))
    if Supplier.query.filter(Supplier.name==name,Supplier.id!=(row.id if row else 0)).first(): flash("Supplier already exists","error"); return redirect(url_for("inventory.masters"))
    if not row: row=Supplier(name=name); db.session.add(row)
    row.name=name; row.phone=request.form.get("phone","").strip() or None; row.whatsapp=request.form.get("whatsapp","").strip() or None; row.gstin=request.form.get("gstin","").strip() or None; row.address=request.form.get("address","").strip() or None; row.notes=request.form.get("notes","").strip() or None; row.active=True
    db.session.commit(); flash("Supplier saved","success"); return redirect(url_for("inventory.masters"))

@inventory_bp.route("/suppliers/<int:supplier_id>/toggle",methods=["POST"])
@role_required("admin","manager")
def toggle_supplier(supplier_id):
    row=db.session.get(Supplier,supplier_id)
    if row is None: abort(404)
    row.active=not row.active; db.session.commit(); flash("Supplier status updated","success"); return redirect(url_for("inventory.masters"))
