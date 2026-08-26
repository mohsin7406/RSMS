import re
from decimal import Decimal

from app.extensions import db
from app.models import Customer, JobPurchase, Part, PartUsage, RepairOrder, StockMovement, User


def _csrf(client, path):
    response = client.get(path)
    text = response.get_data(as_text=True)
    match = re.search(r'(?:name="csrf_token" value|meta name="csrf-token" content)="([^"]+)"', text)
    assert match, f"CSRF token not found on {path}; status={response.status_code}"
    return match.group(1)


def test_technician_can_use_inventory_or_record_job_purchase(app, client):
    with app.app_context():
        technician = User(email="materials-tech@example.com", role="technician")
        technician.set_password("MaterialsTech123!")
        customer = Customer(name="Materials Customer", phone="9999999999")
        part = Part(
            sku="OLED-15-TEST",
            name="iPhone 15 OLED",
            quantity=Decimal("3.00"),
            reorder_level=Decimal("1.00"),
            cost_price=Decimal("3000.00"),
            selling_price=Decimal("5000.00"),
            active=True,
        )
        db.session.add_all([technician, customer, part])
        db.session.flush()
        repair = RepairOrder(
            job_number="JOB-MATERIALS-0001",
            customer_id=customer.id,
            assigned_technician_id=technician.id,
            device="iPhone 15",
            issue_description="Display replacement",
            service_type="Doorstep",
            status="Approved",
            estimated_amount=Decimal("7000.00"),
        )
        db.session.add(repair)
        db.session.commit()
        technician_id = technician.id
        repair_id = repair.id
        part_id = part.id

    with client.session_transaction() as session:
        session["user_id"] = technician_id

    materials_url = f"/materials/repair/{repair_id}"
    response = client.post(
        f"/materials/repair/{repair_id}/inventory",
        data={
            "csrf_token": _csrf(client, materials_url),
            "part_id": part_id,
            "quantity": "1",
            "unit_price": "5000",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        part = db.session.get(Part, part_id)
        usage = PartUsage.query.filter_by(repair_id=repair_id).one()
        movement = StockMovement.query.filter_by(part_id=part_id, reference="JOB-MATERIALS-0001").one()
        assert part.quantity == Decimal("2.00")
        assert usage.cost_total == Decimal("3000.00")
        assert usage.sale_total == Decimal("5000.00")
        assert movement.movement_type == "OUT"

    response = client.post(
        f"/materials/repair/{repair_id}/purchase",
        data={
            "csrf_token": _csrf(client, materials_url),
            "item_name": "Back glass",
            "quantity": "1",
            "unit_cost": "900",
            "unit_price": "1800",
            "supplier": "Local Supplier",
            "reference": "BILL-123",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        part = db.session.get(Part, part_id)
        purchase = JobPurchase.query.filter_by(repair_id=repair_id).one()
        repair = db.session.get(RepairOrder, repair_id)
        total_material_cost = sum((u.cost_total for u in repair.parts_used), Decimal("0")) + sum(
            (p.cost_total for p in repair.job_purchases), Decimal("0")
        )
        assert part.quantity == Decimal("2.00")
        assert purchase.item_name == "Back glass"
        assert purchase.cost_total == Decimal("900.00")
        assert purchase.sale_total == Decimal("1800.00")
        assert purchase.supplier == "Local Supplier"
        assert purchase.reference == "BILL-123"
        assert purchase.added_by_id == technician_id
        assert total_material_cost == Decimal("3900.00")
