from app.extensions import db
from app.models import Lead, SystemSetting, WebhookLog


def _setting(key,value):
    db.session.add(SystemSetting(key=key,value=value))


def test_elementor_webhook_captures_before_otp_then_updates_verified(app,client):
    with app.app_context():
        _setting("lead_webhook_enabled","1")
        _setting("lead_webhook_secret","test-webhook-secret")
        _setting("lead_webhook_pending_status","pending_otp")
        _setting("lead_webhook_verified_status","verified")
        _setting("lead_webhook_duplicate_window_minutes","120")
        _setting("lead_webhook_default_source","Website")
        _setting("lead_webhook_default_service_type","Doorstep")
        db.session.commit()
    payload={"name":"test1","contact_number":"7892713637","device":"iPhone","issue":"Front Glass Broken","status":"pending_otp","source_url":"https://ifixer.in/rpr-landing/"}
    first=client.post("/api/webhooks/leads/elementor",data=payload,headers={"X-RSMS-Webhook-Token":"test-webhook-secret"})
    assert first.status_code==200
    assert first.get_json()["result"]=="created"
    payload["status"]="verified"
    second=client.post("/api/webhooks/leads/elementor",data=payload,headers={"X-RSMS-Webhook-Token":"test-webhook-secret"})
    assert second.status_code==200
    assert second.get_json()["result"]=="updated"
    assert second.get_json()["verified"] is True
    with app.app_context():
        assert Lead.query.count()==1
        lead=Lead.query.one()
        assert lead.phone=="7892713637"
        assert lead.otp_status=="verified"
        assert lead.otp_verified_at is not None
        assert lead.source_url=="https://ifixer.in/rpr-landing/"
        assert WebhookLog.query.count()==2


def test_elementor_webhook_rejects_bad_secret(app,client):
    with app.app_context():
        _setting("lead_webhook_enabled","1")
        _setting("lead_webhook_secret","correct-secret")
        db.session.commit()
    response=client.post("/api/webhooks/leads/elementor",data={"name":"Bad","contact_number":"7892713637","status":"pending_otp"},headers={"X-RSMS-Webhook-Token":"wrong-secret"})
    assert response.status_code==401
    with app.app_context():
        assert Lead.query.count()==0
        assert WebhookLog.query.filter_by(result="unauthorized").count()==1
