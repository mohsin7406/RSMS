import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

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
MAX_PHOTO_SIZE = 8 * 1024 * 1024
ALLOWED_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def _ensure_qc(repair):
    qc = repair.qc
    if qc is None:
        qc = RepairQC(repair_id=repair.id)
        db.session.add(qc)
        db.session.flush()
    return qc


def _photo_dir(repair, stage):
    root = Path(current_app.static_folder or "static") / "uploads" / "qc" / repair.job_number / stage
    root.mkdir(parents=True, exist_ok=True)
    return root


def _save_photos(repair, stage):
    saved = []
    for upload in request.files.getlist("photos"):
        if not upload or not upload.filename:
            continue
        filename = secure_filename(upload.filename)
        if not filename or "." not in filename:
            flash(f"Skipped invalid photo: {upload.filename}", "error")
            continue
        extension = filename.rsplit(".", 1)[1].lower()
        if extension not in ALLOWED_PHOTO_EXTENSIONS:
            flash(f"Unsupported photo type: {extension}", "error")
            continue
        upload.stream.seek(0, os.SEEK_END)
        size = upload.stream.tell()
        upload.stream.seek(0)
        if size > MAX_PHOTO_SIZE:
            flash(f"Photo {filename} is larger than 8 MB", "error")
            continue
        target = _photo_dir(repair, stage) / f"{uuid4().hex}_{filename}"
        upload.save(target)
        saved.append(f"uploads/qc/{repair.job_number}/{stage}/{target.name}")
    return saved


def _stage_fields(stage):
    if stage == "before":
        return "before_status", "before_checklist", "before_notes", "before_tested_by_id", "before_tested_at", "before_photos"
    return "after_status", "after_checklist", "after_notes", "after_tested_by_id", "after_tested_at", "after_photos"


def _stage_title(stage):
    return "QC Before Repair" if stage == "before" else "QC After Repair"


@qc_bp.route("/repair/<int:repair_id>")
@role_required("admin", "staff", "technician")
def qc_detail(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id).first_or_404()
    qc = _ensure_qc(repair)
    db.session.commit()
    stage = request.args.get("stage", "before").lower()
    if stage not in {"before", "after"}:
        stage = "before"
    return render_template("qc/detail.html", repair=repair, qc=qc, checks=DEFAULT_CHECKS, stage=stage)


@qc_bp.route("/repair/<int:repair_id>", methods=["POST"])
@role_required("admin", "staff", "technician")
def save_qc(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id).first_or_404()
    stage = request.form.get("stage", "before").lower()
    if stage not in {"before", "after"}:
        flash("Invalid QC stage", "error")
        return redirect(url_for("qc.qc_detail", repair_id=repair.id, stage="before"))
    if g.current_user and g.current_user.role == "technician" and repair.assigned_technician_id != g.current_user.id:
        return ("Forbidden", 403)

    qc = _ensure_qc(repair)
    status = request.form.get("status", "Pending")
    if status not in QC_STATUSES:
        flash("Invalid QC status", "error")
        return redirect(url_for("qc.qc_detail", repair_id=repair.id, stage=stage))

    checklist = {key: request.form.get(f"check_{idx}", "") for idx, key in enumerate(DEFAULT_CHECKS)}
    notes = request.form.get("notes", "").strip() or None
    if status == "Passed" and any(value not in {"pass", "na"} for value in checklist.values()):
        flash("Every QC item must pass or be marked N/A before QC can be passed", "error")
        return redirect(url_for("qc.qc_detail", repair_id=repair.id, stage=stage))

    status_field, checklist_field, notes_field, tester_field, tested_at_field, photos_field = _stage_fields(stage)
    existing_photos = list(getattr(qc, photos_field) or [])
    existing_photos.extend(_save_photos(repair, stage))
    setattr(qc, status_field, status)
    setattr(qc, checklist_field, checklist)
    setattr(qc, notes_field, notes)
    setattr(qc, tester_field, g.current_user.id if g.current_user else None)
    setattr(qc, tested_at_field, datetime.now(timezone.utc))
    setattr(qc, photos_field, existing_photos)

    # Keep the legacy/general QC fields synchronized with the post-repair QC.
    if stage == "after":
        qc.status = status
        qc.checklist = checklist
        qc.notes = notes
        qc.tested_by_id = g.current_user.id if g.current_user else None
        qc.tested_at = getattr(qc, tested_at_field)
        if status == "Passed":
            repair.status = "Ready"
        elif status == "Failed":
            repair.status = "In Repair"

    db.session.commit()
    flash(f"{_stage_title(stage)} marked {status}", "success")
    return redirect(url_for("qc.qc_detail", repair_id=repair.id, stage=stage))
