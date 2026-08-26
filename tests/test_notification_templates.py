from app.models.customer import Customer
from app.models.notification_setting import NotificationSetting
from app.models.notification_template import NotificationTemplate
from app.models.repair import RepairOrder
from app.services import sms


def test_notification_template_overrides_default(app, monkeypatch):
    with app.app_context():
        customer = Customer(name="Template Customer", phone="9999999999")
        repair = RepairOrder(
            job_number="JOB-TEMPLATE-0001",
            customer=customer,
            device="iPhone 15",
            issue_description="Display issue",
            status="Received",
        )
        setting = NotificationSetting(
            channel="sms",
            enabled=True,
            provider="smsalert.in",
            api_key="test-key",
            sender_id="FIXZON",
        )
        template = NotificationTemplate(
            channel="sms",
            event="received",
            enabled=True,
            body="FixZone update: {job_number} for {device}",
        )
        from app.extensions import db
        db.session.add_all([customer, repair, setting, template])
        db.session.commit()

        sent = {}

        def fake_send(mobile, text, **kwargs):
            sent["mobile"] = mobile
            sent["text"] = text
            return {"ok": True}

        monkeypatch.setattr(sms, "send_sms", fake_send)
        result = sms.notify_customer("received", repair)

        assert result["ok"] is True
        assert sent["mobile"] == "9999999999"
        assert sent["text"] == "FixZone update: JOB-TEMPLATE-0001 for iPhone 15"


def test_disabled_notification_template_skips_send(app, monkeypatch):
    with app.app_context():
        customer = Customer(name="Disabled Customer", phone="9999999999")
        repair = RepairOrder(
            job_number="JOB-TEMPLATE-0002",
            customer=customer,
            device="iPhone 14",
            issue_description="Battery issue",
            status="Ready",
        )
        setting = NotificationSetting(
            channel="sms",
            enabled=True,
            provider="smsalert.in",
            api_key="test-key",
            sender_id="FIXZON",
        )
        template = NotificationTemplate(
            channel="sms",
            event="repair_ready",
            enabled=False,
            body="Should not send",
        )
        from app.extensions import db
        db.session.add_all([customer, repair, setting, template])
        db.session.commit()

        monkeypatch.setattr(sms, "send_sms", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("send_sms should not be called")))
        result = sms.notify_customer("repair_ready", repair)

        assert result["skipped"] is True
