from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for, g
from flask import abort

from app.extensions import db
from app.models import Invoice, Payment, RepairExtraCharge, RepairOrder
from app.models.payment import PAYMENT_METHODS, PAYMENT_TYPES
from app.security import permission_required, role_required

billing_bp = Blueprint("billing", __name__, url_prefix="/billing")


def _money(value):
    try:
        amount = Decimal(value or "0")
        return amount if amount >= 0 else Decimal("0")
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _number(prefix, model, field):
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    latest = model.query.filter(getattr(model, field).like(f"{prefix}-{today}-%")).order_by(model.id.desc()).first()
    sequence = int(getattr(latest, field).rsplit("-", 1)[-1]) + 1 if latest else 1
    return f"{prefix}-{today}-{sequence:04d}"


def _totals(invoice):
    paid = sum((p.amount for p in invoice.payments if p.payment_type == "Payment"), Decimal("0"))
    refunded = sum((p.amount for p in invoice.payments if p.payment_type == "Refund"), Decimal("0"))
    net_paid = max(paid - refunded, Decimal("0"))
    balance = max(invoice.total - net_paid, Decimal("0"))
    return paid, refunded, net_paid, balance


def _extra_total(repair_id):
    return sum((charge.amount for charge in RepairExtraCharge.query.filter_by(repair_id=repair_id).all()), Decimal("0"))


def _sync_doorstep_final_amount(repair):
    extras_total = _extra_total(repair.id)
    current_total = _money(repair.final_amount)
    estimate = _money(repair.estimated_amount)
    explicit_base = current_total - extras_total if current_total > extras_total else Decimal("0")
    base = explicit_base if explicit_base > 0 else estimate
    repair.final_amount = base + extras_total
    return _money(repair.final_amount)


def _create_invoice_for_repair(repair, discount=Decimal("0"), tax=Decimal("0")):
    if repair.invoice:
        return repair.invoice
    if repair.service_type == "Doorstep":
        _sync_doorstep_final_amount(repair)
    subtotal = _money(repair.final_amount)
    discount = min(_money(discount), subtotal)
    tax = _money(tax)
    total = subtotal - discount + tax
    invoice = Invoice(invoice_number=_number("INV", Invoice, "invoice_number"), repair_id=repair.id, customer_id=repair.customer_id, subtotal=subtotal, discount=discount, tax=tax, total=total, status="Issued", issued_at=datetime.now(timezone.utc), due_at=datetime.now(timezone.utc))
    db.session.add(invoice); db.session.flush()
    unlinked = Payment.query.filter_by(repair_id=repair.id, invoice_id=None).all()
    for payment in unlinked: payment.invoice_id = invoice.id
    net_paid = max(sum((p.amount for p in unlinked if p.payment_type == "Payment"), Decimal("0")) - sum((p.amount for p in unlinked if p.payment_type == "Refund"), Decimal("0")), Decimal("0"))
    outstanding = max(total - net_paid, Decimal("0"))
    invoice.status = "Paid" if outstanding == 0 and total > 0 else "Partially Paid" if net_paid > 0 else "Issued"
    repair.final_amount = total; repair.amount_paid = net_paid; repair.payment_status = "Paid" if outstanding == 0 and total > 0 else "Partially Paid" if net_paid > 0 else "Unpaid"
    return invoice


@billing_bp.route("/repair/<int:repair_id>/invoice", methods=["POST"])
@permission_required("billing")
def create_invoice(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id).with_for_update().first_or_404()
    if repair.invoice: return redirect(url_for("billing.view_invoice", invoice_id=repair.invoice.id))
    invoice = _create_invoice_for_repair(repair, discount=_money(request.form.get("discount")), tax=_money(request.form.get("tax")))
    db.session.commit(); flash(f"Invoice {invoice.invoice_number} created", "success")
    return redirect(url_for("billing.view_invoice", invoice_id=invoice.id))


