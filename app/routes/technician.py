from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for, g

from app.extensions import db
from app.models import Booking, RepairOrder, RepairAuditLog
from app.models.repair import REPAIR_STATUSES
from app.security import role_required, current_user_id

technician_bp = Blueprint("technician", __name__, url_prefix="/technician")


@technician_bp.route("/")
@role_required("technician")
def dashboard():
    bookings = Booking.query.filter_by(technician_id=current_user_id()).order_by(Booking.scheduled_at.asc()).all()
    repairs = RepairOrder.query.filter_by(assigned_technician_id=current_user_id()).filter(RepairOrder.deleted_at.is_(None)).order_by(RepairOrder.updated_at.desc()).all()
    return render_template("technician/dashboard.html", bookings=bookings, repairs=repairs, statuses=REPAIR_STATUSES)


@technician_bp.route("/booking/<int:id>/status", methods=["POST"])
@role_required("technician")
def booking_status(id):
    booking = Booking.query.get_or_404(id)
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
    repair = RepairOrder.query.get_or_404(id)
    if repair.assigned_technician_id != current_user_id():
        return ("Forbidden", 403)
    status = request.form.get("status", "")
    allowed = {"Received", "Diagnosing", "Waiting Approval", "Approved", "Waiting Parts", "In Repair", "QC"}
    if status not in allowed:
        flash("Technicians cannot set that repair status", "error")
        return redirect(url_for("technician.dashboard"))
    old = repair.status
    if old != status:
        repair.status = status
        db.session.add(RepairAuditLog(repair_id=repair.id, user_id=current_user_id(), action="status_changed", old_value=old, new_value=status))
    if status == "Received" and repair.delivered_at is None:
        repair.delivered_at = None
    db.session.commit()
    return redirect(url_for("technician.dashboard"))
