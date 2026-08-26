from app.services import smsalert


def test_smsalert_builds_expected_request(monkeypatch):
    captured = {}

    class FakeResponse:
        status = 200

        def read(self):
            return b'{"status":"success"}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.method
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(smsalert, "urlopen", fake_urlopen)
    result = smsalert.send_sms(
        api_key="secret-key",
        sender="FIXZON",
        mobile="9876543210",
        text="Repair ready",
    )

    assert result.status_code == 200
    assert "apikey=secret-key" in captured["url"]
    assert "sender=FIXZON" in captured["url"]
    assert "mobileno=9876543210" in captured["url"]
    assert "text=Repair+ready" in captured["url"]
    assert captured["method"] == "POST"


def test_smsalert_rejects_missing_credentials():
    try:
        smsalert.send_sms(api_key="", sender="FIXZON", mobile="9876543210", text="Test")
    except smsalert.SMSAlertError as exc:
        assert "API key" in str(exc)
    else:
        raise AssertionError("Expected SMSAlertError")