@billing_bp.route("/invoice/<int:invoice_id>/edit", methods=["GET", "POST"])
@permission_required("billing")
def edit_invoice(invoice_id):
    invoice = Invoice.query.filter_by(id=invoice_id).with_for_update().first_or_404()
    repair = invoice.repair
    if request.method == "POST":
        repair.device = request.form.get("device", "").strip() or repair.device
        model = request.form.get("model", "").strip()
        repair.model = model if model and model.casefold() != repair.device.casefold() else None
        repair.imei = request.form.get("imei", "").strip() or None
        repair.serial_number = request.form.get("serial_number", "").strip() or None
        repair.issue_description = request.form.get("issue_description", "").strip() or repair.issue_description
        repair.diagnosis = request.form.get("diagnosis", "").strip() or None
        repair.repair_notes = request.form.get("repair_notes", "").strip() or None
        repair.warranty_days = max(request.form.get("warranty_days", 0, type=int), 0)
        subtotal = _money(request.form.get("subtotal")); discount = min(_money(request.form.get("discount")), subtotal); tax = _money(request.form.get("tax")); total = subtotal - discount + tax
        _, _, net_paid, _ = _totals(invoice)
        if total < net_paid:
            flash("Invoice total cannot be lower than the amount already paid.", "error")
            return render_template("billing/edit_invoice.html", invoice=invoice)
        invoice.subtotal = subtotal; invoice.discount = discount; invoice.tax = tax; invoice.total = total
        repair.final_amount = total; repair.amount_paid = net_paid
        invoice.status = "Paid" if total > 0 and net_paid == total else "Partially Paid" if net_paid > 0 else "Issued"
        repair.payment_status = "Paid" if total > 0 and net_paid == total else "Partially Paid" if net_paid > 0 else "Unpaid"
        db.session.commit(); flash("Invoice updated", "success")
        return redirect(url_for("billing.view_invoice", invoice_id=invoice.id))
    return render_template("billing/edit_invoice.html", invoice=invoice)


@billing_bp.route("/repair/<int:repair_id>/extra-charge", methods=["POST"])
@role_required("admin", "manager", "staff", "technician")
def add_extra_charge(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id).with_for_update().first_or_404()
    if g.current_user and g.current_user.role == "technician" and repair.assigned_technician_id != g.current_user.id: return ("Forbidden", 403)
    if repair.service_type != "Doorstep": flash("This action is only for Doorstep jobs", "error"); return redirect(url_for("repair.view_repair", id=repair.id))
    if repair.invoice: flash("Invoice already exists. Edit the invoice instead.", "error"); return redirect(url_for("repair.view_repair", id=repair.id))
    amount = _money(request.form.get("amount")); description = request.form.get("description", "").strip()
    if amount <= 0 or not description: flash("Enter a valid extra charge amount and reason", "error"); return redirect(url_for("repair.view_repair", id=repair.id))
    prior_extras = _extra_total(repair.id); current_total = _money(repair.final_amount); explicit_base = current_total - prior_extras if current_total > prior_extras else Decimal("0"); base = explicit_base if explicit_base > 0 else _money(repair.estimated_amount)
    db.session.add(RepairExtraCharge(repair_id=repair.id, amount=amount, description=description, added_by_id=g.current_user.id)); repair.final_amount = base + prior_extras + amount
    db.session.commit(); flash(f"Extra charge ₹{amount:.2f} added", "success"); return redirect(url_for("repair.view_repair", id=repair.id))


@billing_bp.route("/repair/<int:repair_id>/doorstep-payment", methods=["POST"])
@role_required("admin", "manager", "staff", "accounts", "technician")
def collect_doorstep_payment(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id).with_for_update().first_or_404()
    if g.current_user and g.current_user.role == "technician" and repair.assigned_technician_id != g.current_user.id: return ("Forbidden", 403)
    if repair.service_type != "Doorstep": flash("This payment action is only for Doorstep jobs", "error"); return redirect(url_for("repair.view_repair", id=repair.id))
    if repair.status != "Completed": flash("Doorstep job must be Completed after QC After before payment", "error"); return redirect(url_for("repair.view_repair", id=repair.id))
    method = request.form.get("payment_method", ""); amount = _money(request.form.get("amount"))
    if method not in PAYMENT_METHODS or amount <= 0: flash("Enter a valid payment amount and method", "error"); return redirect(url_for("repair.view_repair", id=repair.id))
    final_amount = _sync_doorstep_final_amount(repair); amount_paid = _money(repair.amount_paid); outstanding = max(final_amount - amount_paid, Decimal("0"))
    if final_amount <= 0: flash("Set the job amount before collecting payment.", "error"); return redirect(url_for("repair.view_repair", id=repair.id))
    if amount > outstanding: db.session.commit(); flash(f"Payment cannot exceed ₹{outstanding:.2f}", "error"); return redirect(url_for("repair.view_repair", id=repair.id))
    payment = Payment(payment_number=_number("PAY", Payment, "payment_number"), repair_id=repair.id, invoice_id=repair.invoice.id if repair.invoice else None, amount=amount, payment_method=method, payment_type="Payment", reference=request.form.get("reference", "").strip() or None, notes="Doorstep payment collected after job completion", received_by_id=g.current_user.id if g.current_user else None)
    db.session.add(payment); repair.amount_paid = amount_paid + amount; remaining = max(final_amount - repair.amount_paid, Decimal("0")); repair.payment_status = "Paid" if remaining == 0 else "Partially Paid"; repair.payment_method = method
    if repair.invoice: repair.invoice.status = "Paid" if remaining == 0 else "Partially Paid"
    db.session.commit(); flash(f"Payment {payment.payment_number} recorded", "success"); return redirect(url_for("repair.view_repair", id=repair.id))


