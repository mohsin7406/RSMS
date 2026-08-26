from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Booking, Customer, Lead, LeadContact, User
from app.models.lead import LEAD_STATUSES
from app.models.lead_contact import CONTACT_METHODS, CONTACT_OUTCOMES
from app.security import current_user_id, permission_required

leads_bp = Blueprint("leads", __name__, url_prefix="/leads")


def _booking_number():
    today = datetime.now().strftime("%Y%m%d")
    latest = Booking.query.filter(Booking.booking_number.like(f"BOOK-{today}-%")).order_by(Booking.id.desc()).first()
    seq = int(latest.booking_number.rsplit("-", 1)[-1]) + 1 if latest else 1
    return f"BOOK-{today}-{seq:04d}"


def _find_or_create_customer(lead):
    customer = db.session.get(Customer, lead.customer_id) if lead.customer_id else None
    if customer:
        return customer
    customer = Customer.query.filter_by(phone=lead.phone).order_by(Customer.id.asc()).first()
    if customer is None and lead.email:
        customer = Customer.query.filter_by(email=lead.email).first()
    if customer is None:
        customer = Customer(name=lead.name, phone=lead.phone, email=lead.email)
        db.session.add(customer)
        db.session.flush()
    lead.customer_id = customer.id
    return customer


@leads_bp.route("/")
@permission_required("leads")
def list_leads():
    leads = Lead.query.order_by(Lead.created_at.desc()).all()
    return render_template("leads/list.html", leads=leads, statuses=LEAD_STATUSES)


@leads_bp.route("/<int:id>")
@permission_required("leads")
def lead_detail(id):
    lead = Lead.query.get_or_404(id)
    return render_template("leads/detail.html", lead=lead, methods=CONTACT_METHODS, outcomes=CONTACT_OUTCOMES)


@leads_bp.route("/add", methods=["GET", "POST"])
@permission_required("leads")
def add_lead():
    staff = User.query.filter(User.role.in_(["admin", "manager", "staff", "reception"])).order_by(User.email.asc()).all()
    if request.method == "POST":
        status = request.form.get("status", "New")
        if status not in LEAD_STATUSES:
            flash("Invalid lead status", "error")
            return render_template("leads/form.html", staff=staff, statuses=LEAD_STATUSES)
        lead = Lead(
            name=request.form.get("name", "").strip(), phone=request.form.get("phone", "").strip(),
            email=request.form.get("email", "").strip() or None, device=request.form.get("device", "").strip() or None,
            issue=request.form.get("issue", "").strip() or None, source=request.form.get("source", "").strip() or None,
            area=request.form.get("area", "").strip() or None, service_type=request.form.get("service_type", "Doorstep"),
            status=status, assigned_to_id=request.form.get("assigned_to_id", type=int), notes=request.form.get("notes", "").strip() or None,
        )
        if not lead.name or not lead.phone:
            flash("Name and phone are required", "error")
            return render_template("leads/form.html", staff=staff, statuses=LEAD_STATUSES)
        db.session.add(lead)
        db.session.commit()
        flash("Lead created", "success")
        return redirect(url_for("leads.lead_detail", id=lead.id))
    return render_template("leads/form.html", staff=staff, statuses=LEAD_STATUSES)


@leads_bp.route("/<int:id>/contact", methods=["POST"])
@permission_required("leads")
def add_contact(id):
    lead = Lead.query.get_or_404(id)
    method = request.form.get("method", "Call")
    outcome = request.form.get("outcome", "Follow Up")
    notes = request.form.get("notes", "").strip() or None
    if method not in CONTACT_METHODS or outcome not in CONTACT_OUTCOMES:
        flash("Invalid contact method or outcome", "error")
        return redirect(url_for("leads.lead_detail", id=id))
    db.session.add(LeadContact(lead_id=lead.id, user_id=current_user_id(), method=method, outcome=outcome, notes=notes))
    if outcome == "Follow Up":
        lead.status = "Follow Up"
    elif outcome == "Not Interested":
        lead.status = "Not Interested"
    elif lead.status not in {"Booked", "Lost", "Not Interested"}:
        lead.status = "Contacted"
    db.session.commit()
    flash("Contact attempt recorded", "success")
    return redirect(url_for("leads.lead_detail", id=id))


@leads_bp.route("/<int:id>/confirm", methods=["POST"])
@permission_required("leads")
def confirm_lead(id):
    lead = Lead.query.get_or_404(id)
    if lead.booking_id:
        flash("This lead already has a booking", "success")
        return redirect(url_for("bookings.list_bookings"))
    try:
        scheduled_at = datetime.fromisoformat(request.form.get("scheduled_at", "").strip())
    except ValueError:
        flash("Select a valid booking date and time", "error")
        return redirect(url_for("leads.lead_detail", id=id))

    customer = _find_or_create_customer(lead)
    booking = Booking(
        booking_number=_booking_number(), customer_id=customer.id, service_type=lead.service_type,
        scheduled_at=scheduled_at, area=lead.area,
        notes=" | ".join(filter(None, [lead.device, lead.issue, lead.notes])), status="Confirmed",
    )
    db.session.add(booking)
    db.session.flush()
    lead.booking_id = booking.id
    lead.status = "Booked"
    db.session.add(LeadContact(lead_id=lead.id, user_id=current_user_id(), method="Other", outcome="Confirmed", notes=f"Confirmed as booking {booking.booking_number}"))
    db.session.commit()
    flash(f"Lead confirmed and moved to booking {booking.booking_number}", "success")
    return redirect(url_for("bookings.list_bookings"))


@leads_bp.route("/<int:id>/status", methods=["POST"])
@permission_required("leads")
def update_status(id):
    lead = Lead.query.get_or_404(id)
    status = request.form.get("status", "")
    if status not in LEAD_STATUSES:
        flash("Invalid lead status", "error")
        return redirect(url_for("leads.list_leads"))
    if status == "Booked" and not lead.booking_id:
        flash("Use Confirm & Create Booking so the booking is actually created", "error")
        return redirect(url_for("leads.lead_detail", id=id))
    lead.status = status
    db.session.commit()
    flash("Lead status updated", "success")
    return redirect(url_for("leads.list_leads"))


@leads_bp.route("/<int:id>/assign", methods=["POST"])
@permission_required("leads")
def assign_lead(id):
    lead = Lead.query.get_or_404(id)
    lead.assigned_to_id = request.form.get("assigned_to_id", type=int)
    db.session.commit()
    flash("Lead assigned", "success")
    return redirect(url_for("leads.lead_detail", id=id))
