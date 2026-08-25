from datetime import datetime, timedelta
import secrets
from hashlib import sha256

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import RepairOrder, RepairCustomerConfirmation
from app.security import role_required, current_user_id

customer_status_bp = Blueprint("customer_status", __name__, url_prefix="/customer-status")
OTP_TTL_MINUTES = 10
MAX_OTP_ATTEMPTS = 5


def _otp_hash(otp: str) -> str:
    return sha256(otp.encode("utf-8")).hexdigest()


@customer_status_bp.route("/repair/<int:repair_id>")
def repair_status(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id, deleted_at=None).first_or_404()
    return render_template("customer_status/repair.html", repair=repair)


@customer_status_bp.route("/repair/<int:repair_id>/request-otp", methods=["POST"])
@role_required("admin", "staff", "technician")
def request_otp(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id, deleted_at=None).first_or_404()
    confirmation = repair.customer_confirmation
    otp = f"{secrets.randbelow(1_000_000):06d}"
    if confirmation is None:
        confirmation = RepairCustomerConfirmation(repair_id=repair.id)
    confirmation.otp_hash = _otp_hash(otp)
    confirmation.otp_expires_at = datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)
    confirmation.attempts = 0
    confirmation.requested_by_id = current_user_id()
    confirmation.verified_at = None
    confirmation.cancelled_at = None
    db.session.add(confirmation)
    db.session.commit()
    flash("OTP generated. Connect the SMS/WhatsApp provider to deliver it to the customer.", "success")
    return redirect(url_for("customer_status.repair_status", repair_id=repair.id))


@customer_status_bp.route("/repair/<int:repair_id>/verify", methods=["POST"])
def verify(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id, deleted_at=None).first_or_404()
    confirmation = repair.customer_confirmation
    if not confirmation or confirmation.cancelled_at or not confirmation.otp_hash:
        flash("No active confirmation request", "error")
        return redirect(url_for("customer_status.repair_status", repair_id=repair.id))
    if confirmation.otp_expires_at is None or datetime.utcnow() > confirmation.otp_expires_at:
        flash("OTP has expired", "error")
        return redirect(url_for("customer_status.repair_status", repair_id=repair.id))
    if confirmation.attempts >= MAX_OTP_ATTEMPTS:
        flash("Too many OTP attempts", "error")
        return redirect(url_for("customer_status.repair_status", repair_id=repair.id))

    confirmation.attempts += 1
    supplied = request.form.get("otp", "").strip()
    if not supplied or not secrets.compare_digest(_otp_hash(supplied), confirmation.otp_hash):
        db.session.commit()
        flash("Invalid OTP", "error")
        return redirect(url_for("customer_status.repair_status", repair_id=repair.id))

    confirmation.verified_at = datetime.utcnow()
    confirmation.otp_hash = None
    db.session.commit()
    flash("Customer confirmation verified", "success")
    return redirect(url_for("customer_status.repair_status", repair_id=repair.id))
