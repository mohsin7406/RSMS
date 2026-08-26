from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for, g

from app.extensions import db
from app.models import Booking, User
from app.models.booking import BOOKING_STATUSES
from app.security import permission_required, current_user_id

bookings_bp = Blueprint("bookings", __name__, url_prefix="/bookings")


def _booking_number():
    today = datetime.utcnow().strftime("%Y%m%d")
    latest = Booking.query.filter(Booking.booking_number.like(f"BOOK-{today}-%")).order_by(Booking.id.desc()).first()
    seq = int(latest.booking_number.rsplit("-", 1)[-1]) + 1 if latest else 1
    return f"BOOK-{today}-{seq:04d}"


@bookings_bp.route("/")
@permission_required("bookings")
def list_bookings():
    bookings = Booking.query.order_by(Booking.scheduled_at.asc()).all()
    return render_template("bookings/list.html", bookings=bookings, statuses=BOOKING_STATUSES)


@bookings_bp.route("/add", methods=["GET", "POST"])
@permission_required("bookings")
def add_booking():
    technicians = User.query.filter_by(role="technician").order_by(User.email.asc()).all()
    if request.method == "POST":
        try:
            scheduled_at = datetime.fromisoformat(request.form.get("scheduled_at", ""))
        except ValueError:
            flash("Invalid scheduled date and time", "error")
            return render_template("bookings/form.html", technicians=technicians)
        booking = Booking(
            booking_number=_booking_number(), customer_id=request.form.get("customer_id", type=int),
            technician_id=request.form.get("technician_id", type=int), service_type=request.form.get("service_type", "Doorstep"),
            scheduled_at=scheduled_at, address=request.form.get("address", "").strip() or None,
            area=request.form.get("area", "").strip() or None, notes=request.form.get("notes", "").strip() or None,
            status="Assigned" if request.form.get("technician_id", type=int) else "Scheduled",
        )
        if not booking.customer_id:
            flash("Customer is required", "error")
            return render_template("bookings/form.html", technicians=technicians)
        db.session.add(booking)
        db.session.commit()
        flash(f"Booking {booking.booking_number} created", "success")
        return redirect(url_for("bookings.list_bookings"))
    return render_template("bookings/form.html", technicians=technicians)


@bookings_bp.route("/<int:id>/status", methods=["POST"])
def update_status(id):
    booking = Booking.query.get_or_404(id)
    if g.current_user is None:
        from flask import abort
        abort(403)
    if g.current_user.role == "technician":
        if booking.technician_id != current_user_id():
            return ("Forbidden", 403)
    else:
        from app.roles import has_permission
        if not has_permission(g.current_user.role, "bookings"):
            from flask import abort
            abort(403)
    status = request.form.get("status", "")
    if status not in BOOKING_STATUSES:
        flash("Invalid booking status", "error")
        return redirect(url_for("bookings.list_bookings"))
    booking.status = status
    db.session.commit()
    flash("Booking status updated", "success")
    return redirect(url_for("bookings.list_bookings"))
