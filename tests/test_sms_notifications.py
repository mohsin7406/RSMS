from decimal import Decimal

from app.extensions import db
from app.models import Customer, RepairOrder, User
from app.models.notification_setting import NotificationSetting


def test_sms_notification_hook_on_repair_status(app, monkeypatch):
    sent = []

    def fake_notify(event, repair, **values):
        sent.append((event, repair.job_number, values))
        return {"ok": True}

    monkeypatch.setattr("app.services.notification_hooks.notify_customer", fake_notify)

    with app.app_context():
        customer = Customer(name="SMS Customer", phone="9999999999")
        repair = RepairOrder(
            job_number="JOB-SMS-0001",
            customer=customer,
            device="iPhone 15 Pro",
            issue_description="Screen repair",
            status="Received",
            final_amount=Decimal("1000.00"),
            amount_paid=Decimal("0.00"),
            payment_status="Unpaid",
            warranty_days=0,
        )
        db.session.add_all([customer, repair])
        db.session.commit()

        repair.status = "Ready"
        db.session.commit()

    assert sent == [("repair_ready", "JOB-SMS-0001", {})]


def test_sms_provider_configuration_is_required_for_send(app):
    with app.app_context():
        setting = NotificationSetting(channel="sms", enabled=False, provider="SMSAlert.in")
        db.session.add(setting)
        db.session.commit()

        from app.services.sms import send_sms

        result = send_sms("9999999999", "Test")

        assert result["ok"] is False
        assert result["skipped"] is True
