from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Lead, User
from app.models.lead import LEAD_STATUSES
from app.security import permission_required

leads_bp = Blueprint("leads", __name__, url_prefix="/leads")


@leads_bp.route("/")
@permission_required("leads")
def list_leads():
    leads = Lead.query.order_by(Lead.created_at.desc()).all()
    return render_template("leads/list.html", leads=leads, statuses=LEAD_STATUSES)


@leads_bp.route("/add", methods=["GET", "POST"])
@permission_required("leads")
def add_lead():
    staff = User.query.filter(User.role.in_(["admin", "manager", "staff", "reception"])).order_by(User.email.asc()).all()
    if request.method == "POST":
        status = request.form.get("status", "New")
        if status not in LEAD_STATUSES:
            flash("Invalid lead status", "error")
            return render_template("leads/form.html", staff=staff, statuses=LEAD_STATUSES)
        lead = Lead(
            name=request.form.get("name", "").strip(),
            phone=request.form.get("phone", "").strip(),
            email=request.form.get("email", "").strip() or None,
            device=request.form.get("device", "").strip() or None,
            issue=request.form.get("issue", "").strip() or None,
            source=request.form.get("source", "").strip() or None,
            area=request.form.get("area", "").strip() or None,
            service_type=request.form.get("service_type", "Doorstep"),
            status=status,
            assigned_to_id=request.form.get("assigned_to_id", type=int),
            notes=request.form.get("notes", "").strip() or None,
        )
        if not lead.name or not lead.phone:
            flash("Name and phone are required", "error")
            return render_template("leads/form.html", staff=staff, statuses=LEAD_STATUSES)
        db.session.add(lead)
        db.session.commit()
        flash("Lead created", "success")
        return redirect(url_for("leads.list_leads"))
    return render_template("leads/form.html", staff=staff, statuses=LEAD_STATUSES)


@leads_bp.route("/<int:id>/status", methods=["POST"])
@permission_required("leads")
def update_status(id):
    lead = Lead.query.get_or_404(id)
    status = request.form.get("status", "")
    if status not in LEAD_STATUSES:
        flash("Invalid lead status", "error")
        return redirect(url_for("leads.list_leads"))
    lead.status = status
    db.session.commit()
    flash("Lead status updated", "success")
    return redirect(url_for("leads.list_leads"))


@leads_bp.route("/<int:id>/assign", methods=["POST"])
@permission_required("leads")
def assign_lead(id):
    lead = Lead.query.get_or_404(id)
    lead.assigned_to_id = request.form.get("assigned_to_id", type=int)
    db.session.commit()
    flash("Lead assigned", "success")
    return redirect(url_for("leads.list_leads"))
