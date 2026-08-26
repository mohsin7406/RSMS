from datetime import datetime, timezone
from flask import Blueprint, flash, redirect, url_for
from app.extensions import db
from app.models import Booking, Lead, RepairOrder
from app.security import role_required
from app.services.settings import format_number, get_int

conversion_bp=Blueprint("conversion",__name__)
def _new_job_number():return format_number("job_prefix","JOB",RepairOrder,"job_number",datetime.now(timezone.utc))

def _status_for_booking(booking):
    if booking.service_type=="Doorstep":return "Approved" if booking.status in {"Confirmed","Assigned","On The Way","Started","Completed"} and booking.technician_id else "Pending"
    return "Received" if booking.status in {"Started","Completed"} else "Pending"

@conversion_bp.route("/bookings/<int:booking_id>/convert",methods=["POST"])
@role_required("admin","staff")
def convert_booking(booking_id):
    booking=db.session.get(Booking,booking_id)
    if booking is None:return ("Not Found",404)
    if booking.repair_id:return redirect(url_for("repair.view_repair",id=booking.repair_id))
    repair=RepairOrder(job_number=_new_job_number(),customer_id=booking.customer_id,assigned_technician_id=booking.technician_id,device="Booking device",issue_description=booking.notes or "Issue to be diagnosed",service_type=booking.service_type,status=_status_for_booking(booking),warranty_days=get_int("default_warranty_days",0));db.session.add(repair);db.session.flush();booking.repair_id=repair.id;db.session.commit();flash(f"Booking converted to repair {repair.job_number}","success");return redirect(url_for("repair.view_repair",id=repair.id))

@conversion_bp.route("/leads/<int:lead_id>/convert",methods=["POST"])
@role_required("admin","staff")
def convert_lead(lead_id):
    lead=db.session.get(Lead,lead_id)
    if lead is None:return ("Not Found",404)
    if not lead.customer_id:flash("Lead must be linked to a customer before conversion","error");return redirect(url_for("leads.list_leads"))
    repair=RepairOrder(job_number=_new_job_number(),customer_id=lead.customer_id,device=lead.device or "Unknown device",issue_description=lead.issue or "Issue to be diagnosed",service_type=lead.service_type,status="Pending",warranty_days=get_int("default_warranty_days",0));db.session.add(repair);lead.status="Booked";db.session.flush();db.session.commit();flash(f"Lead converted to repair {repair.job_number}","success");return redirect(url_for("repair.view_repair",id=repair.id))
