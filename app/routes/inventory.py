from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import JobPurchase, JobPurchaseReturn, Part, StockMovement
from app.security import permission_required

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


def _decimal(value):
    try:
        amount = Decimal(value or "0")
        return amount if amount >= 0 else Decimal("0")
    except (InvalidOperation, ValueError):
        return Decimal("0")


@inventory_bp.route("/")
@permission_required("inventory")
def list_parts():
    parts = Part.query.filter_by(active=True).order_by(Part.name.asc()).all()
    low_stock = [p for p in parts if p.quantity <= p.reorder_level]
    return render_template("inventory/list.html", parts=parts, low_stock=low_stock)


@inventory_bp.route("/report")
@permission_required("inventory")
def inventory_report():
    parts = Part.query.filter_by(active=True).order_by(Part.name.asc()).all()
    low_stock = [part for part in parts if part.quantity <= part.reorder_level]
    totals = {
        "skus": len(parts),
        "units": sum((part.quantity for part in parts), Decimal("0")),
        "cost_value": sum((part.quantity * part.cost_price for part in parts), Decimal("0")),
        "retail_value": sum((part.quantity * part.selling_price for part in parts), Decimal("0")),
        "low_stock": len(low_stock),
    }
    movements = StockMovement.query.order_by(StockMovement.created_at.desc()).limit(100).all()
    pending_job_purchases = [purchase for purchase in JobPurchase.query.order_by(JobPurchase.created_at.desc()).all() if purchase.remaining_quantity > 0]
    returns = JobPurchaseReturn.query.order_by(JobPurchaseReturn.created_at.desc()).limit(100).all()
    returned_to_inventory = sum((row.quantity for row in returns if row.destination == "Inventory"), Decimal("0"))
    returned_to_supplier = sum((row.quantity for row in returns if row.destination == "Supplier"), Decimal("0"))
    return render_template(
        "inventory/report.html",
        parts=parts,
        low_stock=low_stock,
        totals=totals,
        movements=movements,
        pending_job_purchases=pending_job_purchases,
        returns=returns,
        returned_to_inventory=returned_to_inventory,
        returned_to_supplier=returned_to_supplier,
    )


@inventory_bp.route("/add", methods=["GET", "POST"])
@permission_required("inventory")
def add_part():
    if request.method == "POST":
        sku = request.form.get("sku", "").strip()
        name = request.form.get("name", "").strip()
        if not sku or not name:
            flash("SKU and part name are required", "error")
            return render_template("inventory/form.html")
        if Part.query.filter_by(sku=sku).first():
            flash("SKU already exists", "error")
            return render_template("inventory/form.html")
        part = Part(
            sku=sku,
            name=name,
            brand=request.form.get("brand", "").strip() or None,
            model=request.form.get("model", "").strip() or None,
            category=request.form.get("category", "").strip() or None,
            quantity=_decimal(request.form.get("quantity")),
            reorder_level=_decimal(request.form.get("reorder_level")),
            cost_price=_decimal(request.form.get("cost_price")),
            selling_price=_decimal(request.form.get("selling_price")),
            supplier=request.form.get("supplier", "").strip() or None,
        )
        db.session.add(part)
        db.session.flush()
        if part.quantity:
            db.session.add(StockMovement(part_id=part.id, user_id=None, movement_type="IN", quantity=part.quantity, reference="OPENING", notes="Opening stock"))
        db.session.commit()
        flash("Part added", "success")
        return redirect(url_for("inventory.list_parts"))
    return render_template("inventory/form.html")


@inventory_bp.route("/stock/<int:part_id>", methods=["POST"])
@permission_required("inventory")
def adjust_stock(part_id):
    part = db.session.get(Part, part_id)
    if part is None:
        from flask import abort
        abort(404)
    quantity = _decimal(request.form.get("quantity"))
    movement_type = request.form.get("movement_type", "ADJUSTMENT")
    if quantity <= 0 or movement_type not in {"IN", "OUT", "ADJUSTMENT"}:
        flash("Invalid stock adjustment", "error")
        return redirect(url_for("inventory.list_parts"))
    if movement_type == "OUT" and part.quantity < quantity:
        flash("Insufficient stock", "error")
        return redirect(url_for("inventory.list_parts"))
    if movement_type == "OUT":
        part.quantity -= quantity
    else:
        part.quantity += quantity
    db.session.add(StockMovement(part_id=part.id, user_id=None, movement_type=movement_type, quantity=quantity, reference=request.form.get("reference", "").strip() or None, notes=request.form.get("notes", "").strip() or None))
    db.session.commit()
    flash("Stock updated", "success")
    return redirect(url_for("inventory.list_parts"))
