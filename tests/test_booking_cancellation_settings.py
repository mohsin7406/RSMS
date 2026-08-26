import re
from datetime import datetime

from app.extensions import db
from app.models import Booking, Customer, User


def _csrf(client):
    response = client.get("/bookings/")
    match = re.search(r'<meta name="csrf-token" content="([^"]+)"', response.get_data(as_text=True))
    assert match
    return match.group(1)


def test_booking_cancel_requires_configured_reason(app, client):
    with app.app_context():
        user = User(email="booking-cancel@example.com", role="reception")
        user.set_password("BookingCancelPassword123!")
        customer = Customer(name="Cancel Customer", phone="9999999999")
        db.session.add_all([user, customer])
        db.session.flush()
        booking = Booking(
            booking_number="BOOK-CANCEL-0001",
            customer_id=customer.id,
            service_type="Doorstep",
            scheduled_at=datetime(2026, 8, 27, 11, 30),
            status="Scheduled",
        )
        db.session.add(booking)
        db.session.commit()
        user_id = user.id
        booking_id = booking.id

    with client.session_transaction() as session:
        session["user_id"] = user_id

    response = client.post(
        f"/bookings/{booking_id}/status",
        data={"csrf_token": _csrf(client), "status": "Cancelled", "cancellation_reason": ""},
        follow_redirects=False,
    )
    assert response.status_code == 302
    with app.app_context():
        booking = db.session.get(Booking, booking_id)
        assert booking.status == "Scheduled"
        assert booking.cancellation_reason is None

    response = client.post(
        f"/bookings/{booking_id}/status",
        data={"csrf_token": _csrf(client), "status": "Cancelled", "cancellation_reason": "Customer Cancelled"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    with app.app_context():
        booking = db.session.get(Booking, booking_id)
        assert booking.status == "Cancelled"
        assert booking.cancellation_reason == "Customer Cancelled"
