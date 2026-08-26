from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models import Part, Purchase, PurchaseItem, PurchaseReturn, Supplier, SupplierPayment, User


def _login(client,user_id):
    with client.session_transaction() as session:
        session["user_id"]=user_id


def test_optimized_supplier_ledger_totals_and_pagination(app,client):
    with app.app_context():
        user=User(email="perf-admin@example.com",role="admin");user.set_password("PerformanceAdmin123!");db.session.add(user)
        part=Part(sku="PERF-001",name="Performance Part",quantity=Decimal("10"),cost_price=Decimal("100"),selling_price=Decimal("200"));db.session.add(part);db.session.flush()
        suppliers=[]
        for i in range(21):
            supplier=Supplier(name=f"Supplier {i:02d}");db.session.add(supplier);db.session.flush();suppliers.append(supplier)
        purchase=Purchase(purchase_number="PUR-PERF-001",supplier_id=suppliers[0].id,purchase_date=date(2026,8,27),status="Active",created_by=user.id);db.session.add(purchase);db.session.flush()
        item=PurchaseItem(purchase_id=purchase.id,part_id=part.id,quantity=Decimal("5"),unit_cost=Decimal("100"));db.session.add(item);db.session.flush()
        db.session.add(PurchaseReturn(return_number="RET-PERF-001",purchase_id=purchase.id,purchase_item_id=item.id,quantity=Decimal("1"),unit_cost=Decimal("100"),reason="Test",created_by=user.id))
        db.session.add(SupplierPayment(supplier_id=suppliers[0].id,amount=Decimal("150"),payment_date=date(2026,8,27),method="Cash",created_by=user.id));db.session.commit();user_id=user.id
    _login(client,user_id)
    first=client.get("/operations/suppliers");assert first.status_code==200;html=first.get_data(as_text=True);assert html.count("Outstanding ₹") == 20;assert "Outstanding ₹250.00" in html
    second=client.get("/operations/suppliers?page=2");assert second.status_code==200;assert second.get_data(as_text=True).count("Outstanding ₹") == 1
