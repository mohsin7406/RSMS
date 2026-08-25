from datetime import datetime, timedelta
import secrets
from hashlib import sha256

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db, limiter
from app.models import RepairOrder, ServiceConfirmation
from app.services.notifications import notify_customer

customer_status_bp = Blueprint("customer_status", __name__, url_prefix="/customer-status")
OTP_TTL_MINUTES = 10
MAX_OTP_ATTEMPTS = 5


def _otp_hash(otp: str) -> str:
    return sha256(otp.encode("utf-8")).hexdigest()


def _public_token() -> str:
    return secrets.token_urlsafe(48)


@customer_status_bp.route("/repair/<token>")
def repair_status(token):
    confirmation = ServiceConfirmation.query.filter_by(public_token=token).first_or_404()
    repair = RepairOrder.query.filter_by(id=confirmation.repair_id, deleted_at=None).first_or_404()
    return render_template("customer_status/repair.html", repair=repair, confirmation=confirmation)


@customer_status_bp.route("/repair/<token>/request-otp", methods=["POST"])
@limiter.limit("3 per 10 minutes")
def request_otp(token):
    confirmation = ServiceConfirmation.query.filter_by(public_token=token).first_or_404()
    repair = RepairOrder.query.filter_by(id=confirmation.repair_id, deleted_at=None).first_or_404()
    otp = f"{secrets.randbelow(1_000_000):06d}"
    confirmation.otp_hash = _otp_hash(otp)
    confirmation.otp_expires_at = datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)
    confirmation.otp_attempts = 0
    confirmation.otp_verified = False
    confirmation.customer_confirmed = False
    db.session.commit()
    message = f"FixZone confirmation OTP for {repair.job_number}: {otp}. Valid for {OTP_TTL_MINUTES} minutes."
    notify_customer(repair.customer.phone, message)
    flash("OTP requested", "success")
    return redirect(url_for("customer_status.repair_status", token=token))


@customer_status_bp.route("/repair/<token>/verify", methods=["POST"])
@limiter.limit("5 per 10 minutes")
def verify(token):
    confirmation = ServiceConfirmation.query.filter_by(public_token=token).first_or_404()
    repair = RepairOrder.query.filter_by(id=confirmation.repair_id, deleted_at=None).first_or_404()
    if not confirmation.otp_hash:
        flash("No active confirmation request", "error")
        return redirect(url_for("customer_status.repair_status", token=token))
    if confirmation.otp_expires_at is None or datetime.utcnow() > confirmation.otp_expires_at:
        flash("OTP has expired", "error")
        return redirect(url_for("customer_status.repair_status", token=token))
    if confirmation.otp_attempts >= MAX_OTP_ATTEMPTS:
        flash("Too many OTP attempts", "error")
        return redirect(url_for("customer_status.repair_status", token=token))

    confirmation.otp_attempts += 1
    supplied = request.form.get("otp", "").strip()
    if not supplied or not secrets.compare_digest(_otp_hash(supplied), confirmation.otp_hash):
        db.session.commit()
        flash("Invalid OTP", "error")
        return redirect(url_for("customer_status.repair_status", token=token))

    confirmation.otp_verified = True
    confirmation.customer_confirmed = True
    confirmation.confirmed_at = datetime.utcnow()
    confirmation.otp_hash = None
    db.session.commit()
    flash("Customer confirmation verified", "success")
    return redirect(url_for("customer_status.repair_status", token=token))
