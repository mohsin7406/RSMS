from flask import abort, g, request

from app.roles import has_permission
from app.routes.repair_order import repair_bp


@repair_bp.before_request
def enforce_repair_permissions():
    if g.current_user is None:
        return None

    permission = (
        "repairs_view"
        if request.method in {"GET", "HEAD", "OPTIONS"}
        else "repairs_manage"
    )
    if not has_permission(g.current_user.role, permission):
        abort(403)

    return None
