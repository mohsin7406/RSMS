from datetime import datetime, timedelta, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for, g, abort

from app.extensions import db
from app.models import RepairOrder, WarrantyClaim
from app.models.warranty_claim import WARRANTY_STATUSES
from app.security import login_required, role_required

warranty_bp = Blueprint("warranty", __name__, url_prefix="/warranty")


def _as_utc(value):
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


@warranty_bp.route("/repair/<int:repair_id>")
@login_required
def repair_warranty(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id).first_or_404()
    warranty_until = None
    delivered_at = _as_utc(repair.delivered_at)
    if delivered_at and repair.warranty_days:
        warranty_until = delivered_at + timedelta(days=repair.warranty_days)
    return render_template("warranty/repair.html", repair=repair, warranty_until=warranty_until)


@warranty_bp.route("/repair/<int:repair_id>/claim", methods=["POST"])
@role_required("admin", "staff", "technician")
def open_claim(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id).first_or_404()
    issue = request.form.get("issue", "").strip()
    if not issue:
        flash("Warranty issue is required", "error")
        return redirect(url_for("warranty.repair_warranty", repair_id=repair_id))
    if not repair.delivered_at or not repair.warranty_days:
        flash("This repair has no active warranty", "error")
        return redirect(url_for("warranty.repair_warranty", repair_id=repair_id))
    warranty_until = _as_utc(repair.delivered_at) + timedelta(days=repair.warranty_days)
    if datetime.now(timezone.utc) > warranty_until:
        flash("Warranty period has expired", "error")
        return redirect(url_for("warranty.repair_warranty", repair_id=repair_id))

    claim = WarrantyClaim(
        repair_id=repair.id,
        customer_id=repair.customer_id,
        issue=issue,
        status="Open",
        handled_by_id=g.current_user.id if g.current_user else None,
    )
    db.session.add(claim)
    db.session.commit()
    flash("Warranty claim opened", "success")
    return redirect(url_for("warranty.repair_warranty", repair_id=repair_id))


@warranty_bp.route("/claim/<int:claim_id>", methods=["POST"])
@role_required("admin", "staff", "technician")
def update_claim(claim_id):
    claim = db.session.get(WarrantyClaim, claim_id)
    if claim is None:
        abort(404)
    status = request.form.get("status", claim.status)
    if status not in WARRANTY_STATUSES:
        flash("Invalid warranty status", "error")
        return redirect(url_for("warranty.repair_warranty", repair_id=claim.repair_id))
    claim.status = status
    claim.resolution = request.form.get("resolution", "").strip() or claim.resolution
    claim.handled_by_id = g.current_user.id if g.current_user else claim.handled_by_id
    if status in {"Resolved", "Closed", "Rejected"}:
        claim.resolved_at = claim.resolved_at or datetime.now(timezone.utc)
    db.session.commit()
    flash("Warranty claim updated", "success")
    return redirect(url_for("warranty.repair_warranty", repair_id=claim.repair_id))
