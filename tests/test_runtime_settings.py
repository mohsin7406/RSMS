from app.extensions import db
from app.models import Invoice, RepairOrder, SettingOption, SystemSetting
from app.services.settings import format_number, get_bool, get_options, get_setting
from datetime import datetime, timezone


def test_runtime_settings_defaults_and_overrides(app):
    with app.app_context():
        assert "UPI" in get_options("payment_methods")
        assert "In-Shop" in get_options("service_types")
        db.session.add(SystemSetting(key="job_prefix", value="FZJOB"))
        db.session.add(SystemSetting(key="allow_negative_stock", value="1"))
        db.session.commit()
        assert get_setting("job_prefix") == "FZJOB"
        assert get_bool("allow_negative_stock") is True


def test_setting_options_replace_defaults_when_configured(app):
    with app.app_context():
        db.session.add(SettingOption(group="payment_methods", value="QR Pay", label="QR Pay", sort_order=10, active=True))
        db.session.commit()
        assert get_options("payment_methods") == ["QR Pay"]
