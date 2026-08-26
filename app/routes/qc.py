import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import QCChecklistItem, RepairOrder, RepairQC
from app.models.qc import QC_STATUSES
from app.security import permission_required
from app.services.settings import get_bool, get_int, get_setting

qc_bp=Blueprint("qc",__name__,url_prefix="/qc")
DEFAULT_CHECKS=("Power / boot","Display / touch","Face ID / Touch ID","Cameras","Microphone / speaker","Charging","Wi-Fi / Bluetooth","Network / SIM","Buttons","Physical condition")

def _checks_for_stage(stage):
    items=QCChecklistItem.query.filter(QCChecklistItem.active.is_(True),QCChecklistItem.stage.in_(["both",stage])).order_by(QCChecklistItem.sort_order,QCChecklistItem.id).all();return [i.label for i in items] if items else list(DEFAULT_CHECKS)
def _ensure_qc(repair):
    qc=repair.qc
    if qc is None:qc=RepairQC(repair_id=repair.id);db.session.add(qc);db.session.flush()
    return qc
def _photo_dir(repair,stage):
    root=Path(current_app.static_folder or "static")/"uploads"/"qc"/repair.job_number/stage;root.mkdir(parents=True,exist_ok=True);return root
def _allowed_extensions():return {x.strip().lower() for x in get_setting("allowed_image_extensions","jpg,jpeg,png,webp").split(",") if x.strip()}
def _save_photos(repair,stage):
    saved=[];max_bytes=max(get_int("max_upload_mb",8),1)*1024*1024;max_photos=max(get_int("qc_max_photos",10),1)
    uploads=[u for u in request.files.getlist("photos") if u and u.filename][:max_photos]
    for upload in uploads:
        filename=secure_filename(upload.filename)
        if not filename or "." not in filename:flash(f"Skipped invalid photo: {upload.filename}","error");continue
        extension=filename.rsplit(".",1)[1].lower()
        if extension not in _allowed_extensions():flash(f"Unsupported photo type: {extension}","error");continue
        upload.stream.seek(0,os.SEEK_END);size=upload.stream.tell();upload.stream.seek(0)
        if size>max_bytes:flash(f"Photo {filename} exceeds {get_int('max_upload_mb',8)} MB","error");continue
        target=_photo_dir(repair,stage)/f"{uuid4().hex}_{filename}";upload.save(target);saved.append(f"uploads/qc/{repair.job_number}/{stage}/{target.name}")
    return saved
def _stage_fields(stage):return ("before_status","before_checklist","before_notes","before_tested_by_id","before_tested_at","before_photos") if stage=="before" else ("after_status","after_checklist","after_notes","after_tested_by_id","after_tested_at","after_photos")
def _stage_title(stage):return "QC Before Repair" if stage=="before" else "QC After Repair"
def _validate_stage_order(repair,qc,stage):
    if stage=="before" and not get_bool("require_qc_before"):return "QC Before is disabled in System Settings"
    if stage=="after" and not get_bool("require_qc_after"):return "QC After is disabled in System Settings"
    if repair.service_type!="Doorstep":return None
    if get_bool("require_technician_assignment") and not repair.assigned_technician_id:return "Assign a technician before starting doorstep QC"
    if stage=="before" and repair.status!="Approved":return "Doorstep job must be Approved before QC Before"
    if stage=="after" and get_bool("require_qc_before") and qc.before_status not in {"Passed","Waived"}:return "QC Before must be passed or waived before QC After"
    if stage=="after" and repair.status not in {"Approved","Completed"}:return "Doorstep job must remain Approved until QC After is completed"
    return None

@qc_bp.route("/repair/<int:repair_id>")
@permission_required("qc")
def qc_detail(repair_id):
    repair=RepairOrder.query.filter_by(id=repair_id).first_or_404();qc=_ensure_qc(repair);db.session.commit();stage=request.args.get("stage","before").lower();stage=stage if stage in {"before","after"} else "before";return render_template("qc/detail.html",repair=repair,qc=qc,checks=_checks_for_stage(stage),stage=stage,allow_na=get_bool("allow_qc_na"),min_photos=get_int("qc_min_photos",0),max_photos=get_int("qc_max_photos",10),photo_required=get_bool("qc_before_photo_required" if stage=="before" else "qc_after_photo_required"))

