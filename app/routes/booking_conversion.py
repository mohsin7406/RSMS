from datetime import datetime

from flask import Blueprint, flash, redirect, url_for

from app.extensions import db
from app.models import Booking, Lead, RepairOrder
from app.security import current_user_id, role_required

conversion_bp = Blueprint("conversion", __name__)


def _new_job_number():
    prefix = datetime.utcnow().strftime("JOB-%Y%m%d")
    latest = RepairOrder.query.filter(RepairOrder.job_number.like(f"{prefix}-%")).order_by(RepairOrder.id.desc()).first()
    sequence = int(latest.job_number.rsplit("-", 1)[-1]) + 1 if latest and latest.job_number.rsplit("-", 1)[-1].isdigit() else 1
    return f"{prefix}-{sequence:04d}"


@conversion_bp.route("/bookings/<int:booking_id>/convert", methods=["POST"])
@role_required("admin", "staff")
def convert_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.repair_id:
        return redirect(url_for("repair.view_repair", id=booking.repair_id))

    repair = RepairOrder(
        job_number=_new_job_number(),
        customer_id=booking.customer_id,
        assigned_technician_id=booking.technician_id,
        device="Booking device",
        issue_description=booking.notes or "Issue to be diagnosed",
        service_type=booking.service_type,
        status="Received" if booking.status in {"Started", "Completed"} else "Pending",
    )
    db.session.add(repair)
    db.session.flush()
    booking.repair_id = repair.id
    booking.status = "Completed" if booking.status == "Completed" else booking.status
    db.session.commit()
    flash(f"Booking converted to repair {repair.job_number}", "success")
    return redirect(url_for("repair.view_repair", id=repair.id))


@conversion_bp.route("/leads/<int:lead_id>/convert", methods=["POST"])
@role_required("admin", "staff")
def convert_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    if not lead.customer_id:
        flash("Lead must be linked to a customer before conversion", "error")
        return redirect(url_for("leads.list_leads"))

    repair = RepairOrder(
        job_number=_new_job_number(),
        customer_id=lead.customer_id,
        device=lead.device or "Unknown device",
        issue_description=lead.issue or "Issue to be diagnosed",
        service_type=lead.service_type,
        status="Pending",
    )
    db.session.add(repair)
    lead.status = "Converted"
    db.session.flush()
    db.session.commit()
    flash(f"Lead converted to repair {repair.job_number}", "success")
    return redirect(url_for("repair.view_repair", id=repair.id))
