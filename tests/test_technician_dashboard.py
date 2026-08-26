from app.extensions import db
from app.models import Customer, RepairOrder, RepairQC, User


def _set_user(client, user_id):
    with client.session_transaction() as session:
        session["user_id"] = user_id


def test_technician_dashboard_shows_only_assigned_work_and_qc_before_queue(app, client):
    with app.app_context():
        tech = User(email="tech-dashboard@example.com", role="technician")
        tech.set_password("TechnicianPassword123!")
        other = User(email="other-tech@example.com", role="technician")
        other.set_password("TechnicianPassword123!")
        customer = Customer(name="Dashboard Customer", phone="9999999999")
        db.session.add_all([tech, other, customer])
        db.session.flush()

        mine = RepairOrder(
            job_number="JOB-DASH-0001",
            customer_id=customer.id,
            assigned_technician_id=tech.id,
            device="iPhone 15 Pro",
            issue_description="Display issue",
            status="Approved",
        )
        theirs = RepairOrder(
            job_number="JOB-DASH-0002",
            customer_id=customer.id,
            assigned_technician_id=other.id,
            device="iPhone 14",
            issue_description="Battery issue",
            status="Approved",
        )
        db.session.add_all([mine, theirs])
        db.session.flush()
        db.session.add(RepairQC(repair_id=mine.id, before_status="Pending", after_status="Pending"))
        db.session.commit()
        tech_id = tech.id

    _set_user(client, tech_id)
    response = client.get("/technician/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "JOB-DASH-0001" in html
    assert "JOB-DASH-0002" not in html
    assert "QC Before Pending" in html
    assert "QC Before" in html
