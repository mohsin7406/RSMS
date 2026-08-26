import re
from decimal import Decimal

from app.extensions import db
from app.models import Customer, RepairOrder, RepairQC, User


def _csrf_token(client, path):
    response = client.get(path)
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match, f"CSRF token not found on {path}; status={response.status_code}"
    return match.group(1)


def _login(client):
    token = _csrf_token(client, "/auth/login")
    return client.post(
        "/auth/login",
        data={
            "csrf_token": token,
            "email": "admin@example.com",
            "password": "AdminPassword123!",
        },
        follow_redirects=False,
    )


def test_billing_payment_delivery_and_warranty_gate(app, client):
    with app.app_context():
        admin = User(email="admin@example.com", role="admin")
        admin.set_password("AdminPassword123!")
        customer = Customer(name="Billing Customer", phone="8888888888")
        repair = RepairOrder(
            job_number="JOB-TEST-BILL-0001",
            customer=customer,
            device="iPhone 15 Pro",
            issue_description="Screen replacement",
            status="Ready",
            final_amount=Decimal("1000.00"),
            amount_paid=Decimal("0.00"),
            payment_status="Unpaid",
            warranty_days=30,
        )
        db.session.add_all([admin, customer, repair])
        db.session.flush()
        qc = RepairQC(
            repair_id=repair.id,
            before_status="Passed",
            after_status="Passed",
            before_checklist={"Power / boot": "pass"},
            after_checklist={"Power / boot": "pass"},
            before_tested_by_id=admin.id,
            after_tested_by_id=admin.id,
        )
        db.session.add(qc)
        db.session.commit()
        repair_id = repair.id

    login = _login(client)
    assert login.status_code == 302

    token = _csrf_token(client, f"/repairs/view/{repair_id}")
    response = client.post(
        f"/billing/repair/{repair_id}/invoice",
        data={"csrf_token": token, "discount": "0", "tax": "0"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        repair = db.session.get(RepairOrder, repair_id)
        invoice = repair.invoice
        assert invoice.total == Decimal("1000.00")
        invoice_id = invoice.id

    token = _csrf_token(client, f"/billing/invoice/{invoice_id}")
    response = client.post(
        f"/billing/invoice/{invoice_id}/payment",
        data={
            "csrf_token": token,
            "payment_type": "Payment",
            "payment_method": "UPI",
            "amount": "400",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        repair = db.session.get(RepairOrder, repair_id)
        invoice = db.session.get(type(repair.invoice), invoice_id)
        assert repair.payment_status == "Partially Paid"
        assert invoice.status == "Partially Paid"

    token = _csrf_token(client, f"/billing/invoice/{invoice_id}")
    response = client.post(
        f"/billing/invoice/{invoice_id}/payment",
        data={
            "csrf_token": token,
            "payment_type": "Payment",
            "payment_method": "UPI",
            "amount": "600",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        repair = db.session.get(RepairOrder, repair_id)
        assert repair.payment_status == "Paid"
        assert repair.amount_paid == Decimal("1000.00")

    token = _csrf_token(client, f"/repairs/view/{repair_id}")
    response = client.post(
        f"/repairs/update_status/{repair_id}",
        data={"csrf_token": token, "status": "Delivered"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        repair = db.session.get(RepairOrder, repair_id)
        assert repair.status == "Delivered"
        assert repair.delivered_at is not None

    token = _csrf_token(client, f"/warranty/repair/{repair_id}")
    response = client.post(
        f"/warranty/repair/{repair_id}/claim",
        data={"csrf_token": token, "issue": "Display flickering after repair"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        repair = db.session.get(RepairOrder, repair_id)
        assert len(repair.warranty_claims) == 1
        assert repair.warranty_claims[0].status == "Open"
