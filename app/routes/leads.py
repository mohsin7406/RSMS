from datetime import datetime, timezone
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from app.extensions import db
from app.models import Booking, Customer, Lead, LeadContact, User
from app.models.lead import LEAD_STATUSES
from app.models.lead_contact import CONTACT_METHODS, CONTACT_OUTCOMES
from app.security import current_user_id, permission_required
from app.services.settings import get_options, get_setting

leads_bp=Blueprint("leads",__name__,url_prefix="/leads")
PER_PAGE=20
def _booking_number():
    today=datetime.now(timezone.utc).strftime("%Y%m%d");latest=Booking.query.filter(Booking.booking_number.like(f"BOOK-{today}-%")).order_by(Booking.id.desc()).first();seq=int(latest.booking_number.rsplit("-",1)[-1])+1 if latest else 1;return f"BOOK-{today}-{seq:04d}"
def _get_lead_or_404(lead_id):
    lead=db.session.get(Lead,lead_id)
    if lead is None:abort(404)
    return lead
def _find_or_create_customer(lead):
    customer=db.session.get(Customer,lead.customer_id) if lead.customer_id else None
    if customer:return customer
    customer=Customer.query.filter_by(phone=lead.phone).order_by(Customer.id).first()
    if customer is None and lead.email:customer=Customer.query.filter_by(email=lead.email).first()
    if customer is None:customer=Customer(name=lead.name,phone=lead.phone,email=lead.email);db.session.add(customer);db.session.flush()
    lead.customer_id=customer.id;return customer
def _staff_users():return User.query.filter(User.role.in_(["admin","manager","staff","reception"])).order_by(User.email).all()
def _apply_lead_form(lead):
    lead.name=request.form.get("name","").strip();lead.phone=request.form.get("phone","").strip();lead.email=request.form.get("email","").strip() or None;lead.device=request.form.get("device","").strip() or None;lead.issue=request.form.get("issue","").strip() or None;lead.source=request.form.get("source","").strip() or None;lead.area=request.form.get("area","").strip() or None;lead.service_type=request.form.get("service_type","Doorstep");lead.assigned_to_id=request.form.get("assigned_to_id",type=int);lead.notes=request.form.get("notes","").strip() or None
    if lead.source and lead.source not in get_options("lead_sources"):return False,"Invalid lead source"
    if get_options("service_types") and lead.service_type not in get_options("service_types"):return False,"Invalid service type"
    return bool(lead.name and lead.phone),"Name and phone are required"

@leads_bp.route("/")
@permission_required("leads")
def list_leads():
    page=max(request.args.get("page",1,type=int),1);pagination=Lead.query.order_by(Lead.created_at.desc()).paginate(page=page,per_page=PER_PAGE,error_out=False);return render_template("leads/list.html",leads=pagination.items,pagination=pagination,statuses=LEAD_STATUSES)
@leads_bp.route("/<int:id>")
@permission_required("leads")
def lead_detail(id):return render_template("leads/detail.html",lead=_get_lead_or_404(id),methods=CONTACT_METHODS,outcomes=CONTACT_OUTCOMES)
@leads_bp.route("/add",methods=["GET","POST"])
@permission_required("leads")
def add_lead():
    staff=_staff_users()
    if request.method=="POST":
        status=request.form.get("status","New")
        if status not in LEAD_STATUSES:flash("Invalid lead status","error");return render_template("leads/form.html",staff=staff,statuses=LEAD_STATUSES,action="Add")
        lead=Lead(status=status);ok,error=_apply_lead_form(lead)
        if not ok:flash(error,"error");return render_template("leads/form.html",staff=staff,statuses=LEAD_STATUSES,action="Add",lead=lead)
        db.session.add(lead);db.session.commit();flash("Lead created","success");return redirect(url_for("leads.lead_detail",id=lead.id))
    return render_template("leads/form.html",staff=staff,statuses=LEAD_STATUSES,action="Add")