@qc_bp.route("/repair/<int:repair_id>",methods=["POST"])
@permission_required("qc")
def save_qc(repair_id):
    repair=RepairOrder.query.filter_by(id=repair_id).first_or_404();stage=request.form.get("stage","before").lower()
    if stage not in {"before","after"}:flash("Invalid QC stage","error");return redirect(url_for("qc.qc_detail",repair_id=repair.id,stage="before"))
    if g.current_user and g.current_user.role=="technician" and repair.assigned_technician_id!=g.current_user.id:return ("Forbidden",403)
    qc=_ensure_qc(repair);error=_validate_stage_order(repair,qc,stage)
    if error:flash(error,"error");return redirect(url_for("qc.qc_detail",repair_id=repair.id,stage=stage))
    status=request.form.get("status","Pending")
    if status not in QC_STATUSES:flash("Invalid QC status","error");return redirect(url_for("qc.qc_detail",repair_id=repair.id,stage=stage))
    checks=_checks_for_stage(stage);checklist={key:request.form.get(f"check_{idx}","") for idx,key in enumerate(checks)};notes=request.form.get("notes","").strip() or None;allowed={"pass","na"} if get_bool("allow_qc_na") else {"pass"}
    if status=="Passed" and any(v not in allowed for v in checklist.values()):flash("Every active QC item must pass"+(" or be N/A" if get_bool("allow_qc_na") else ""),"error");return redirect(url_for("qc.qc_detail",repair_id=repair.id,stage=stage))
    if status=="Failed" and get_bool("qc_failed_notes_required") and not notes:flash("Notes are required when QC fails.","error");return redirect(url_for("qc.qc_detail",repair_id=repair.id,stage=stage))
    status_field,checklist_field,notes_field,tester_field,tested_at_field,photos_field=_stage_fields(stage);existing=list(getattr(qc,photos_field) or []);new=_save_photos(repair,stage);all_photos=existing+new;required=get_bool("qc_before_photo_required" if stage=="before" else "qc_after_photo_required");minimum=max(get_int("qc_min_photos",0),1 if required else 0)
    if status in {"Passed","Failed"} and len(all_photos)<minimum:flash(f"At least {minimum} QC photo(s) required for this stage.","error");return redirect(url_for("qc.qc_detail",repair_id=repair.id,stage=stage))
    setattr(qc,status_field,status);setattr(qc,checklist_field,checklist);setattr(qc,notes_field,notes);setattr(qc,tester_field,g.current_user.id if g.current_user else None);setattr(qc,tested_at_field,datetime.now(timezone.utc));setattr(qc,photos_field,all_photos)
    if repair.service_type=="Doorstep":
        if stage=="before":repair.status="Approved"
        else:
            qc.status=status;qc.checklist=checklist;qc.notes=notes;qc.tested_by_id=g.current_user.id if g.current_user else None;qc.tested_at=getattr(qc,tested_at_field);repair.status="Completed" if status in {"Passed","Waived"} else "Approved" if status=="Failed" else repair.status
    else:
        if stage=="before" and status in {"Passed","Waived"} and repair.status in {"Approved","Waiting Parts"}:repair.status="In Repair"
        elif stage=="after":
            qc.status=status;qc.checklist=checklist;qc.notes=notes;qc.tested_by_id=g.current_user.id if g.current_user else None;qc.tested_at=getattr(qc,tested_at_field);repair.status="Ready" if status in {"Passed","Waived"} else "In Repair" if status=="Failed" else repair.status
    db.session.commit();flash(f"{_stage_title(stage)} marked {status}","success");return redirect(url_for("qc.qc_detail",repair_id=repair.id,stage=stage))
