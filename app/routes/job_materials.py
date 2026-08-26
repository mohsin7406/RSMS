from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from app.extensions import db
from app.models import JobPurchase, Part, PartUsage, RepairOrder, StockMovement
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
    parts = Part.query.filter(Part.active.is_(True), Part.quantity > 0).order_by(Part.name.asc()).all()
    inventory_cost = sum((usage.cost_total for usage in repair.parts_used), Decimal("0"))
    inventory_sale = sum((usage.sale_total for usage in repair.parts_used), Decimal("0"))
    purchase_cost = sum((purchase.cost_total for purchase in repair.job_purchases), Decimal("0"))
    purchase_sale = sum((purchase.sale_total for purchase in repair.job_purchases), Decimal("0"))
    return render_template(
        "repairs/materials.html",
        repair=repair,
        parts=parts,
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
    usage = PartUsage(
        repair_id=repair.id,
        part_id=part.id,
        quantity=quantity,
        unit_cost=part.cost_price,
        unit_price=unit_price,
    )
    db.session.add(usage)
    db.session.add(
        StockMovement(
            part_id=part.id,
            user_id=current_user_id(),
            movement_type="OUT",
            quantity=quantity,
            reference=repair.job_number,
            notes="Used on repair",
        )
    )
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

    purchase = JobPurchase(
        repair_id=repair.id,
        item_name=item_name,
        quantity=quantity,
        unit_cost=unit_cost,
        unit_price=unit_price,
        supplier=request.form.get("supplier", "").strip() or None,
        reference=request.form.get("reference", "").strip() or None,
        added_by_id=current_user_id(),
    )
    db.session.add(purchase)
    db.session.commit()
    flash(f"{item_name} recorded as purchased for this job", "success")
    return redirect(url_for("materials.repair_materials", repair_id=repair_id))
