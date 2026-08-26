import re
from decimal import Decimal

from app.extensions import db
from app.models import Customer, Part, PartUsage, PartUsageReturn, RepairOrder, StockMovement, User


def _csrf(client, path):
    response = client.get(path)
    match = re.search(r'(?:name="csrf_token" value|meta name="csrf-token" content)="([^"]+)"', response.get_data(as_text=True))
    assert match, f"CSRF token not found on {path}; status={response.status_code}"
    return match.group(1)


def test_inventory_part_return_is_admin_manager_only_and_restores_stock(app, client):
    with app.app_context():
        admin = User(email="return-admin@example.com", role="admin")
        admin.set_password("ReturnAdmin123!")
        technician = User(email="return-tech@example.com", role="technician")
        technician.set_password("ReturnTech123!")
        customer = Customer(name="Return Customer", phone="9999999999")
        part = Part(
            sku="RETURN-PART-1",
            name="Test Display",
            quantity=Decimal("1.00"),
            reorder_level=Decimal("0"),
            cost_price=Decimal("2000.00"),
            selling_price=Decimal("3500.00"),
            active=True,
        )
        db.session.add_all([admin, technician, customer, part])
        db.session.flush()
        repair = RepairOrder(
            job_number="JOB-RETURN-0001",
            customer_id=customer.id,
            assigned_technician_id=technician.id,
            device="iPhone 15",
            issue_description="Display",
            service_type="Doorstep",
            status="Approved",
        )
        db.session.add(repair)
        db.session.flush()
        usage = PartUsage(
            repair_id=repair.id,
            part_id=part.id,
            quantity=Decimal("1.00"),
            unit_cost=Decimal("2000.00"),
            unit_price=Decimal("3500.00"),
        )
        part.quantity -= Decimal("1.00")
        db.session.add(usage)
        db.session.commit()
        admin_id = admin.id
        technician_id = technician.id
        repair_id = repair.id
        usage_id = usage.id
        part_id = part.id

    materials_url = f"/materials/repair/{repair_id}"
    with client.session_transaction() as session:
        session["user_id"] = technician_id
    response = client.post(
        f"/materials/usage/{usage_id}/return",
        data={"csrf_token": _csrf(client, materials_url), "quantity": "1", "reason": "Unused"},
        follow_redirects=False,
    )
    assert response.status_code == 403

    with client.session_transaction() as session:
        session["user_id"] = admin_id
    response = client.post(
        f"/materials/usage/{usage_id}/return",
        data={"csrf_token": _csrf(client, materials_url), "quantity": "1", "reason": "Customer cancelled"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        part = db.session.get(Part, part_id)
        usage = db.session.get(PartUsage, usage_id)
        returned = PartUsageReturn.query.filter_by(usage_id=usage_id).one()
        movement = StockMovement.query.filter_by(part_id=part_id, reference="JOB-RETURN-0001", movement_type="IN").one()
        assert part.quantity == Decimal("1.00")
        assert usage.remaining_quantity == Decimal("0.00")
        assert usage.net_cost_total == Decimal("0.00")
        assert returned.quantity == Decimal("1.00")
        assert returned.processed_by_id == admin_id
        assert movement.quantity == Decimal("1.00")