@leads_bp.route("/<int:id>/edit",methods=["GET","POST"])
@permission_required("leads")
def edit_lead(id):
    lead=_get_lead_or_404(id);staff=_staff_users()
    if request.method=="POST":
        ok,error=_apply_lead_form(lead)
        if not ok:flash(error,"error");return render_template("leads/form.html",staff=staff,statuses=LEAD_STATUSES,action="Edit",lead=lead)
        db.session.commit();flash("Lead updated","success");return redirect(url_for("leads.lead_detail",id=lead.id))
    return render_template("leads/form.html",staff=staff,statuses=LEAD_STATUSES,action="Edit",lead=lead)
@leads_bp.route("/<int:id>/delete",methods=["POST"])
@permission_required("leads")
def delete_lead(id):
    lead=_get_lead_or_404(id)
    if lead.booking_id:flash("Cannot delete a lead that is linked to a booking. Keep it for history or mark it Lost/Not Interested.","error");return redirect(url_for("leads.lead_detail",id=lead.id))
    db.session.delete(lead);db.session.commit();flash("Lead deleted","success");return redirect(url_for("leads.list_leads"))
@leads_bp.route("/<int:id>/contact",methods=["POST"])
@permission_required("leads")
def add_contact(id):
    lead=_get_lead_or_404(id);method=request.form.get("method","Call");outcome=request.form.get("outcome","Follow Up");notes=request.form.get("notes","").strip() or None
    if method not in CONTACT_METHODS or outcome not in CONTACT_OUTCOMES:flash("Invalid contact method or outcome","error");return redirect(url_for("leads.lead_detail",id=id))
    db.session.add(LeadContact(lead_id=lead.id,user_id=current_user_id(),method=method,outcome=outcome,notes=notes));lead.status="Follow Up" if outcome=="Follow Up" else "Not Interested" if outcome=="Not Interested" else "Contacted" if lead.status not in {"Booked","Lost","Not Interested"} else lead.status;db.session.commit();flash("Contact attempt recorded","success");return redirect(url_for("leads.lead_detail",id=id))
@leads_bp.route("/<int:id>/confirm",methods=["POST"])
@permission_required("leads")
def confirm_lead(id):
    lead=_get_lead_or_404(id)
    if lead.booking_id:flash("This lead already has a booking","success");return redirect(url_for("bookings.list_bookings"))
    try:scheduled_at=datetime.fromisoformat(request.form.get("scheduled_at","").strip())
    except ValueError:flash("Select a valid booking date and time","error");return redirect(url_for("leads.lead_detail",id=id))
    start=get_setting("booking_start_time","09:00");end=get_setting("booking_end_time","20:00");clock=scheduled_at.strftime("%H:%M")
    if start and clock<start or end and clock>end:flash(f"Booking time must be between {start} and {end}.","error");return redirect(url_for("leads.lead_detail",id=id))
    customer=_find_or_create_customer(lead);booking=Booking(booking_number=_booking_number(),customer_id=customer.id,service_type=lead.service_type,scheduled_at=scheduled_at,area=lead.area,notes=" | ".join(filter(None,[lead.device,lead.issue,lead.notes])),status="Scheduled");db.session.add(booking);db.session.flush();lead.booking_id=booking.id;lead.status="Booked";db.session.add(LeadContact(lead_id=lead.id,user_id=current_user_id(),method="Other",outcome="Confirmed",notes=f"Moved to scheduled booking {booking.booking_number}"));db.session.commit();flash(f"Lead moved to scheduled booking {booking.booking_number}. Confirm the booking to create the repair job.","success");return redirect(url_for("bookings.list_bookings"))
@leads_bp.route("/<int:id>/status",methods=["POST"])
@permission_required("leads")
def update_status(id):
    lead=_get_lead_or_404(id);status=request.form.get("status","")
    if status not in LEAD_STATUSES:flash("Invalid lead status","error");return redirect(url_for("leads.list_leads"))
    if status=="Booked" and not lead.booking_id:flash("Use Confirm & Create Booking so the booking is actually created","error");return redirect(url_for("leads.lead_detail",id=id))
    lead.status=status;db.session.commit();flash("Lead status updated","success");return redirect(url_for("leads.list_leads"))
@leads_bp.route("/<int:id>/assign",methods=["POST"])
@permission_required("leads")
def assign_lead(id):
    lead=_get_lead_or_404(id);lead.assigned_to_id=request.form.get("assigned_to_id",type=int);db.session.commit();flash("Lead assigned","success");return redirect(url_for("leads.lead_detail",id=id))
