from datetime import datetime, timezone
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, g
from app.extensions import db
from app.models import Booking, Customer, Lead, RepairOrder, User
from app.models.booking import BOOKING_STATUSES
from app.security import permission_required, current_user_id
from app.services.settings import format_number, get_bool, get_int, get_options, get_setting

bookings_bp=Blueprint("bookings",__name__,url_prefix="/bookings")
def _booking_number():
    today=datetime.now(timezone.utc).strftime("%Y%m%d");latest=Booking.query.filter(Booking.booking_number.like(f"BOOK-{today}-%")).order_by(Booking.id.desc()).first();seq=int(latest.booking_number.rsplit("-",1)[-1])+1 if latest else 1;return f"BOOK-{today}-{seq:04d}"
def _job_number():return format_number("job_prefix","JOB",RepairOrder,"job_number",datetime.now(timezone.utc))
def _ensure_repair_for_booking(booking):
    if booking.repair_id:return db.session.get(RepairOrder,booking.repair_id),False
    lead=Lead.query.filter_by(booking_id=booking.id).first();device=lead.device if lead and lead.device else "Booking device";issue=lead.issue if lead and lead.issue else booking.notes or "Issue to be diagnosed";initial="Approved" if booking.service_type=="Doorstep" and booking.technician_id else "Pending";repair=RepairOrder(job_number=_job_number(),customer_id=booking.customer_id,assigned_technician_id=booking.technician_id,device=device,issue_description=issue,service_type=booking.service_type,status=initial,customer_approved=initial=="Approved",warranty_days=get_int("default_warranty_days",0));db.session.add(repair);db.session.flush();booking.repair_id=repair.id;return repair,True
def _form_context():return {"technicians":User.query.filter_by(role="technician").order_by(User.email).all(),"customers":Customer.query.order_by(Customer.name).all()}
def _apply_booking_form(booking):
    try:booking.scheduled_at=datetime.fromisoformat(request.form.get("scheduled_at",""))
    except ValueError:return "Invalid scheduled date and time"
    booking.customer_id=request.form.get("customer_id",type=int);booking.technician_id=request.form.get("technician_id",type=int);booking.service_type=request.form.get("service_type","Doorstep");booking.address=request.form.get("address","").strip() or None;booking.area=request.form.get("area","").strip() or None;booking.notes=request.form.get("notes","").strip() or None
    if not booking.customer_id or db.session.get(Customer,booking.customer_id) is None:return "Customer is required"
    if get_options("service_types") and booking.service_type not in get_options("service_types"):return "Invalid service type"
    start=get_setting("booking_start_time","09:00");end=get_setting("booking_end_time","20:00");clock=booking.scheduled_at.strftime("%H:%M")
    if (start and clock<start) or (end and clock>end):return f"Booking time must be between {start} and {end}"
    if booking.technician_id and User.query.filter_by(id=booking.technician_id,role="technician").first() is None:return "Selected technician is invalid"
    return None
@bookings_bp.route("/")
@permission_required("bookings")
def list_bookings():return render_template("bookings/list.html",bookings=Booking.query.order_by(Booking.scheduled_at).all(),statuses=BOOKING_STATUSES,cancellation_reasons=get_options("cancellation_reasons"))
@bookings_bp.route("/add",methods=["GET","POST"])
@permission_required("bookings")
def add_booking():
    context=_form_context()
    if request.method=="POST":
        booking=Booking(booking_number=_booking_number(),status="Scheduled");error=_apply_booking_form(booking)
        if error:flash(error,"error");return render_template("bookings/form.html",action="Add",booking=booking,**context)
        if booking.technician_id:booking.status="Assigned"
        db.session.add(booking);db.session.commit();flash(f"Booking {booking.booking_number} created","success");return redirect(url_for("bookings.list_bookings"))
    return render_template("bookings/form.html",action="Add",**context)
@bookings_bp.route("/<int:id>/edit",methods=["GET","POST"])
@permission_required("bookings")
def edit_booking(id):
    booking=db.session.get(Booking,id)
    if booking is None:abort(404)
    context=_form_context()
    if request.method=="POST":
        error=_apply_booking_form(booking)
        if error:flash(error,"error");return render_template("bookings/form.html",action="Edit",booking=booking,**context)
        if booking.repair_id:
            repair=db.session.get(RepairOrder,booking.repair_id)
            if repair:
                repair.assigned_technician_id=booking.technician_id;repair.service_type=booking.service_type;repair.customer_id=booking.customer_id
                if repair.service_type=="Doorstep" and repair.status=="Pending" and booking.technician_id:
                    repair.status="Approved";repair.customer_approved=True
        db.session.commit();flash("Booking updated","success");return redirect(url_for("bookings.list_bookings"))
    return render_template("bookings/form.html",action="Edit",booking=booking,**context)
@bookings_bp.route("/<int:id>/delete",methods=["POST"])
@permission_required("bookings")
def delete_booking(id):
    booking=db.session.get(Booking,id)
    if booking is None:abort(404)
    if booking.repair_id:flash("Cannot delete a booking that is linked to a repair job.","error");return redirect(url_for("bookings.list_bookings"))
    for lead in Lead.query.filter_by(booking_id=booking.id).all():lead.booking_id=None;lead.status="Follow Up" if lead.status=="Booked" else lead.status
    db.session.delete(booking);db.session.commit();flash("Booking deleted","success");return redirect(url_for("bookings.list_bookings"))
@bookings_bp.route("/<int:id>/status",methods=["POST"])
def update_status(id):
    booking=db.session.get(Booking,id)
    if booking is None:abort(404)
    if g.current_user is None:abort(403)
    if g.current_user.role=="technician":
        if booking.technician_id!=current_user_id():return ("Forbidden",403)
    else:
        from app.roles import has_permission
        if not has_permission(g.current_user.role,"bookings"):abort(403)
    status=request.form.get("status","")
    if status not in BOOKING_STATUSES:flash("Invalid booking status","error");return redirect(url_for("bookings.list_bookings"))
    if status=="Cancelled":
        reason=request.form.get("cancellation_reason","").strip();allowed=get_options("cancellation_reasons")
        if not reason:flash("Select a cancellation reason.","error");return redirect(url_for("bookings.list_bookings"))
        if allowed and reason not in allowed:flash("Invalid cancellation reason.","error");return redirect(url_for("bookings.list_bookings"))
        booking.cancellation_reason=reason
        if booking.repair_id:
            linked=db.session.get(RepairOrder,booking.repair_id)
            if linked and linked.status in {"Pending","Approved"}:linked.status="Cancelled"
    else:
        booking.cancellation_reason=None
    booking.status=status;repair=None;created=False
    if status in {"Confirmed","Started","Completed"}:repair,created=_ensure_repair_for_booking(booking)
    db.session.commit()
    if created and repair is not None:
        if repair.service_type=="Doorstep" and repair.status=="Approved":flash(f"Booking confirmed. Doorstep job {repair.job_number} is Approved and ready for QC Before","success")
        elif repair.service_type=="Doorstep" and repair.status=="Pending" and get_bool("require_technician_assignment"):flash(f"Booking confirmed and repair {repair.job_number} created as Pending. Assign a technician to approve the Doorstep job.","success")
        else:flash(f"Booking confirmed. Linked repair {repair.job_number}","success")
    elif status=="Cancelled":flash(f"Booking cancelled: {booking.cancellation_reason}","success")
    else:flash("Booking status updated","success")
    return redirect(url_for("bookings.list_bookings"))
