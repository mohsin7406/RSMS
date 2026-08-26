import re
from decimal import Decimal
from datetime import date

from app.extensions import db
from app.models import (
    Customer, Expense, Part, PartUsage, Purchase, PurchaseItem, RepairOrder,
    StockAllocation, StockMovement, Supplier, SupplierPayment, User,
)


def _csrf(client, path):
    response = client.get(path)
    text = response.get_data(as_text=True)
    match = re.search(r'(?:name="csrf_token" value|meta name="csrf-token" content)="([^"]+)"', text)
    assert match, f"CSRF token not found on {path}; status={response.status_code}"
    return match.group(1)


def _admin_session(app, client):
    with app.app_context():
        admin = User(email="consolidation-admin@example.com", role="admin")
        admin.set_password("Consolidation123!")
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id
    with client.session_transaction() as session:
        session["user_id"] = admin_id
    return admin_id


def test_reserved_stock_used_becomes_job_material_and_stock_movement(app, client):
    admin_id = _admin_session(app, client)
    with app.app_context():
        technician = User(email="consolidation-tech@example.com", role="technician")
        technician.set_password("Tech123456!")
        customer = Customer(name="Stock Customer", phone="9999999999")
        part = Part(sku="CONS-OLED", name="OLED", quantity=Decimal("5"), reorder_level=Decimal("1"), cost_price=Decimal("2000"), selling_price=Decimal("3500"), active=True)
        db.session.add_all([technician, customer, part])
        db.session.flush()
        repair = RepairOrder(job_number="JOB-CONS-STOCK", customer_id=customer.id, assigned_technician_id=technician.id, device="iPhone", issue_description="Display", service_type="Doorstep", status="Approved")
        db.session.add(repair)
        db.session.commit()
        repair_id, part_id, tech_id = repair.id, part.id, technician.id

    token = _csrf(client, "/operations/stock")
    response = client.post("/operations/stock", data={"csrf_token": token, "part_id": part_id, "repair_id": repair_id, "technician_id": tech_id, "quantity": "1"}, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        allocation = StockAllocation.query.filter_by(repair_id=repair_id).one()
        allocation_id = allocation.id
        assert db.session.get(Part, part_id).quantity == Decimal("5")

    response = client.post(f"/operations/stock/{allocation_id}/Used", data={"csrf_token": _csrf(client, "/operations/stock")}, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        assert db.session.get(Part, part_id).quantity == Decimal("4")
        usage = PartUsage.query.filter_by(repair_id=repair_id, part_id=part_id).one()
        assert usage.net_cost_total == Decimal("2000")
        movement = StockMovement.query.filter_by(part_id=part_id, reference="JOB-CONS-STOCK", movement_type="OUT").one()
        assert movement.quantity == Decimal("1")
        assert db.session.get(StockAllocation, allocation_id).status == "Used"


def test_supplier_payment_cannot_exceed_net_outstanding(app, client):
    _admin_session(app, client)
    with app.app_context():
        supplier = Supplier(name="Ledger Supplier", active=True)
        part = Part(sku="CONS-BAT", name="Battery", quantity=Decimal("2"), cost_price=Decimal("500"), selling_price=Decimal("900"), active=True)
        db.session.add_all([supplier, part])
        db.session.flush()
        purchase = Purchase(purchase_number="PUR-CONS-001", supplier_id=supplier.id, purchase_date=date.today(), status="Active")
        db.session.add(purchase)
        db.session.flush()
        db.session.add(PurchaseItem(purchase_id=purchase.id, part_id=part.id, quantity=Decimal("2"), unit_cost=Decimal("500")))
        db.session.commit()
        supplier_id = supplier.id

    response = client.post(f"/operations/suppliers/{supplier_id}/payment", data={"csrf_token": _csrf(client, "/operations/suppliers"), "amount": "1200", "method": "UPI"}, follow_redirects=False)
    assert response.status_code == 302
    with app.app_context():
        assert SupplierPayment.query.filter_by(supplier_id=supplier_id).count() == 0

    response = client.post(f"/operations/suppliers/{supplier_id}/payment", data={"csrf_token": _csrf(client, "/operations/suppliers"), "amount": "1000", "method": "UPI"}, follow_redirects=False)
    assert response.status_code == 302
    with app.app_context():
        assert SupplierPayment.query.filter_by(supplier_id=supplier_id).one().amount == Decimal("1000")


def test_purchase_void_reverses_remaining_stock_and_job_expenses_reduce_profit(app, client):
    _admin_session(app, client)
    with app.app_context():
        supplier = Supplier(name="Void Supplier", active=True)
        customer = Customer(name="Profit Customer", phone="8888888888")
        part = Part(sku="CONS-VOID", name="Camera", quantity=Decimal("3"), cost_price=Decimal("1000"), selling_price=Decimal("1800"), active=True)
        db.session.add_all([supplier, customer, part])
        db.session.flush()
        purchase = Purchase(purchase_number="PUR-CONS-VOID", supplier_id=supplier.id, purchase_date=date.today(), status="Active")
        repair = RepairOrder(job_number="JOB-CONS-PROFIT", customer_id=customer.id, device="iPhone", issue_description="Camera", status="Ready", final_amount=Decimal("5000"))
        db.session.add_all([purchase, repair])
        db.session.flush()
        db.session.add(PurchaseItem(purchase_id=purchase.id, part_id=part.id, quantity=Decimal("3"), unit_cost=Decimal("1000")))
        db.session.add(Expense(expense_date=date.today(), category="Travel", amount=Decimal("500"), repair_id=repair.id, description="Doorstep travel"))
        db.session.commit()
        purchase_id, part_id = purchase.id, part.id

    response = client.post(f"/purchases/{purchase_id}/void", data={"csrf_token": _csrf(client, f"/purchases/{purchase_id}"), "reason": "Wrong supplier bill"}, follow_redirects=False)
    assert response.status_code == 302
    with app.app_context():
        purchase = db.session.get(Purchase, purchase_id)
        assert purchase.status == "Voided"
        assert db.session.get(Part, part_id).quantity == Decimal("0")
        assert StockMovement.query.filter_by(part_id=part_id, movement_type="PURCHASE_VOID").one().quantity == Decimal("3")

    response = client.get("/reports/profitability")
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "Job Expenses" in text
    assert "₹500.00" in text
