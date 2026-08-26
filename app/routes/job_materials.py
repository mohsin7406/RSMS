from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from app.extensions import db
from app.models import JobPurchase, JobPurchaseReturn, Part, PartUsage, RepairOrder, StockMovement
from app.security import current_user_id, role_required

materials_bp = Blueprint("materials", __name__, url_prefix="/materials")


def _money(value):
    try:
        amount = Decimal(value or "0")
        return amount if amount >= 0 else Decimal("0")
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _repair_or_404(repair_id):
    repair = RepairOrder.query.filter(
        RepairOrder.id == repair_id,
        RepairOrder.deleted_at.is_(None),
    ).first_or_404()
    if g.current_user and g.current_user.role == "technician" and repair.assigned_technician_id != g.current_user.id:
        return None
    return repair


@materials_bp.route("/repair/<int:repair_id>")
@role_required("admin", "manager", "staff", "technician")
def repair_materials(repair_id):
    repair = _repair_or_404(repair_id)
    if repair is None:
        return ("Forbidden", 403)
    parts = Part.query.filter(Part.active.is_(True)).order_by(Part.name.asc()).all()
    available_parts = [part for part in parts if part.quantity > 0]
    inventory_cost = sum((usage.cost_total for usage in repair.parts_used), Decimal("0"))
    inventory_sale = sum((usage.sale_total for usage in repair.parts_used), Decimal("0"))
    purchase_cost = sum((purchase.net_cost_total for purchase in repair.job_purchases), Decimal("0"))
    purchase_sale = sum((purchase.net_sale_total for purchase in repair.job_purchases), Decimal("0"))
    return render_template(
        "repairs/materials.html",
        repair=repair,
        parts=parts,
        available_parts=available_parts,
        inventory_cost=inventory_cost,
        inventory_sale=inventory_sale,
        purchase_cost=purchase_cost,
        purchase_sale=purchase_sale,
    )


@materials_bp.route("/repair/<int:repair_id>/inventory", methods=["POST"])
@role_required("admin", "manager", "staff", "technician")
def add_inventory_part(repair_id):
    repair = _repair_or_404(repair_id)
    if repair is None:
        return ("Forbidden", 403)
    if repair.status == "Cancelled":
        flash("Cannot add material to a cancelled job", "error")
        return redirect(url_for("materials.repair_materials", repair_id=repair_id))

    part = Part.query.filter_by(id=request.form.get("part_id", type=int), active=True).with_for_update().first_or_404()
    quantity = _money(request.form.get("quantity"))
    unit_price = _money(request.form.get("unit_price")) or part.selling_price
    if quantity <= 0:
        flash("Quantity must be greater than zero", "error")
        return redirect(url_for("materials.repair_materials", repair_id=repair_id))
    if part.quantity < quantity:
        flash(f"Insufficient stock for {part.name}. Available: {part.quantity}", "error")
        return redirect(url_for("materials.repair_materials", repair_id=repair_id))

    part.quantity -= quantity
    db.session.add(PartUsage(repair_id=repair.id, part_id=part.id, quantity=quantity, unit_cost=part.cost_price, unit_price=unit_price))
    db.session.add(StockMovement(part_id=part.id, user_id=current_user_id(), movement_type="OUT", quantity=quantity, reference=repair.job_number, notes="Used on repair"))
    db.session.commit()
    flash(f"{part.name} added from inventory", "success")
    return redirect(url_for("materials.repair_materials", repair_id=repair_id))


@materials_bp.route("/repair/<int:repair_id>/purchase", methods=["POST"])
@role_required("admin", "manager", "staff", "technician")
def add_job_purchase(repair_id):
    repair = _repair_or_404(repair_id)
    if repair is None:
        return ("Forbidden", 403)
    if repair.status == "Cancelled":
        flash("Cannot add a purchase to a cancelled job", "error")
        return redirect(url_for("materials.repair_materials", repair_id=repair_id))

    item_name = request.form.get("item_name", "").strip()
    quantity = _money(request.form.get("quantity"))
    unit_cost = _money(request.form.get("unit_cost"))
    unit_price = _money(request.form.get("unit_price"))
    if not item_name or quantity <= 0:
        flash("Item name and quantity are required", "error")
        return redirect(url_for("materials.repair_materials", repair_id=repair_id))

    db.session.add(JobPurchase(
        repair_id=repair.id,
        item_name=item_name,
        quantity=quantity,
        unit_cost=unit_cost,
        unit_price=unit_price,
        supplier=request.form.get("supplier", "").strip() or None,
        reference=request.form.get("reference", "").strip() or None,
        added_by_id=current_user_id(),
    ))
    db.session.commit()
    flash(f"{item_name} recorded as purchased for this job", "success")
    return redirect(url_for("materials.repair_materials", repair_id=repair_id))


@materials_bp.route("/purchase/<int:purchase_id>/return", methods=["POST"])
@role_required("admin", "manager")
def return_job_purchase(purchase_id):
    purchase = db.session.get(JobPurchase, purchase_id)
    if purchase is None:
        from flask import abort
        abort(404)

    quantity = _money(request.form.get("quantity"))
    destination = request.form.get("destination", "").strip()
    reason = request.form.get("reason", "").strip() or None
    if quantity <= 0 or quantity > purchase.remaining_quantity:
        flash(f"Return quantity must be between 0 and {purchase.remaining_quantity}", "error")
        return redirect(url_for("materials.repair_materials", repair_id=purchase.repair_id))
    if destination not in {"Inventory", "Supplier"}:
        flash("Choose Inventory or Supplier as the return destination", "error")
        return redirect(url_for("materials.repair_materials", repair_id=purchase.repair_id))

    inventory_part = None
    if destination == "Inventory":
        inventory_part_id = request.form.get("inventory_part_id", type=int)
        if inventory_part_id:
            inventory_part = Part.query.filter_by(id=inventory_part_id, active=True).first()
        if inventory_part is None:
            sku = f"JOBRET-{purchase.id}"
            inventory_part = Part.query.filter_by(sku=sku).first()
            if inventory_part is None:
                inventory_part = Part(
                    sku=sku,
                    name=purchase.item_name,
                    quantity=Decimal("0"),
                    reorder_level=Decimal("0"),
                    cost_price=purchase.unit_cost,
                    selling_price=purchase.unit_price,
                    supplier=purchase.supplier,
                    active=True,
                )
                db.session.add(inventory_part)
                db.session.flush()
        inventory_part.quantity += quantity
        db.session.add(StockMovement(
            part_id=inventory_part.id,
            user_id=current_user_id(),
            movement_type="IN",
            quantity=quantity,
            reference=purchase.repair.job_number,
            notes=f"Unused job purchase returned to inventory: {purchase.item_name}",
        ))

    db.session.add(JobPurchaseReturn(
        purchase_id=purchase.id,
        quantity=quantity,
        destination=destination,
        inventory_part_id=inventory_part.id if inventory_part else None,
        reason=reason,
        processed_by_id=current_user_id(),
    ))
    db.session.commit()
    flash(f"Returned {quantity} × {purchase.item_name} to {destination}", "success")
    return redirect(url_for("materials.repair_materials", repair_id=purchase.repair_id))
