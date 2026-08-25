from urllib.parse import urlparse

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from app.extensions import db, limiter
from app.models import User
from app.security import login_required, role_required


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _safe_next_url(value):
    if not value:
        return url_for("main.dashboard")
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return url_for("main.dashboard")
    return value


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if g.current_user is not None:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            session.clear()
            session["user_id"] = user.id
            session.permanent = True
            return redirect(_safe_next_url(request.args.get("next")))

        flash("Invalid email or password", "error")

    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
@role_required("admin")
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "staff")
        allowed_roles = {"staff", "technician", "customer"}

        if not email or "@" not in email:
            flash("Enter a valid email address", "error")
            return render_template("register.html")
        if len(password) < 12:
            flash("Password must be at least 12 characters", "error")
            return render_template("register.html")
        if role not in allowed_roles:
            flash("Invalid role", "error")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("Email already exists", "error")
            return render_template("register.html")

        user = User(email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("User created successfully", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("register.html")


@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    if request.method == "GET":
        return render_template("logout_confirm.html")
    session.clear()
    return redirect(url_for("main.home"))
