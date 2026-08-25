from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for, g

from app.extensions import db
from app.models import Invoice, Payment, RepairOrder
from app.models.payment import PAYMENT_METHODS, PAYMENT_TYPES
from app.security import role_required

billing_bp = Blueprint("billing", __name__, url_prefix="/billing")


def _money(value):
    try:
        amount = Decimal(value or "0")
        return amount if amount >= 0 else Decimal("0")
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _number(prefix, model, field):
    today = datetime.utcnow().strftime("%Y%m%d")
    latest = model.query.filter(getattr(model, field).like(f"{prefix}-{today}-%")).order_by(model.id.desc()).first()
    sequence = int(getattr(latest, field).rsplit("-", 1)[-1]) + 1 if latest else 1
    return f"{prefix}-{today}-{sequence:04d}"


@billing_bp.route("/repair/<int:repair_id>/invoice", methods=["POST"])
@role_required("admin", "staff")
def create_invoice(repair_id):
    repair = RepairOrder.query.get_or_404(repair_id)
    if repair.invoice:
        return redirect(url_for("billing.view_invoice", invoice_id=repair.invoice.id))

    discount = _money(request.form.get("discount"))
    tax = _money(request.form.get("tax"))
    subtotal = _money(repair.final_amount)
    discount = min(discount, subtotal)
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
        issued_at=datetime.utcnow(),
        due_at=datetime.utcnow(),
    )
    repair.final_amount = total
    db.session.add(invoice)
    db.session.commit()
    flash(f"Invoice {invoice.invoice_number} created", "success")
    return redirect(url_for("billing.view_invoice", invoice_id=invoice.id))


@billing_bp.route("/invoice/<int:invoice_id>")
@role_required("admin", "staff", "technician")
def view_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    paid = sum((p.amount for p in invoice.payments if p.payment_type == "Payment"), Decimal("0"))
    refunded = sum((p.amount for p in invoice.payments if p.payment_type == "Refund"), Decimal("0"))
    balance = max(invoice.total - paid + refunded, Decimal("0"))
    return render_template("billing/invoice.html", invoice=invoice, paid=paid, refunded=refunded, balance=balance)


@billing_bp.route("/invoice/<int:invoice_id>/payment", methods=["POST"])
@role_required("admin", "staff")
def record_payment(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    payment_type = request.form.get("payment_type", "Payment")
    method = request.form.get("payment_method", "")
    amount = _money(request.form.get("amount"))

    if payment_type not in PAYMENT_TYPES or method not in PAYMENT_METHODS or amount <= 0:
        flash("Invalid payment details", "error")
        return redirect(url_for("billing.view_invoice", invoice_id=invoice_id))

    paid = sum((p.amount for p in invoice.payments if p.payment_type == "Payment"), Decimal("0"))
    refunded = sum((p.amount for p in invoice.payments if p.payment_type == "Refund"), Decimal("0"))
    balance = invoice.total - paid + refunded
    net_paid_before = paid - refunded
    if payment_type == "Payment" and amount > balance:
        flash("Payment exceeds outstanding balance", "error")
        return redirect(url_for("billing.view_invoice", invoice_id=invoice_id))
    if payment_type == "Refund" and amount > net_paid_before:
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

    new_paid = paid + amount if payment_type == "Payment" else paid
    new_refunded = refunded + amount if payment_type == "Refund" else refunded
    net_paid = new_paid - new_refunded
    outstanding = invoice.total - net_paid
    invoice.status = "Paid" if outstanding == 0 else "Partially Paid" if net_paid > 0 else "Issued"

    repair = invoice.repair
    repair.amount_paid = max(net_paid, Decimal("0"))
    repair.payment_status = "Paid" if outstanding == 0 else "Partially Paid" if net_paid > 0 else "Unpaid"
    repair.payment_method = method
    db.session.commit()
    flash(f"{payment_type} {payment.payment_number} recorded", "success")
    return redirect(url_for("billing.view_invoice", invoice_id=invoice_id))
