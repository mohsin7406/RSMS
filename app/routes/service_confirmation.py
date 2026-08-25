from datetime import datetime
from hashlib import sha256
import secrets

from flask import Blueprint, flash, redirect, request, url_for, g

from app.extensions import db
from app.models import RepairOrder, ServiceConfirmation
from app.security import role_required, current_user_id, login_required

confirmation_bp = Blueprint("confirmation", __name__, url_prefix="/service-confirmation")


def _hash(value):
    return sha256(value.encode("utf-8")).hexdigest()


@confirmation_bp.route("/<int:repair_id>/send", methods=["POST"])
@role_required("admin", "staff", "technician")
def send_confirmation(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id).first_or_404()
    confirmation = repair.service_confirmation or ServiceConfirmation(repair_id=repair.id)
    otp = f"{secrets.randbelow(1_000_000):06d}"
    confirmation.otp_hash = _hash(otp)
    confirmation.otp_verified = False
    confirmation.customer_confirmed = False
    db.session.add(confirmation)
    db.session.commit()
    # Do not expose OTP in production response; notification provider will consume it later.
    flash("Customer confirmation OTP generated and queued for delivery", "success")
    return redirect(url_for("repair.view_repair", id=repair_id))


@confirmation_bp.route("/<int:repair_id>/verify", methods=["POST"])
@login_required
def verify_confirmation(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id).first_or_404()
    confirmation = repair.service_confirmation
    if not confirmation or not confirmation.otp_hash:
        flash("No active confirmation request", "error")
        return redirect(url_for("repair.view_repair", id=repair_id))
    otp = request.form.get("otp", "").strip()
    if len(otp) != 6 or not otp.isdigit() or _hash(otp) != confirmation.otp_hash:
        flash("Invalid confirmation OTP", "error")
        return redirect(url_for("repair.view_repair", id=repair_id))
    confirmation.otp_verified = True
    confirmation.customer_confirmed = True
    confirmation.confirmed_at = datetime.utcnow()
    confirmation.confirmed_by_id = current_user_id()
    db.session.commit()
    flash("Customer confirmation verified", "success")
    return redirect(url_for("repair.view_repair", id=repair_id))


@confirmation_bp.route("/<int:repair_id>/cancel", methods=["POST"])
@role_required("admin", "staff")
def cancel_confirmation(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id).first_or_404()
    if repair.service_confirmation:
        repair.service_confirmation.otp_hash = None
        repair.service_confirmation.otp_verified = False
        repair.service_confirmation.customer_confirmed = False
        db.session.commit()
    flash("Customer confirmation request cancelled", "success")
    return redirect(url_for("repair.view_repair", id=repair_id))
