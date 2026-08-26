import re

from app.extensions import db
from app.models import Customer, QCChecklistItem, RepairOrder, User


def _csrf(client, path):
    response = client.get(path)
    match = re.search(r'(?:name="csrf_token" value|meta name="csrf-token" content)="([^"]+)"', response.get_data(as_text=True))
    assert match
    return match.group(1)


def test_custom_qc_item_is_stage_specific_and_admin_can_manage_it(app, client):
    with app.app_context():
        admin = User(email="settings-admin@example.com", role="admin")
        admin.set_password("SettingsAdmin123!")
        tech = User(email="settings-tech@example.com", role="technician")
        tech.set_password("SettingsTech123!")
        customer = Customer(name="Settings Customer", phone="9999999999")
        db.session.add_all([admin, tech, customer])
        db.session.flush()
        repair = RepairOrder(job_number="JOB-SETTINGS-QC-1", customer_id=customer.id, assigned_technician_id=tech.id, device="iPhone 15 Pro", issue_description="Test", service_type="Doorstep", status="Approved")
        db.session.add(repair)
        db.session.commit()
        admin_id, repair_id = admin.id, repair.id

    with client.session_transaction() as session:
        session["user_id"] = admin_id

    token = _csrf(client, "/system-settings/")
    response = client.post("/system-settings/qc/add", data={"csrf_token": token, "label": "Battery health custom", "stage": "after"}, follow_redirects=False)
    assert response.status_code == 302

    before = client.get(f"/qc/repair/{repair_id}?stage=before").get_data(as_text=True)
    after = client.get(f"/qc/repair/{repair_id}?stage=after").get_data(as_text=True)
    assert "Battery health custom" not in before
    assert "Battery health custom" in after

    with app.app_context():
        item = QCChecklistItem.query.filter_by(label="Battery health custom").one()
        item_id = item.id

    token = _csrf(client, "/system-settings/")
    response = client.post(f"/system-settings/qc/{item_id}/delete", data={"csrf_token": token}, follow_redirects=False)
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(QCChecklistItem, item_id) is None
