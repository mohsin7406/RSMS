import re
from datetime import datetime
from decimal import Decimal

from app.extensions import db
from app.models import Booking, Customer, Invoice, Payment, RepairOrder, RepairQC, User


def _csrf(client, path):
    response = client.get(path)
    text = response.get_data(as_text=True)
    match = re.search(r'(?:name="csrf_token" value|meta name="csrf-token" content)="([^"]+)"', text)
    assert match, f"CSRF token not found on {path}; status={response.status_code}"
    return match.group(1)


def _checklist(client, repair_id, stage):
    return {
        "csrf_token": _csrf(client, f"/qc/repair/{repair_id}?stage={stage}"),
        "stage": stage,
        "status": "Passed",
        "notes": f"Doorstep {stage} QC passed",
        **{f"check_{idx}": "pass" for idx in range(10)},
    }


def test_doorstep_booking_confirmation_starts_approved_and_qc_after_completes_job(app, client):
    with app.app_context():
        admin = User(email="doorstep-admin@example.com", role="admin")
        admin.set_password("DoorstepAdmin123!")
        technician = User(email="doorstep-tech@example.com", role="technician")
        technician.set_password("DoorstepTech123!")
        customer = Customer(name="Doorstep Customer", phone="9999999999")
        db.session.add_all([admin, technician, customer])
        db.session.flush()
        booking = Booking(
            booking_number="BOOK-DOORSTEP-0001",
            customer_id=customer.id,
            technician_id=technician.id,
            service_type="Doorstep",
            scheduled_at=datetime(2026, 8, 27, 11, 30),
            status="Scheduled",
            notes="iPhone 15 Pro | Display issue",
        )
        db.session.add(booking)
        db.session.commit()
        admin_id = admin.id
        booking_id = booking.id

    with client.session_transaction() as session:
        session["user_id"] = admin_id

    token = _csrf(client, "/bookings/")
    response = client.post(
        f"/bookings/{booking_id}/status",
        data={"csrf_token": token, "status": "Confirmed"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        booking = db.session.get(Booking, booking_id)
        repair = db.session.get(RepairOrder, booking.repair_id)
        assert repair is not None
        assert repair.service_type == "Doorstep"
        assert repair.assigned_technician_id is not None
        assert repair.status == "Approved"
        repair.final_amount = Decimal("1500.00")
        db.session.commit()
        repair_id = repair.id

    response = client.post(
        f"/qc/repair/{repair_id}",
        data=_checklist(client, repair_id, "before"),
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        repair = db.session.get(RepairOrder, repair_id)
        qc = RepairQC.query.filter_by(repair_id=repair_id).one()
        assert qc.before_status == "Passed"
        assert repair.status == "Approved"

    response = client.post(
        f"/qc/repair/{repair_id}",
        data=_checklist(client, repair_id, "after"),
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        repair = db.session.get(RepairOrder, repair_id)
        qc = RepairQC.query.filter_by(repair_id=repair_id).one()
        assert qc.after_status == "Passed"
        assert repair.status == "Completed"

    response = client.post(
        f"/billing/repair/{repair_id}/doorstep-payment",
        data={
            "csrf_token": _csrf(client, f"/repairs/view/{repair_id}"),
            "amount": "1500",
            "payment_method": "UPI",
            "reference": "UPI-TEST-001",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        repair = db.session.get(RepairOrder, repair_id)
        invoice = Invoice.query.filter_by(repair_id=repair_id).one()
        payment = Payment.query.filter_by(repair_id=repair_id).one()
        assert repair.payment_status == "Paid"
        assert repair.amount_paid == Decimal("1500.00")
        assert invoice.status == "Paid"
        assert invoice.total == Decimal("1500.00")
        assert payment.amount == Decimal("1500.00")
        assert payment.payment_method == "UPI"
