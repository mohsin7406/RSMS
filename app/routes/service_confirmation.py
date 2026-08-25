from datetime import datetime, timedelta
from hashlib import sha256
import secrets

from flask import Blueprint, flash, redirect, request, url_for

from app.extensions import db
from app.models import RepairOrder, ServiceConfirmation
from app.security import current_user_id, role_required

confirmation_bp = Blueprint("confirmation", __name__, url_prefix="/service-confirmation")
OTP_TTL_MINUTES = 10


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _public_token() -> str:
    return secrets.token_urlsafe(48)


@confirmation_bp.route("/<int:repair_id>/send", methods=["POST"])
@role_required("admin", "staff", "technician")
def send_confirmation(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id, deleted_at=None).first_or_404()
    confirmation = repair.service_confirmation or ServiceConfirmation(repair_id=repair.id)
    if not confirmation.public_token:
        confirmation.public_token = _public_token()
    otp = f"{secrets.randbelow(1_000_000):06d}"
    confirmation.otp_hash = _hash(otp)
    confirmation.otp_expires_at = datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)
    confirmation.otp_attempts = 0
    confirmation.otp_verified = False
    confirmation.customer_confirmed = False
    db.session.add(confirmation)
    db.session.commit()
    flash("Customer confirmation OTP queued for delivery", "success")
    return redirect(url_for("repair.view_repair", id=repair_id))


@confirmation_bp.route("/<int:repair_id>/verify", methods=["POST"])
def verify_confirmation(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id, deleted_at=None).first_or_404()
    confirmation = repair.service_confirmation
    if not confirmation or not confirmation.otp_hash:
        flash("No active confirmation request", "error")
        return redirect(url_for("repair.view_repair", id=repair_id))
    if confirmation.otp_expires_at is None or datetime.utcnow() > confirmation.otp_expires_at:
        flash("OTP has expired", "error")
        return redirect(url_for("repair.view_repair", id=repair_id))
    if confirmation.otp_attempts >= 5:
        flash("Too many OTP attempts", "error")
        return redirect(url_for("repair.view_repair", id=repair_id))

    confirmation.otp_attempts += 1
    otp = request.form.get("otp", "").strip()
    if len(otp) != 6 or not otp.isdigit() or not secrets.compare_digest(_hash(otp), confirmation.otp_hash):
        db.session.commit()
        flash("Invalid confirmation OTP", "error")
        return redirect(url_for("repair.view_repair", id=repair_id))
    confirmation.otp_verified = True
    confirmation.customer_confirmed = True
    confirmation.confirmed_at = datetime.utcnow()
    confirmation.confirmed_by_id = current_user_id()
    confirmation.otp_hash = None
    db.session.commit()
    flash("Customer confirmation verified", "success")
    return redirect(url_for("repair.view_repair", id=repair_id))


@confirmation_bp.route("/<int:repair_id>/cancel", methods=["POST"])
@role_required("admin", "staff")
def cancel_confirmation(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id, deleted_at=None).first_or_404()
    if repair.service_confirmation:
        repair.service_confirmation.otp_hash = None
        repair.service_confirmation.otp_expires_at = None
        repair.service_confirmation.otp_attempts = 0
        repair.service_confirmation.otp_verified = False
        repair.service_confirmation.customer_confirmed = False
        db.session.commit()
    flash("Customer confirmation request cancelled", "success")
    return redirect(url_for("repair.view_repair", id=repair_id))
