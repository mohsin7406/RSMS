from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import User
from app.security import role_required

users_bp = Blueprint("users", __name__, url_prefix="/users")


@users_bp.route("/")
@role_required("admin")
def list_users():
    users = User.query.order_by(User.role.asc(), User.email.asc()).all()
    return render_template("users/list.html", users=users)


@users_bp.route("/add", methods=["GET", "POST"])
@role_required("admin")
def add_user():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "staff")
        if not email or "@" not in email:
            flash("Enter a valid email address", "error")
            return render_template("users/form.html", action="Add")
        if len(password) < 12:
            flash("Password must be at least 12 characters", "error")
            return render_template("users/form.html", action="Add")
        if role not in {"admin", "staff", "technician", "customer"}:
            flash("Invalid role", "error")
            return render_template("users/form.html", action="Add")
        if User.query.filter_by(email=email).first():
            flash("Email already exists", "error")
            return render_template("users/form.html", action="Add")
        user = User(email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("User created successfully", "success")
        return redirect(url_for("users.list_users"))
    return render_template("users/form.html", action="Add")


@users_bp.route("/<int:user_id>/role", methods=["POST"])
@role_required("admin")
def update_role(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        from flask import abort
        abort(404)
    role = request.form.get("role", "")
    if role not in {"admin", "staff", "technician", "customer"}:
        flash("Invalid role", "error")
        return redirect(url_for("users.list_users"))
    user.role = role
    db.session.commit()
    flash(f"Role updated for {user.email}", "success")
    return redirect(url_for("users.list_users"))
