import secrets
from functools import wraps
from hmac import compare_digest

from flask import abort, current_app, g, redirect, render_template, request, session, url_for

from app.extensions import db
from app.models import User
from app.roles import has_permission, role_allowed

CSRF_SESSION_KEY = "_csrf_token"

def get_csrf_token() -> str:
    token=session.get(CSRF_SESSION_KEY)
    if not token:
        token=secrets.token_urlsafe(32); session[CSRF_SESSION_KEY]=token
    return token

def validate_csrf() -> None:
    if request.method not in {"POST","PUT","PATCH","DELETE"}: return
    if request.endpoint in {"lead_webhook.elementor"}: return
    supplied=request.form.get("csrf_token") or request.headers.get("X-CSRFToken"); expected=session.get(CSRF_SESSION_KEY)
    if not supplied or not expected or not compare_digest(supplied,expected): abort(400,description="Invalid or missing CSRF token.")

def load_current_user() -> None:
    user_id=session.get("user_id"); g.current_user=db.session.get(User,user_id) if user_id else None
    if user_id and g.current_user is None: session.clear()
def current_user_id(): return g.current_user.id if g.current_user else None

def login_required(view):
    @wraps(view)
    def wrapped(*args,**kwargs):
        if g.current_user is None:return redirect(url_for("auth.login",next=request.full_path))
        return view(*args,**kwargs)
    return wrapped

def role_required(*roles):
    allowed=set(roles)
    def decorator(view):
        @wraps(view)
        def wrapped(*args,**kwargs):
            if g.current_user is None:return redirect(url_for("auth.login",next=request.full_path))
            if not role_allowed(g.current_user.role,allowed):abort(403)
            return view(*args,**kwargs)
        return wrapped
    return decorator

def permission_required(permission):
    def decorator(view):
        @wraps(view)
        def wrapped(*args,**kwargs):
            if g.current_user is None:return redirect(url_for("auth.login",next=request.full_path))
            if not has_permission(g.current_user.role,permission):abort(403)
            return view(*args,**kwargs)
        return wrapped
    return decorator

def register_security(app):
    @app.before_request
    def _security_before_request():
        load_current_user()
        try:
            from app.services.settings import get_bool
            maintenance=get_bool("maintenance_mode",False)
        except Exception:
            maintenance=False
        if maintenance and not (g.current_user and g.current_user.role=="admin") and request.endpoint!="lead_webhook.elementor":
            return render_template("errors/503.html"),503
        validate_csrf()
    @app.context_processor
    def _security_context(): return {"csrf_token":get_csrf_token,"current_user":g.current_user,"has_permission":lambda permission:bool(g.current_user and has_permission(g.current_user.role,permission))}
    @app.after_request
    def _security_headers(response):
        response.headers.setdefault("X-Content-Type-Options","nosniff"); response.headers.setdefault("X-Frame-Options","SAMEORIGIN"); response.headers.setdefault("Referrer-Policy","strict-origin-when-cross-origin"); response.headers.setdefault("Permissions-Policy","camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy","same-origin")
        if not response.headers.get("Content-Security-Policy"):
            response.headers["Content-Security-Policy"]="default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; font-src 'self' data:; connect-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'"
        if current_app.config.get("SESSION_COOKIE_SECURE"): response.headers.setdefault("Strict-Transport-Security","max-age=31536000; includeSubDomains")
        if request.endpoint and request.endpoint.startswith(("auth.","users.","billing.","system_settings.","system_update.")): response.headers.setdefault("Cache-Control","no-store")
        return response
    @app.errorhandler(400)
    def bad_request(error): return render_template("errors/400.html",error=error),400
    @app.errorhandler(403)
    def forbidden(error): return render_template("errors/403.html",error=error),403
    @app.errorhandler(404)
    def not_found(error): return render_template("errors/404.html",error=error),404
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback(); app.logger.exception("Unhandled application error"); return render_template("errors/500.html"),500
