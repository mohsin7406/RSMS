from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for, g

from app.extensions import db
from app.models import RepairOrder, RepairQC
from app.models.qc import QC_STATUSES
from app.security import role_required

qc_bp = Blueprint("qc", __name__, url_prefix="/qc")
DEFAULT_CHECKS = (
    "Power / boot",
    "Display / touch",
    "Face ID / Touch ID",
    "Cameras",
    "Microphone / speaker",
    "Charging",
    "Wi-Fi / Bluetooth",
    "Network / SIM",
    "Buttons",
    "Physical condition",
)


@qc_bp.route("/repair/<int:repair_id>")
@role_required("admin", "staff", "technician")
def qc_detail(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id).first_or_404()
    qc = repair.qc
    return render_template("qc/detail.html", repair=repair, qc=qc, checks=DEFAULT_CHECKS)


@qc_bp.route("/repair/<int:repair_id>", methods=["POST"])
@role_required("admin", "staff", "technician")
def save_qc(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id).first_or_404()
    qc = repair.qc or RepairQC(repair_id=repair.id)
    status = request.form.get("status", "Pending")
    if status not in QC_STATUSES:
        flash("Invalid QC status", "error")
        return redirect(url_for("qc.qc_detail", repair_id=repair.id))

    checklist = {key: request.form.get(f"check_{idx}", "") for idx, key in enumerate(DEFAULT_CHECKS)}
    notes = request.form.get("notes", "").strip() or None
    if status == "Passed" and any(value not in {"pass", "na"} for value in checklist.values()):
        flash("Every QC item must pass or be marked N/A before QC can be passed", "error")
        return redirect(url_for("qc.qc_detail", repair_id=repair.id))

    qc.status = status
    qc.checklist = checklist
    qc.notes = notes
    qc.tested_by_id = g.current_user.id if g.current_user else None
    qc.tested_at = datetime.utcnow()
    db.session.add(qc)

    if status == "Passed":
        repair.status = "Ready"
    elif status == "Failed":
        repair.status = "In Repair"
    db.session.commit()
    flash(f"QC marked {status}", "success")
    return redirect(url_for("qc.qc_detail", repair_id=repair.id))
