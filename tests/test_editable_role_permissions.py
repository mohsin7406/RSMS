from app.extensions import db
from app.models import RolePermission, User
from app.roles import PERMISSIONS, has_permission


def _set_user(client, user_id):
    with client.session_transaction() as session:
        session["user_id"] = user_id


def test_database_permission_override_changes_effective_role_access(app, client):
    with app.app_context():
        admin = User(email="permission-admin@example.com", role="admin")
        admin.set_password("PermissionAdmin123!")
        tech = User(email="permission-tech@example.com", role="technician")
        tech.set_password("PermissionTech123!")
        db.session.add_all([admin, tech])
        db.session.flush()

        # Saving a matrix creates one row for every permission, including disabled
        # rows, so an empty/partial selection does not fall back to defaults.
        for permission in PERMISSIONS:
            db.session.add(RolePermission(role="technician", permission=permission, enabled=permission in {"repairs_view", "billing"}))
        db.session.commit()
        tech_id = tech.id

        assert has_permission("technician", "billing") is True
        assert has_permission("technician", "qc") is False

    _set_user(client, tech_id)
    # Permission gate allows billing; missing invoice produces app-level 404.
    assert client.get("/billing/invoice/999999").status_code == 404
    # QC is denied by the saved matrix.
    assert client.get("/qc/repair/999999").status_code == 403
