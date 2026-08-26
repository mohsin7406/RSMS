import re

from app.extensions import db
from app.models import Booking, Customer, Lead, LeadContact, User


def _csrf(client, path="/leads/"):
    response = client.get(path)
    text = response.get_data(as_text=True)
    match = re.search(r'<meta name="csrf-token" content="([^"]+)"', text)
    assert match, f"CSRF token not found on {path}; status={response.status_code}"
    return match.group(1)


def test_lead_keeps_multiple_contacts_and_confirmation_creates_booking(app, client):
    with app.app_context():
        user = User(email="reception@example.com", role="reception")
        user.set_password("ReceptionPassword123!")
        lead = Lead(
            name="Lead Customer",
            phone="9999999999",
            email="lead@example.com",
            device="iPhone 15 Pro",
            issue="Display issue",
            area="Madhapur",
            service_type="Doorstep",
            status="New",
        )
        db.session.add_all([user, lead])
        db.session.commit()
        user_id = user.id
        lead_id = lead.id

    with client.session_transaction() as session:
        session["user_id"] = user_id

    token = _csrf(client)
    first = client.post(
        f"/leads/{lead_id}/contact",
        data={"csrf_token": token, "method": "Call", "outcome": "No Answer", "notes": "No response"},
        follow_redirects=False,
    )
    assert first.status_code == 302

    token = _csrf(client, f"/leads/{lead_id}")
    second = client.post(
        f"/leads/{lead_id}/contact",
        data={"csrf_token": token, "method": "WhatsApp", "outcome": "Follow Up", "notes": "Asked to call later"},
        follow_redirects=False,
    )
    assert second.status_code == 302

    with app.app_context():
        lead = db.session.get(Lead, lead_id)
        assert lead.status == "Follow Up"
        assert LeadContact.query.filter_by(lead_id=lead_id).count() == 2

    token = _csrf(client, f"/leads/{lead_id}")
    confirmed = client.post(
        f"/leads/{lead_id}/confirm",
        data={"csrf_token": token, "scheduled_at": "2026-08-27T11:30"},
        follow_redirects=False,
    )
    assert confirmed.status_code == 302

    with app.app_context():
        lead = db.session.get(Lead, lead_id)
        assert lead.status == "Booked"
        assert lead.booking_id is not None
        assert lead.customer_id is not None
        assert Booking.query.count() == 1
        assert Customer.query.filter_by(phone="9999999999").count() == 1
        assert LeadContact.query.filter_by(lead_id=lead_id).count() == 3
        assert lead.booking.status == "Confirmed"
