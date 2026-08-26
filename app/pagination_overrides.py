from datetime import date
from decimal import Decimal

from flask import flash, g, redirect, render_template, request, url_for
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import joinedload, selectinload

from app.models import (
    AuditEvent, Customer, Expense, Part, Purchase, PurchaseItem, PurchaseReturn,
    RepairOrder, StockAllocation, Supplier, SupplierPayment, User,
)
from app.security import permission_required

PER_PAGE = 20


def _history_condition():
    return or_(RepairOrder.status.in_(("Delivered", "Cancelled")), and_(RepairOrder.status == "Completed", RepairOrder.service_type == "Doorstep"))


def _is_history_repair(repair):
    return repair.status in {"Delivered", "Cancelled"} or (repair.status == "Completed" and repair.service_type == "Doorstep")


def _pager(pagination, endpoint, **params):
    base = {k: v for k, v in params.items() if v not in (None, "")}
    return {"page": pagination.page, "pages": pagination.pages, "total": pagination.total, "per_page": pagination.per_page, "has_prev": pagination.has_prev, "has_next": pagination.has_next, "prev_url": url_for(endpoint, page=pagination.prev_num, **base) if pagination.has_prev else None, "next_url": url_for(endpoint, page=pagination.next_num, **base) if pagination.has_next else None}


def _supplier_totals_for_ids(ids):
    if not ids:
        return {}
    purchase_totals = dict(
        db.session.query(Purchase.supplier_id, func.coalesce(func.sum(PurchaseItem.quantity * PurchaseItem.unit_cost), 0))
        .join(PurchaseItem, PurchaseItem.purchase_id == Purchase.id)
        .filter(Purchase.supplier_id.in_(ids), Purchase.status != "Voided")
        .group_by(Purchase.supplier_id).all()
    )
    return_totals = dict(
        db.session.query(Purchase.supplier_id, func.coalesce(func.sum(PurchaseReturn.quantity * PurchaseReturn.unit_cost), 0))
        .join(PurchaseReturn, PurchaseReturn.purchase_id == Purchase.id)
        .filter(Purchase.supplier_id.in_(ids), Purchase.status != "Voided")
        .group_by(Purchase.supplier_id).all()
    )
    paid_totals = dict(
        db.session.query(SupplierPayment.supplier_id, func.coalesce(func.sum(SupplierPayment.amount), 0))
        .filter(SupplierPayment.supplier_id.in_(ids)).group_by(SupplierPayment.supplier_id).all()
    )
    result = {}
    for supplier_id in ids:
        purchases = Decimal(purchase_totals.get(supplier_id, 0) or 0)
        returns = Decimal(return_totals.get(supplier_id, 0) or 0)
        paid = Decimal(paid_totals.get(supplier_id, 0) or 0)
        result[supplier_id] = (purchases, returns, paid, max(purchases - returns - paid, Decimal("0")))
    return result


