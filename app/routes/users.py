from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import RolePermission, User
from app.roles import DEFAULT_ROLE_PERMISSIONS, PERMISSION_LABELS, PERMISSIONS, ROLE_LABELS, VALID_ROLES, permissions_for_role
from app.security import permission_required

users_bp = Blueprint("users", __name__, url_prefix="/users")


def _user_form_context(action):
    return {"action": action, "role_labels": ROLE_LABELS}


@users_bp.route("/")
@permission_required("users_admin")
def list_users():
    users = User.query.order_by(User.role.asc(), User.email.asc()).all()
    effective_permissions = {role: permissions_for_role(role) for role in ROLE_LABELS}
    return render_template(
        "users/list.html",
        users=users,
        role_labels=ROLE_LABELS,
        permission_labels=PERMISSION_LABELS,
        effective_permissions=effective_permissions,
    )


@users_bp.route("/permissions", methods=["POST"])
@permission_required("users_admin")
def update_permissions():
    role = request.form.get("role", "")
    if role not in VALID_ROLES or role == "admin":
        flash("Administrator permissions are fixed for safety", "error")
        return redirect(url_for("users.list_users"))

    selected = {permission for permission in PERMISSIONS if request.form.get(f"permission_{permission}") == "on"}
    existing = {row.permission: row for row in RolePermission.query.filter_by(role=role).all()}
    for permission in PERMISSIONS:
        row = existing.get(permission)
        if row is None:
            row = RolePermission(role=role, permission=permission)
            db.session.add(row)
        row.enabled = permission in selected
    db.session.commit()
    flash(f"Permissions updated for {ROLE_LABELS.get(role, role)}", "success")
    return redirect(url_for("users.list_users"))


@users_bp.route("/permissions/<role>/reset", methods=["POST"])
@permission_required("users_admin")
def reset_permissions(role):
    if role not in VALID_ROLES or role == "admin":
        flash("Administrator permissions cannot be reset", "error")
        return redirect(url_for("users.list_users"))
    RolePermission.query.filter_by(role=role).delete()
    db.session.commit()
    flash(f"{ROLE_LABELS.get(role, role)} permissions restored to defaults", "success")
    return redirect(url_for("users.list_users"))


@users_bp.route("/add", methods=["GET", "POST"])
@permission_required("users_admin")
def add_user():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "staff")
        if not email or "@" not in email:
            flash("Enter a valid email address", "error")
            return render_template("users/form.html", **_user_form_context("Add"))
        if len(password) < 12:
            flash("Password must be at least 12 characters", "error")
            return render_template("users/form.html", **_user_form_context("Add"))
        if role not in VALID_ROLES:
            flash("Invalid role", "error")
            return render_template("users/form.html", **_user_form_context("Add"))
        if User.query.filter_by(email=email).first():
            flash("Email already exists", "error")
            return render_template("users/form.html", **_user_form_context("Add"))
        user = User(email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("User created successfully", "success")
        return redirect(url_for("users.list_users"))
    return render_template("users/form.html", **_user_form_context("Add"))


@users_bp.route("/<int:user_id>/role", methods=["POST"])
@permission_required("users_admin")
def update_role(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        from flask import abort
        abort(404)
    role = request.form.get("role", "")
    if role not in VALID_ROLES:
        flash("Invalid role", "error")
        return redirect(url_for("users.list_users"))
    user.role = role
    db.session.commit()
    flash(f"Role updated for {user.email}", "success")
    return redirect(url_for("users.list_users"))
