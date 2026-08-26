import json
import os
import shlex
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import SystemSetting, SystemUpdate
from app.security import role_required
from app.services.system_updater import UpdateError, app_root, current_version, inspect_package, install_package

system_update_bp=Blueprint("system_update",__name__,url_prefix="/system-update")

def _set_maintenance(enabled):
    row=SystemSetting.query.filter_by(key="maintenance_mode").first()
    if row is None: row=SystemSetting(key="maintenance_mode"); db.session.add(row)
    row.value="1" if enabled else "0"; db.session.commit()

def _restart_later(command):
    def run():
        try: subprocess.Popen(shlex.split(command),cwd=str(app_root()),start_new_session=True)
        except Exception: pass
    threading.Timer(1.0,run).start()

@system_update_bp.route("/")
@role_required("admin")
def index():
    rows=SystemUpdate.query.order_by(SystemUpdate.uploaded_at.desc()).limit(30).all()
    return render_template("system_update/index.html",updates=rows,current_version=current_version(),restart_command_configured=bool(os.environ.get("RSMS_RESTART_COMMAND")))

@system_update_bp.route("/upload",methods=["POST"])
@role_required("admin")
def upload():
    file=request.files.get("package")
    if not file or not file.filename or not file.filename.lower().endswith(".zip"):
        flash("Select an RSMS .zip update package.","error"); return redirect(url_for("system_update.index"))
    filename=secure_filename(file.filename) or "rsms-update.zip"; packages=app_root()/"backups"/"system-updates"/"packages"; packages.mkdir(parents=True,exist_ok=True); path=packages/f"{uuid.uuid4().hex}-{filename}"; file.save(path)
    try:
        manifest,package_sha=inspect_package(path)
    except Exception as exc:
        path.unlink(missing_ok=True); flash(f"Update rejected: {exc}","error"); return redirect(url_for("system_update.index"))
    row=SystemUpdate(version=str(manifest["version"]),previous_version=current_version(),filename=filename,package_path=str(path),package_sha256=package_sha,status="Validated",changelog=str(manifest.get("changelog","") or ""),details=json.dumps({"minimum_version":manifest.get("minimum_version"),"files":len(manifest.get("files",{})),"delete":len(manifest.get("delete",[]))}),uploaded_by_id=g.current_user.id if g.current_user else None)
    db.session.add(row); db.session.commit(); flash(f"Update {row.version} validated. Review it, then click Install Update.","success"); return redirect(url_for("system_update.index"))

@system_update_bp.route("/<int:update_id>/install",methods=["POST"])
@role_required("admin")
def install(update_id):
    row=db.session.get(SystemUpdate,update_id)
    if row is None: return ("Not Found",404)
    if row.status not in {"Validated","Failed"}: flash("This package is not available for installation.","error"); return redirect(url_for("system_update.index"))
    package=Path(row.package_path)
    if not package.exists(): flash("Uploaded update package is missing from the server.","error"); return redirect(url_for("system_update.index"))
    try:
        manifest,package_sha=inspect_package(package)
        if package_sha!=row.package_sha256 or str(manifest["version"])!=row.version: raise UpdateError("Uploaded package no longer matches the validated package.")
        row.status="Installing"; row.details="Validated again; entering maintenance mode."; db.session.commit(); _set_maintenance(True)
        backup=install_package(package,manifest)
        row=db.session.get(SystemUpdate,update_id); row.status="Installed - Restart Required"; row.backup_path=backup; row.installed_at=datetime.now(timezone.utc); row.details="Files installed, database migrations completed, and health check passed. Restart Gunicorn to load the new code."; db.session.commit()
        flash(f"RSMS {row.version} installed successfully. Restart the application service to activate all workers.","success")
    except Exception as exc:
        db.session.rollback(); row=db.session.get(SystemUpdate,update_id)
        if row: row.status="Failed"; row.details=str(exc)[-8000:]; db.session.commit()
        flash(f"Update failed: {exc}","error")
    finally:
        try: _set_maintenance(False)
        except Exception: db.session.rollback()
    return redirect(url_for("system_update.index"))

@system_update_bp.route("/restart",methods=["POST"])
@role_required("admin")
def restart_service():
    command=os.environ.get("RSMS_RESTART_COMMAND","").strip()
    if not command:
        flash("Automatic restart is not configured. Restart the Gunicorn/systemd service from the server.","error"); return redirect(url_for("system_update.index"))
    _restart_later(command); flash("Application restart requested. Refresh this page in a few seconds.","success"); return redirect(url_for("system_update.index"))

@system_update_bp.route("/<int:update_id>/delete",methods=["POST"])
@role_required("admin")
def delete_package(update_id):
    row=db.session.get(SystemUpdate,update_id)
    if row is None:return ("Not Found",404)
    if row.status.startswith("Installed"): flash("Installed update history cannot be deleted.","error"); return redirect(url_for("system_update.index"))
    try: Path(row.package_path).unlink(missing_ok=True)
    except OSError: pass
    db.session.delete(row); db.session.commit(); flash("Update package removed.","success"); return redirect(url_for("system_update.index"))
