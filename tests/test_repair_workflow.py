import re

from app.extensions import db
from app.models import Customer, RepairOrder, RepairQC, User


def _csrf_token(client, path="/auth/login"):
    response = client.get(path)
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match, f"CSRF token not found on {path}; status={response.status_code}"
    return match.group(1)


def _login(client, token, email="admin@example.com", password="AdminPassword123!"):
    return client.post(
        "/auth/login",
        data={
            "csrf_token": token,
            "email": email,
            "password": password,
        },
        follow_redirects=False,
    )


def test_repair_assignment_persists_and_qc_can_make_repair_ready(app, client):
    with app.app_context():
        admin = User(email="admin@example.com", role="admin")
        admin.set_password("AdminPassword123!")
        technician = User(email="tech@example.com", role="technician")
        technician.set_password("TechnicianPassword123!")
        customer = Customer(name="Test Customer", phone="9999999999")
        db.session.add_all([admin, technician, customer])
        db.session.commit()
        customer_id = customer.id
        technician_id = technician.id

    login = _login(client, _csrf_token(client))
    assert login.status_code == 302

    token = _csrf_token(client, "/dashboard")
    response = client.post(
        "/repairs/add",
        data={
            "csrf_token": token,
            "customer_id": customer_id,
            "device": "iPhone 15 Pro",
            "issue_description": "Broken screen",
            "status": "Pending",
            "priority": "Normal",
            "service_type": "In-Shop",
            "estimated_amount": "1000",
            "final_amount": "1000",
            "amount_paid": "0",
            "payment_status": "Unpaid",
            "assigned_technician_id": technician_id,
            "warranty_days": "0",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        repair = RepairOrder.query.one()
        assert repair.assigned_technician_id == technician_id
        repair_id = repair.id

    checklist = {f"check_{idx}": "pass" for idx in range(10)}
    checklist.update({
        "csrf_token": _csrf_token(client, f"/qc/repair/{repair_id}"),
        "status": "Passed",
        "notes": "All tests passed",
    })
    response = client.post(f"/qc/repair/{repair_id}", data=checklist, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        repair = db.session.get(RepairOrder, repair_id)
        qc = RepairQC.query.filter_by(repair_id=repair_id).one()
        assert repair.status == "Ready"
        assert qc.status == "Passed"
        assert all(value == "pass" for value in qc.checklist.values())
