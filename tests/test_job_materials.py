import re
from decimal import Decimal

from app.extensions import db
from app.models import Customer, JobPurchase, JobPurchaseReturn, Part, PartUsage, RepairOrder, StockMovement, User


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
        data={"csrf_token": _csrf(client, materials_url), "part_id": part_id, "quantity": "1", "unit_price": "5000"},
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
        data={"csrf_token": _csrf(client, materials_url), "item_name": "Back glass", "quantity": "1", "unit_cost": "900", "unit_price": "1800", "supplier": "Local Supplier", "reference": "BILL-123"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        part = db.session.get(Part, part_id)
        purchase = JobPurchase.query.filter_by(repair_id=repair_id).one()
        repair = db.session.get(RepairOrder, repair_id)
        total_material_cost = sum((u.cost_total for u in repair.parts_used), Decimal("0")) + sum((p.net_cost_total for p in repair.job_purchases), Decimal("0"))
        assert part.quantity == Decimal("2.00")
        assert purchase.item_name == "Back glass"
        assert purchase.cost_total == Decimal("900.00")
        assert purchase.sale_total == Decimal("1800.00")
        assert purchase.supplier == "Local Supplier"
        assert purchase.reference == "BILL-123"
        assert purchase.added_by_id == technician_id
        assert total_material_cost == Decimal("3900.00")


def test_only_admin_or_manager_can_return_job_purchase_to_inventory(app, client):
    with app.app_context():
        admin = User(email="return-admin@example.com", role="admin")
        admin.set_password("ReturnAdmin123!")
        technician = User(email="return-tech@example.com", role="technician")
        technician.set_password("ReturnTech123!")
        customer = Customer(name="Return Customer", phone="8888888888")
        inventory_part = Part(sku="RET-TARGET", name="iPhone 14 Display", quantity=Decimal("0"), reorder_level=Decimal("0"), cost_price=Decimal("2000"), selling_price=Decimal("3500"), active=True)
        db.session.add_all([admin, technician, customer, inventory_part])
        db.session.flush()
        repair = RepairOrder(job_number="JOB-RETURN-0001", customer_id=customer.id, assigned_technician_id=technician.id, device="iPhone 14", issue_description="Display", service_type="Doorstep", status="Approved")
        db.session.add(repair)
        db.session.flush()
        purchase = JobPurchase(repair_id=repair.id, item_name="iPhone 14 Display", quantity=Decimal("1"), unit_cost=Decimal("2000"), unit_price=Decimal("3500"), supplier="Supplier A", added_by_id=technician.id)
        db.session.add(purchase)
        db.session.commit()
        admin_id, technician_id, repair_id, purchase_id, part_id = admin.id, technician.id, repair.id, purchase.id, inventory_part.id

    with client.session_transaction() as session:
        session["user_id"] = technician_id
    materials_url = f"/materials/repair/{repair_id}"
    response = client.post(
        f"/materials/purchase/{purchase_id}/return",
        data={"csrf_token": _csrf(client, materials_url), "quantity": "1", "destination": "Inventory", "inventory_part_id": part_id},
        follow_redirects=False,
    )
    assert response.status_code == 403

    with client.session_transaction() as session:
        session["user_id"] = admin_id
    response = client.post(
        f"/materials/purchase/{purchase_id}/return",
        data={"csrf_token": _csrf(client, materials_url), "quantity": "1", "destination": "Inventory", "inventory_part_id": part_id, "reason": "Unused after inspection"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        purchase = db.session.get(JobPurchase, purchase_id)
        inventory_part = db.session.get(Part, part_id)
        returned = JobPurchaseReturn.query.filter_by(purchase_id=purchase_id).one()
        movement = StockMovement.query.filter_by(part_id=part_id, reference="JOB-RETURN-0001", movement_type="IN").one()
        assert purchase.remaining_quantity == Decimal("0")
        assert purchase.net_cost_total == Decimal("0")
        assert inventory_part.quantity == Decimal("1")
        assert returned.destination == "Inventory"
        assert returned.reason == "Unused after inspection"
        assert movement.quantity == Decimal("1")

    report = client.get("/inventory/report")
    assert report.status_code == 200
    assert "Inventory Report" in report.get_data(as_text=True)
