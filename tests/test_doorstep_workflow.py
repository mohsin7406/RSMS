import re
from datetime import datetime
from decimal import Decimal

from app.extensions import db
from app.models import Booking, Customer, Invoice, Payment, RepairExtraCharge, RepairOrder, RepairQC, User


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
        technician_id = technician.id
        booking_id = booking.id

    with client.session_transaction() as session:
        session["user_id"] = admin_id

    response = client.post(
        f"/bookings/{booking_id}/status",
        data={"csrf_token": _csrf(client, "/bookings/"), "status": "Confirmed"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        booking = db.session.get(Booking, booking_id)
        repair = db.session.get(RepairOrder, booking.repair_id)
        assert repair is not None
        assert repair.service_type == "Doorstep"
        assert repair.assigned_technician_id == technician_id
        assert repair.status == "Approved"
        # Admin enters only the estimate. Final is intentionally left blank/zero.
        repair.estimated_amount = Decimal("1500.00")
        repair.final_amount = Decimal("0.00")
        db.session.commit()
        repair_id = repair.id

    response = client.post(f"/qc/repair/{repair_id}", data=_checklist(client, repair_id, "before"), follow_redirects=False)
    assert response.status_code == 302
    response = client.post(f"/qc/repair/{repair_id}", data=_checklist(client, repair_id, "after"), follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        repair = db.session.get(RepairOrder, repair_id)
        qc = RepairQC.query.filter_by(repair_id=repair_id).one()
        assert qc.before_status == "Passed"
        assert qc.after_status == "Passed"
        assert repair.status == "Completed"

    # Technician can add an audited extra charge; estimate becomes the base automatically.
    with client.session_transaction() as session:
        session["user_id"] = technician_id
    response = client.post(
        f"/billing/repair/{repair_id}/extra-charge",
        data={
            "csrf_token": _csrf(client, f"/repairs/view/{repair_id}"),
            "amount": "800",
            "description": "Charging flex and additional labour",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        repair = db.session.get(RepairOrder, repair_id)
        charge = RepairExtraCharge.query.filter_by(repair_id=repair_id).one()
        assert repair.estimated_amount == Decimal("1500.00")
        assert repair.final_amount == Decimal("2300.00")
        assert charge.amount == Decimal("800.00")
        assert charge.description == "Charging flex and additional labour"
        assert charge.added_by_id == technician_id

    response = client.post(
        f"/billing/repair/{repair_id}/doorstep-payment",
        data={
            "csrf_token": _csrf(client, f"/repairs/view/{repair_id}"),
            "amount": "2300",
            "payment_method": "UPI",
            "reference": "UPI-TEST-001",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        repair = db.session.get(RepairOrder, repair_id)
        payment = Payment.query.filter_by(repair_id=repair_id).one()
        assert repair.payment_status == "Paid"
        assert repair.amount_paid == Decimal("2300.00")
        assert Invoice.query.filter_by(repair_id=repair_id).count() == 0
        assert payment.invoice_id is None
        assert payment.amount == Decimal("2300.00")
        assert payment.payment_method == "UPI"

    with client.session_transaction() as session:
        session["user_id"] = admin_id
    response = client.post(
        f"/billing/repair/{repair_id}/invoice",
        data={"csrf_token": _csrf(client, f"/repairs/view/{repair_id}"), "discount": "0", "tax": "0"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        invoice = Invoice.query.filter_by(repair_id=repair_id).one()
        payment = Payment.query.filter_by(repair_id=repair_id).one()
        assert invoice.status == "Paid"
        assert invoice.total == Decimal("2300.00")
        assert payment.invoice_id == invoice.id
