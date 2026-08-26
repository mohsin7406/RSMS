from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Booking, RepairOrder, RepairAuditLog, RepairQC
from app.models.repair import REPAIR_STATUSES
from app.routes.repair_order import REPAIR_TRANSITIONS
from app.security import role_required, current_user_id


technician_bp = Blueprint("technician", __name__, url_prefix="/technician")


@technician_bp.route("/")
@role_required("technician")
def dashboard():
    bookings = Booking.query.filter_by(technician_id=current_user_id()).order_by(Booking.scheduled_at.asc()).all()
    repairs = (
        RepairOrder.query
        .filter_by(assigned_technician_id=current_user_id())
        .filter(RepairOrder.deleted_at.is_(None))
        .order_by(RepairOrder.updated_at.desc())
        .all()
    )
    return render_template("technician/dashboard.html", bookings=bookings, repairs=repairs, statuses=REPAIR_STATUSES)


@technician_bp.route("/booking/<int:id>/status", methods=["POST"])
@role_required("technician")
def booking_status(id):
    booking = db.session.get(Booking, id)
    if booking is None:
        from flask import abort
        abort(404)
    if booking.technician_id != current_user_id():
        return ("Forbidden", 403)
    status = request.form.get("status", "")
    if status not in ("Scheduled", "Confirmed", "On The Way", "Started", "Completed", "Cancelled", "Rescheduled"):
        flash("Invalid booking status", "error")
        return redirect(url_for("technician.dashboard"))
    booking.status = status
    db.session.commit()
    return redirect(url_for("technician.dashboard"))


@technician_bp.route("/repair/<int:id>/status", methods=["POST"])
@role_required("technician")
def repair_status(id):
    repair = db.session.get(RepairOrder, id)
    if repair is None:
        from flask import abort
        abort(404)
    if repair.deleted_at is not None:
        return ("Not Found", 404)
    if repair.assigned_technician_id != current_user_id():
        return ("Forbidden", 403)

    status = request.form.get("status", "")
    if status not in REPAIR_STATUSES:
        flash("Invalid repair status", "error")
        return redirect(url_for("technician.dashboard"))
    if status != repair.status and status not in REPAIR_TRANSITIONS.get(repair.status, set()):
        flash(f"Invalid status transition: {repair.status} → {status}", "error")
        return redirect(url_for("technician.dashboard"))

    qc = RepairQC.query.filter_by(repair_id=repair.id).first()
    if status == "In Repair" and (qc is None or qc.before_status not in {"Passed", "Waived"}):
        flash("QC Before Repair must be passed or waived before repair work can start", "error")
        return redirect(url_for("technician.dashboard"))
    if status == "Ready":
        flash("QC After Repair must be passed before the repair can be marked Ready", "error")
        return redirect(url_for("technician.dashboard"))
    if status == "Delivered":
        flash("Technicians cannot mark repairs Delivered", "error")
        return redirect(url_for("technician.dashboard"))

    old = repair.status
    if old != status:
        repair.status = status
        db.session.add(
            RepairAuditLog(
                repair_id=repair.id,
                user_id=current_user_id(),
                action="status_changed",
                old_value=old,
                new_value=status,
            )
        )
    db.session.commit()
    return redirect(url_for("technician.dashboard"))
