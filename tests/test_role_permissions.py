from app.extensions import db
from app.models import User


def _set_user(client, user_id):
    with client.session_transaction() as session:
        session["user_id"] = user_id


def test_reception_can_view_repairs_but_not_billing(app, client):
    with app.app_context():
        user = User(email="reception@example.com", role="reception")
        user.set_password("ReceptionPassword123!")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    _set_user(client, user_id)
    assert client.get("/repairs/").status_code == 200
    assert client.get("/billing/invoice/999999").status_code == 403


def test_accounts_can_use_billing_but_not_qc(app, client):
    with app.app_context():
        user = User(email="accounts@example.com", role="accounts")
        user.set_password("AccountsPassword123!")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    _set_user(client, user_id)
    assert client.get("/billing/invoice/999999").status_code == 404
    assert client.get("/qc/repair/999999").status_code == 403


def test_technician_can_access_repairs_and_qc_gate(app, client):
    with app.app_context():
        user = User(email="technician-role@example.com", role="technician")
        user.set_password("TechnicianPassword123!")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    _set_user(client, user_id)
    assert client.get("/repairs/").status_code == 200
    # Permission passes; missing repair is the expected application-level result.
    assert client.get("/qc/repair/999999").status_code == 404