@billing_bp.route("/invoice/<int:invoice_id>")
@permission_required("billing")
def view_invoice(invoice_id):
    invoice = db.session.get(Invoice, invoice_id)
    if invoice is None: abort(404)
    paid, refunded, net_paid, balance = _totals(invoice); repair = invoice.repair
    parts = [usage for usage in repair.parts_used if usage.remaining_quantity > 0]; parts_sale_total = sum((usage.net_sale_total for usage in parts), Decimal("0")); extras_total = _extra_total(repair.id); base_service_amount = max(invoice.subtotal - extras_total - parts_sale_total, Decimal("0"))
    warranty_end = None
    if repair.warranty_days and repair.delivered_at:
        from datetime import timedelta
        warranty_end = repair.delivered_at + timedelta(days=repair.warranty_days)
    return render_template("billing/invoice.html", invoice=invoice, paid=paid, refunded=refunded, net_paid=net_paid, balance=balance, parts=parts, parts_sale_total=parts_sale_total, extras_total=extras_total, base_service_amount=base_service_amount, warranty_end=warranty_end)


@billing_bp.route("/invoice/<int:invoice_id>/payment", methods=["POST"])
@permission_required("billing")
def record_payment(invoice_id):
    invoice = Invoice.query.filter_by(id=invoice_id).with_for_update().first_or_404(); payment_type = request.form.get("payment_type", "Payment"); method = request.form.get("payment_method", ""); amount = _money(request.form.get("amount"))
    if payment_type not in PAYMENT_TYPES or method not in PAYMENT_METHODS or amount <= 0: flash("Invalid payment details", "error"); return redirect(url_for("billing.view_invoice", invoice_id=invoice_id))
    paid, refunded, net_paid, balance = _totals(invoice)
    if payment_type == "Payment" and amount > balance: flash("Payment exceeds outstanding balance", "error"); return redirect(url_for("billing.view_invoice", invoice_id=invoice_id))
    if payment_type == "Refund" and amount > net_paid: flash("Refund exceeds net amount paid", "error"); return redirect(url_for("billing.view_invoice", invoice_id=invoice_id))
    payment = Payment(payment_number=_number("PAY", Payment, "payment_number"), repair_id=invoice.repair_id, invoice_id=invoice.id, amount=amount, payment_method=method, payment_type=payment_type, reference=request.form.get("reference", "").strip() or None, notes=request.form.get("notes", "").strip() or None, received_by_id=g.current_user.id if g.current_user else None); db.session.add(payment)
    net_paid = net_paid + amount if payment_type == "Payment" else net_paid - amount; outstanding = max(invoice.total - net_paid, Decimal("0")); invoice.status = "Paid" if outstanding == 0 else "Partially Paid" if net_paid > 0 else "Issued"; repair = invoice.repair; repair.amount_paid = max(net_paid, Decimal("0")); repair.payment_status = "Paid" if outstanding == 0 else "Partially Paid" if net_paid > 0 else "Unpaid"; repair.payment_method = method
    db.session.commit(); flash(f"{payment_type} {payment.payment_number} recorded", "success"); return redirect(url_for("billing.view_invoice", invoice_id=invoice_id))
