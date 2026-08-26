from datetime import datetime, time

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Booking, RepairOrder, RepairAuditLog, RepairQC
from app.models.repair import REPAIR_STATUSES
from app.routes.repair_order import DOORSTEP_STATUSES, DOORSTEP_TRANSITIONS, REPAIR_TRANSITIONS
from app.security import role_required, current_user_id


technician_bp = Blueprint("technician", __name__, url_prefix="/technician")


def _assigned_repairs(technician_id):
    return (
        RepairOrder.query
        .filter_by(assigned_technician_id=technician_id)
        .filter(RepairOrder.deleted_at.is_(None))
        .order_by(RepairOrder.updated_at.desc())
        .all()
    )


@technician_bp.route("/")
@role_required("technician")
def dashboard():
    technician_id = current_user_id()
    now = datetime.now()
    today_start = datetime.combine(now.date(), time.min)
    today_end = datetime.combine(now.date(), time.max)

    all_bookings = (
        Booking.query.filter_by(technician_id=technician_id)
        .filter(Booking.status.notin_(["Completed", "Cancelled"]))
        .order_by(Booking.scheduled_at.asc())
        .all()
    )
    today_bookings = [b for b in all_bookings if today_start <= b.scheduled_at <= today_end]
    upcoming_bookings = [b for b in all_bookings if b.scheduled_at > today_end]

    all_repairs = _assigned_repairs(technician_id)
    active_repairs = [r for r in all_repairs if r.status not in {"Completed", "Delivered", "Cancelled"}]
    completed_repairs = [r for r in all_repairs if r.status in {"Completed", "Delivered"}]

    qc_by_repair = {
        qc.repair_id: qc
        for qc in RepairQC.query.filter(RepairQC.repair_id.in_([r.id for r in all_repairs])).all()
    } if all_repairs else {}

    qc_before_pending = []
    qc_after_pending = []
    in_repair = []
    waiting_parts = []
    ready = []

    for repair in active_repairs:
        qc = qc_by_repair.get(repair.id)
        before_done = qc is not None and qc.before_status in {"Passed", "Waived"}
        after_done = qc is not None and qc.after_status in {"Passed", "Waived"}

        if repair.service_type == "Doorstep":
            if repair.status == "Approved" and not before_done:
                qc_before_pending.append(repair)
            elif repair.status == "Approved" and before_done and not after_done:
                qc_after_pending.append(repair)
            continue

        if repair.status in {"Approved", "Waiting Parts"} and not before_done:
            qc_before_pending.append(repair)
        if repair.status == "In Repair":
            in_repair.append(repair)
        if repair.status == "Waiting Parts":
            waiting_parts.append(repair)
        if repair.status == "QC" and not after_done:
            qc_after_pending.append(repair)
        if repair.status == "Ready":
            ready.append(repair)

    stats = {
        "today_bookings": len(today_bookings),
        "qc_before": len(qc_before_pending),
        "in_repair": len(in_repair),
        "waiting_parts": len(waiting_parts),
        "qc_after": len(qc_after_pending),
        "ready": len(ready),
        "assigned": len(active_repairs),
        "completed": len(completed_repairs),
    }

    return render_template(
        "technician/dashboard.html",
        bookings=today_bookings,
        upcoming_bookings=upcoming_bookings,
        repairs=active_repairs,
        completed_repairs=completed_repairs,
        qc_before_pending=qc_before_pending,
        qc_after_pending=qc_after_pending,
        in_repair=in_repair,
        waiting_parts=waiting_parts,
        ready=ready,
        stats=stats,
        statuses=REPAIR_STATUSES,
    )


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

    if repair.service_type == "Doorstep":
        if status not in DOORSTEP_STATUSES:
            flash("Doorstep jobs progress through QC Before and QC After, not In Repair statuses", "error")
            return redirect(url_for("technician.dashboard"))
        if status != repair.status and status not in DOORSTEP_TRANSITIONS.get(repair.status, set()):
            flash(f"Invalid Doorstep status transition: {repair.status} → {status}", "error")
            return redirect(url_for("technician.dashboard"))
    elif status != repair.status and status not in REPAIR_TRANSITIONS.get(repair.status, set()):
        flash(f"Invalid status transition: {repair.status} → {status}", "error")
        return redirect(url_for("technician.dashboard"))

    qc = RepairQC.query.filter_by(repair_id=repair.id).first()
    if repair.service_type != "Doorstep" and status == "In Repair" and (qc is None or qc.before_status not in {"Passed", "Waived"}):
        flash("QC Before Repair must be passed or waived before repair work can start", "error")
        return redirect(url_for("technician.dashboard"))
    if repair.service_type != "Doorstep" and status == "Ready":
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
