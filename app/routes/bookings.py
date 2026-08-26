from datetime import datetime, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, g

from app.extensions import db
from app.models import Booking, Customer, Lead, RepairOrder, User
from app.models.booking import BOOKING_STATUSES
from app.security import permission_required, current_user_id

bookings_bp = Blueprint("bookings", __name__, url_prefix="/bookings")


def _booking_number():
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    latest = Booking.query.filter(Booking.booking_number.like(f"BOOK-{today}-%")).order_by(Booking.id.desc()).first()
    seq = int(latest.booking_number.rsplit("-", 1)[-1]) + 1 if latest else 1
    return f"BOOK-{today}-{seq:04d}"


def _job_number():
    prefix = datetime.now(timezone.utc).strftime("JOB-%Y%m%d")
    latest = RepairOrder.query.filter(RepairOrder.job_number.like(f"{prefix}-%")).order_by(RepairOrder.id.desc()).first()
    seq = int(latest.job_number.rsplit("-", 1)[-1]) + 1 if latest and latest.job_number.rsplit("-", 1)[-1].isdigit() else 1
    return f"{prefix}-{seq:04d}"


def _ensure_repair_for_booking(booking):
    if booking.repair_id:
        return db.session.get(RepairOrder, booking.repair_id), False

    lead = Lead.query.filter_by(booking_id=booking.id).first()
    device = lead.device if lead and lead.device else "Booking device"
    issue = lead.issue if lead and lead.issue else booking.notes or "Issue to be diagnosed"
    initial_status = "Approved" if booking.service_type == "Doorstep" and booking.technician_id else "Pending"

    repair = RepairOrder(
        job_number=_job_number(), customer_id=booking.customer_id,
        assigned_technician_id=booking.technician_id, device=device,
        issue_description=issue, service_type=booking.service_type,
        status=initial_status, customer_approved=initial_status == "Approved",
    )
    db.session.add(repair)
    db.session.flush()
    booking.repair_id = repair.id
    return repair, True


def _form_context():
    return {
        "technicians": User.query.filter_by(role="technician").order_by(User.email.asc()).all(),
        "customers": Customer.query.order_by(Customer.name.asc()).all(),
    }


def _apply_booking_form(booking):
    try:
        booking.scheduled_at = datetime.fromisoformat(request.form.get("scheduled_at", ""))
    except ValueError:
        return "Invalid scheduled date and time"
    booking.customer_id = request.form.get("customer_id", type=int)
    booking.technician_id = request.form.get("technician_id", type=int)
    booking.service_type = request.form.get("service_type", "Doorstep")
    booking.address = request.form.get("address", "").strip() or None
    booking.area = request.form.get("area", "").strip() or None
    booking.notes = request.form.get("notes", "").strip() or None
    if not booking.customer_id or db.session.get(Customer, booking.customer_id) is None:
        return "Customer is required"
    return None


@bookings_bp.route("/")
@permission_required("bookings")
def list_bookings():
    bookings = Booking.query.order_by(Booking.scheduled_at.asc()).all()
    return render_template("bookings/list.html", bookings=bookings, statuses=BOOKING_STATUSES)


@bookings_bp.route("/add", methods=["GET", "POST"])
@permission_required("bookings")
def add_booking():
    context = _form_context()
    if request.method == "POST":
        booking = Booking(booking_number=_booking_number(), status="Scheduled")
        error = _apply_booking_form(booking)
        if error:
            flash(error, "error")
            return render_template("bookings/form.html", action="Add", booking=booking, **context)
        if booking.technician_id:
            booking.status = "Assigned"
        db.session.add(booking)
        db.session.commit()
        flash(f"Booking {booking.booking_number} created", "success")
        return redirect(url_for("bookings.list_bookings"))
    return render_template("bookings/form.html", action="Add", **context)


@bookings_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@permission_required("bookings")
def edit_booking(id):
    booking = db.session.get(Booking, id)
    if booking is None:
        abort(404)
    context = _form_context()
    if request.method == "POST":
        error = _apply_booking_form(booking)
        if error:
            flash(error, "error")
            return render_template("bookings/form.html", action="Edit", booking=booking, **context)
        if booking.repair_id:
            repair = db.session.get(RepairOrder, booking.repair_id)
            if repair:
                repair.assigned_technician_id = booking.technician_id
                repair.service_type = booking.service_type
                repair.customer_id = booking.customer_id
        db.session.commit()
        flash("Booking updated", "success")
        return redirect(url_for("bookings.list_bookings"))
    return render_template("bookings/form.html", action="Edit", booking=booking, **context)


@bookings_bp.route("/<int:id>/delete", methods=["POST"])
@permission_required("bookings")
def delete_booking(id):
    booking = db.session.get(Booking, id)
    if booking is None:
        abort(404)
    if booking.repair_id:
        flash("Cannot delete a booking that is linked to a repair job.", "error")
        return redirect(url_for("bookings.list_bookings"))
    linked_leads = Lead.query.filter_by(booking_id=booking.id).all()
    for lead in linked_leads:
        lead.booking_id = None
        if lead.status == "Booked":
            lead.status = "Follow Up"
    db.session.delete(booking)
    db.session.commit()
    flash("Booking deleted", "success")
    return redirect(url_for("bookings.list_bookings"))


@bookings_bp.route("/<int:id>/status", methods=["POST"])
def update_status(id):
    booking = db.session.get(Booking, id)
    if booking is None:
        abort(404)
    if g.current_user is None:
        abort(403)
    if g.current_user.role == "technician":
        if booking.technician_id != current_user_id():
            return ("Forbidden", 403)
    else:
        from app.roles import has_permission
        if not has_permission(g.current_user.role, "bookings"):
            abort(403)
    status = request.form.get("status", "")
    if status not in BOOKING_STATUSES:
        flash("Invalid booking status", "error")
        return redirect(url_for("bookings.list_bookings"))

    booking.status = status
    repair = None
    created = False
    if status in {"Confirmed", "Started", "Completed"}:
        repair, created = _ensure_repair_for_booking(booking)

    db.session.commit()
    if created and repair is not None:
        if repair.service_type == "Doorstep" and repair.status == "Approved":
            flash(f"Booking confirmed. Doorstep job {repair.job_number} is Approved and ready for QC Before", "success")
        else:
            flash(f"Booking confirmed and linked to repair {repair.job_number}", "success")
    else:
        flash("Booking status updated", "success")
    return redirect(url_for("bookings.list_bookings"))