def register_pagination_overrides(app):
    originals = {name: app.view_functions.get(name) for name in ("ops.expenses", "ops.stock", "repair.edit_repair")}

    @permission_required("repairs_view")
    def repairs_list_paginated():
        page=max(request.args.get("page",1,type=int),1);view=request.args.get("view","current");q=request.args.get("q","").strip();status=request.args.get("status","").strip()
        query=RepairOrder.query.options(joinedload(RepairOrder.customer),joinedload(RepairOrder.assigned_technician)).filter(RepairOrder.deleted_at.is_(None)).join(Customer)
        if g.current_user and g.current_user.role=="technician":query=query.filter(RepairOrder.assigned_technician_id==g.current_user.id)
        history_filter=_history_condition()
        if view=="history":query=query.filter(history_filter)
        else:view="current";query=query.filter(~history_filter)
        if q:
            term=f"%{q}%";query=query.filter(or_(Customer.name.ilike(term),RepairOrder.job_number.ilike(term),RepairOrder.device.ilike(term),RepairOrder.imei.ilike(term)))
        if status:query=query.filter(RepairOrder.status==status)
        pagination=query.order_by(RepairOrder.created_at.desc(),RepairOrder.id.desc()).paginate(page=page,per_page=PER_PAGE,error_out=False)
        return render_template("repairs/list.html",repairs=pagination.items,pagination=pagination,pager=_pager(pagination,"repair.list_repairs",view=view,q=q,status=status),repair_view=view)

    def repair_edit_guard(id):
        repair=RepairOrder.query.filter(RepairOrder.id==id,RepairOrder.deleted_at.is_(None)).first()
        if repair and _is_history_repair(repair):
            flash("Repair history is read-only. Open the job to view invoice, payment or warranty information.","error");return redirect(url_for("repair.view_repair",id=id))
        return originals["repair.edit_repair"](id)

    @permission_required("inventory")
    def inventory_list_paginated():
        page=max(request.args.get("page",1,type=int),1);search=request.args.get("q","").strip();stock=request.args.get("stock","").strip();query=Part.query.filter_by(active=True)
        if search:
            term=f"%{search}%";query=query.filter(or_(Part.sku.ilike(term),Part.name.ilike(term),Part.brand.ilike(term),Part.model.ilike(term),Part.category.ilike(term),Part.supplier.ilike(term)))
        if stock=="low":query=query.filter(Part.quantity<=Part.reorder_level)
        elif stock=="out":query=query.filter(Part.quantity<=0)
        pagination=query.order_by(Part.name,Part.id).paginate(page=page,per_page=PER_PAGE,error_out=False);low_stock_count=Part.query.filter(Part.active.is_(True),Part.quantity<=Part.reorder_level).count()
        return render_template("inventory/list.html",parts=pagination.items,pagination=pagination,pager=_pager(pagination,"inventory.list_parts",q=search,stock=stock),low_stock_count=low_stock_count,search=search,stock_filter=stock)

    @permission_required("purchases")
    def purchases_paginated():
        page=max(request.args.get("page",1,type=int),1)
        query=Purchase.query.options(joinedload(Purchase.supplier),selectinload(Purchase.items),selectinload(Purchase.returns))
        pagination=query.order_by(Purchase.purchase_date.desc(),Purchase.id.desc()).paginate(page=page,per_page=PER_PAGE,error_out=False)
        return render_template("purchases/list.html",purchases=pagination.items,pagination=pagination,pager=_pager(pagination,"purchases.index"))

    @permission_required("purchases")
    def suppliers_paginated():
        page=max(request.args.get("page",1,type=int),1)
        pagination=Supplier.query.options(selectinload(Supplier.payments)).order_by(Supplier.name,Supplier.id).paginate(page=page,per_page=PER_PAGE,error_out=False)
        totals=_supplier_totals_for_ids([s.id for s in pagination.items]);rows=[(s,*totals[s.id]) for s in pagination.items]
        return render_template("operations/suppliers.html",rows=rows,pagination=pagination,pager=_pager(pagination,"ops.suppliers"))

    @permission_required("expenses")
    def expenses_paginated():
        if request.method=="POST":return originals["ops.expenses"]()
        page=max(request.args.get("page",1,type=int),1)
        pagination=Expense.query.options(joinedload(Expense.repair)).order_by(Expense.expense_date.desc(),Expense.id.desc()).paginate(page=page,per_page=PER_PAGE,error_out=False)
        repairs=RepairOrder.query.with_entities(RepairOrder.id,RepairOrder.job_number).filter(RepairOrder.deleted_at.is_(None),~_history_condition()).order_by(RepairOrder.id.desc()).limit(50).all()
        return render_template("operations/expenses.html",rows=pagination.items,pagination=pagination,pager=_pager(pagination,"ops.expenses"),repairs=repairs,today=date.today().isoformat())

    @permission_required("inventory")
    def stock_paginated():
        if request.method=="POST":return originals["ops.stock"]()
        page=max(request.args.get("page",1,type=int),1)
        pagination=StockAllocation.query.options(joinedload(StockAllocation.part),joinedload(StockAllocation.repair),joinedload(StockAllocation.technician)).order_by(StockAllocation.id.desc()).paginate(page=page,per_page=PER_PAGE,error_out=False)
        parts=Part.query.with_entities(Part.id,Part.sku,Part.name,Part.quantity).filter_by(active=True).order_by(Part.name).all()
        repairs=RepairOrder.query.with_entities(RepairOrder.id,RepairOrder.job_number,RepairOrder.device).filter(RepairOrder.deleted_at.is_(None),~_history_condition()).order_by(RepairOrder.id.desc()).limit(50).all()
        techs=User.query.with_entities(User.id,User.email).filter_by(role="technician").order_by(User.email).all()
        return render_template("operations/stock.html",rows=pagination.items,pagination=pagination,pager=_pager(pagination,"ops.stock"),parts=parts,repairs=repairs,techs=techs)

    @permission_required("audit")
    def audit_paginated():
        page=max(request.args.get("page",1,type=int),1)
        pagination=AuditEvent.query.options(joinedload(AuditEvent.user)).order_by(AuditEvent.id.desc()).paginate(page=page,per_page=PER_PAGE,error_out=False)
        return render_template("operations/audit.html",rows=pagination.items,pagination=pagination,pager=_pager(pagination,"ops.audit_log"))

    app.view_functions["repair.list_repairs"]=repairs_list_paginated
    app.view_functions["repair.edit_repair"]=repair_edit_guard
    app.view_functions["inventory.list_parts"]=inventory_list_paginated
    app.view_functions["purchases.index"]=purchases_paginated
    app.view_functions["ops.suppliers"]=suppliers_paginated
    app.view_functions["ops.expenses"]=expenses_paginated
    app.view_functions["ops.stock"]=stock_paginated
    app.view_functions["ops.audit_log"]=audit_paginated


from app.extensions import db
