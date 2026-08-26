from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for, g
from flask import abort

from app.extensions import db
from app.models import Invoice, Payment, RepairOrder
from app.models.payment import PAYMENT_METHODS, PAYMENT_TYPES
from app.security import permission_required

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


def _create_invoice_for_repair(repair, discount=Decimal("0"), tax=Decimal("0")):
    if repair.invoice:
        return repair.invoice
    subtotal = _money(repair.final_amount)
    discount = min(_money(discount), subtotal)
    tax = _money(tax)
    total = subtotal - discount + tax
    invoice = Invoice(
        invoice_number=_number("INV", Invoice, "invoice_number"),
        repair_id=repair.id,
        customer_id=repair.customer_id,
        subtotal=subtotal,
        discount=discount,
        tax=tax,
        total=total,
        status="Issued",
        issued_at=datetime.now(timezone.utc),
        due_at=datetime.now(timezone.utc),
    )
    repair.final_amount = total
    db.session.add(invoice)
    db.session.flush()
    return invoice


def _apply_payment(invoice, amount, method, reference=None, notes=None):
    paid, refunded, net_paid, balance = _totals(invoice)
    if amount <= 0:
        return None, "Payment amount must be greater than zero"
    if amount > balance:
        return None, "Payment exceeds outstanding balance"

    payment = Payment(
        payment_number=_number("PAY", Payment, "payment_number"),
        repair_id=invoice.repair_id,
        invoice_id=invoice.id,
        amount=amount,
        payment_method=method,
        payment_type="Payment",
        reference=reference or None,
        notes=notes or None,
        received_by_id=g.current_user.id if g.current_user else None,
    )
    db.session.add(payment)
    net_paid += amount
    outstanding = max(invoice.total - net_paid, Decimal("0"))
    invoice.status = "Paid" if outstanding == 0 else "Partially Paid"
    repair = invoice.repair
    repair.amount_paid = max(net_paid, Decimal("0"))
    repair.payment_status = "Paid" if outstanding == 0 else "Partially Paid"
    repair.payment_method = method
    return payment, None


@billing_bp.route("/repair/<int:repair_id>/invoice", methods=["POST"])
@permission_required("billing")
def create_invoice(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id).with_for_update().first_or_404()
    if repair.invoice:
        return redirect(url_for("billing.view_invoice", invoice_id=repair.invoice.id))

    invoice = _create_invoice_for_repair(
        repair,
        discount=_money(request.form.get("discount")),
        tax=_money(request.form.get("tax")),
    )
    db.session.commit()
    flash(f"Invoice {invoice.invoice_number} created", "success")
    return redirect(url_for("billing.view_invoice", invoice_id=invoice.id))


@billing_bp.route("/repair/<int:repair_id>/doorstep-payment", methods=["POST"])
@permission_required("billing")
def collect_doorstep_payment(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id).with_for_update().first_or_404()
    if repair.service_type != "Doorstep":
        flash("This payment action is only for Doorstep jobs", "error")
        return redirect(url_for("repair.view_repair", id=repair.id))
    if repair.status != "Completed":
        flash("Doorstep job must be Completed after QC After before payment", "error")
        return redirect(url_for("repair.view_repair", id=repair.id))

    method = request.form.get("payment_method", "")
    amount = _money(request.form.get("amount"))
    if method not in PAYMENT_METHODS:
        flash("Select a valid payment method", "error")
        return redirect(url_for("repair.view_repair", id=repair.id))

    # The invoice row is created internally in the same transaction so the
    # payment has a valid accounting parent. To staff, this remains the desired
    # operational flow: Job Complete -> Collect Payment -> Invoice.
    invoice = _create_invoice_for_repair(repair)
    payment, error = _apply_payment(
        invoice,
        amount,
        method,
        reference=request.form.get("reference", "").strip(),
        notes="Doorstep payment collected after job completion",
    )
    if error:
        db.session.rollback()
        flash(error, "error")
        return redirect(url_for("repair.view_repair", id=repair.id))

    db.session.commit()
    flash(f"Payment {payment.payment_number} recorded. Invoice {invoice.invoice_number} generated", "success")
    return redirect(url_for("billing.view_invoice", invoice_id=invoice.id))


@billing_bp.route("/invoice/<int:invoice_id>")
@permission_required("billing")
def view_invoice(invoice_id):
    invoice = db.session.get(Invoice, invoice_id)
    if invoice is None:
        abort(404)
    paid, refunded, net_paid, balance = _totals(invoice)
    return render_template("billing/invoice.html", invoice=invoice, paid=paid, refunded=refunded, net_paid=net_paid, balance=balance)


@billing_bp.route("/invoice/<int:invoice_id>/payment", methods=["POST"])
@permission_required("billing")
def record_payment(invoice_id):
    invoice = Invoice.query.filter_by(id=invoice_id).with_for_update().first_or_404()
    payment_type = request.form.get("payment_type", "Payment")
    method = request.form.get("payment_method", "")
    amount = _money(request.form.get("amount"))

    if payment_type not in PAYMENT_TYPES or method not in PAYMENT_METHODS or amount <= 0:
        flash("Invalid payment details", "error")
        return redirect(url_for("billing.view_invoice", invoice_id=invoice_id))

    paid, refunded, net_paid, balance = _totals(invoice)
    if payment_type == "Payment" and amount > balance:
        flash("Payment exceeds outstanding balance", "error")
        return redirect(url_for("billing.view_invoice", invoice_id=invoice_id))
    if payment_type == "Refund" and amount > net_paid:
        flash("Refund exceeds net amount paid", "error")
        return redirect(url_for("billing.view_invoice", invoice_id=invoice_id))

    payment = Payment(
        payment_number=_number("PAY", Payment, "payment_number"),
        repair_id=invoice.repair_id,
        invoice_id=invoice.id,
        amount=amount,
        payment_method=method,
        payment_type=payment_type,
        reference=request.form.get("reference", "").strip() or None,
        notes=request.form.get("notes", "").strip() or None,
        received_by_id=g.current_user.id if g.current_user else None,
    )
    db.session.add(payment)

    if payment_type == "Payment":
        net_paid += amount
    else:
        net_paid -= amount

    outstanding = max(invoice.total - net_paid, Decimal("0"))
    invoice.status = "Paid" if outstanding == 0 else "Partially Paid" if net_paid > 0 else "Issued"

    repair = invoice.repair
    repair.amount_paid = max(net_paid, Decimal("0"))
    repair.payment_status = "Paid" if outstanding == 0 else "Partially Paid" if net_paid > 0 else "Unpaid"
    repair.payment_method = method

    db.session.commit()
    flash(f"{payment_type} {payment.payment_number} recorded", "success")
    return redirect(url_for("billing.view_invoice", invoice_id=invoice_id))
