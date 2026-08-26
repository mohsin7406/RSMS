from app.extensions import db
from app.models import Customer, Part, RepairOrder, User


def _login(client,user_id):
    with client.session_transaction() as session:
        session["user_id"]=user_id


def test_repair_current_history_and_inventory_are_paginated(app,client):
    with app.app_context():
        user=User(email="pagination-admin@example.com",role="admin");user.set_password("PaginationAdmin123!")
        customer=Customer(name="Pagination Customer",phone="9999999999")
        db.session.add_all([user,customer]);db.session.flush()
        for i in range(25):
            db.session.add(RepairOrder(job_number=f"JOB-PAGE-{i:04d}",customer_id=customer.id,device="iPhone",issue_description="Test",service_type="Doorstep",status="Pending"))
            db.session.add(Part(sku=f"SKU-PAGE-{i:04d}",name=f"Part Page {i:04d}",quantity=1,reorder_level=0,cost_price=1,selling_price=2))
        db.session.add(RepairOrder(job_number="JOB-HISTORY-PAGE",customer_id=customer.id,device="iPhone",issue_description="Done",service_type="Doorstep",status="Completed"))
        db.session.commit();user_id=user.id
    _login(client,user_id)
    current=client.get("/repairs/?view=current")
    assert current.status_code==200
    html=current.get_data(as_text=True)
    assert html.count("JOB-PAGE-")==20
    assert "JOB-HISTORY-PAGE" not in html
    page2=client.get("/repairs/?view=current&page=2")
    assert page2.status_code==200
    assert page2.get_data(as_text=True).count("JOB-PAGE-")==5
    history=client.get("/repairs/?view=history")
    assert history.status_code==200
    assert "JOB-HISTORY-PAGE" in history.get_data(as_text=True)
    inventory=client.get("/inventory/")
    assert inventory.status_code==200
    assert inventory.get_data(as_text=True).count("SKU-PAGE-")==20
    inventory2=client.get("/inventory/?page=2")
    assert inventory2.status_code==200
    assert inventory2.get_data(as_text=True).count("SKU-PAGE-")==5
