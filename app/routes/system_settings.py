from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import QCChecklistItem, SystemSetting
from app.security import permission_required

settings_bp = Blueprint("system_settings", __name__, url_prefix="/system-settings")

SETTING_KEYS = (
    "business_name",
    "business_tagline",
    "business_phone",
    "business_email",
    "business_address",
    "business_gstin",
    "invoice_terms",
    "default_warranty_days",
    "invoice_prefix",
    "job_prefix",
)


def setting_value(key, default=""):
    row = SystemSetting.query.filter_by(key=key).first()
    return row.value if row and row.value is not None else default


def all_settings():
    return {key: setting_value(key) for key in SETTING_KEYS}


@settings_bp.route("/", methods=["GET", "POST"])
@permission_required("system_settings")
def index():
    if request.method == "POST":
        for key in SETTING_KEYS:
            value = request.form.get(key, "").strip()
            row = SystemSetting.query.filter_by(key=key).first()
            if row is None:
                row = SystemSetting(key=key)
                db.session.add(row)
            row.value = value
        db.session.commit()
        flash("System settings saved", "success")
        return redirect(url_for("system_settings.index"))
    items = QCChecklistItem.query.order_by(QCChecklistItem.sort_order.asc(), QCChecklistItem.id.asc()).all()
    return render_template("system_settings/index.html", settings=all_settings(), qc_items=items)


@settings_bp.route("/qc/add", methods=["POST"])
@permission_required("system_settings")
def add_qc_item():
    label = request.form.get("label", "").strip()
    stage = request.form.get("stage", "both")
    if stage not in {"before", "after", "both"}:
        stage = "both"
    if not label:
        flash("QC checklist label is required", "error")
        return redirect(url_for("system_settings.index") + "#qc")
    max_order = db.session.query(db.func.max(QCChecklistItem.sort_order)).scalar() or 0
    db.session.add(QCChecklistItem(label=label, stage=stage, sort_order=max_order + 10, active=True))
    db.session.commit()
    flash("QC checklist item added", "success")
    return redirect(url_for("system_settings.index") + "#qc")


@settings_bp.route("/qc/<int:item_id>/edit", methods=["POST"])
@permission_required("system_settings")
def edit_qc_item(item_id):
    item = db.session.get(QCChecklistItem, item_id)
    if item is None:
        return ("Not Found", 404)
    label = request.form.get("label", "").strip()
    stage = request.form.get("stage", "both")
    if not label or stage not in {"before", "after", "both"}:
        flash("Enter a valid QC label and stage", "error")
        return redirect(url_for("system_settings.index") + "#qc")
    item.label = label
    item.stage = stage
    item.sort_order = request.form.get("sort_order", item.sort_order, type=int)
    db.session.commit()
    flash("QC checklist item updated", "success")
    return redirect(url_for("system_settings.index") + "#qc")


@settings_bp.route("/qc/<int:item_id>/toggle", methods=["POST"])
@permission_required("system_settings")
def toggle_qc_item(item_id):
    item = db.session.get(QCChecklistItem, item_id)
    if item is None:
        return ("Not Found", 404)
    item.active = not item.active
    db.session.commit()
    flash("QC checklist status updated", "success")
    return redirect(url_for("system_settings.index") + "#qc")


@settings_bp.route("/qc/<int:item_id>/delete", methods=["POST"])
@permission_required("system_settings")
def delete_qc_item(item_id):
    item = db.session.get(QCChecklistItem, item_id)
    if item is None:
        return ("Not Found", 404)
    db.session.delete(item)
    db.session.commit()
    flash("QC checklist item deleted. Historical completed QC records remain unchanged.", "success")
    return redirect(url_for("system_settings.index") + "#qc")
