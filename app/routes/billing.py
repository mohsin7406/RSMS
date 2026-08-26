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


def _sync_doorstep_final_amount(repair):
    """Keep Doorstep final amount equal to base estimate plus all audited extras.

    This also repairs older jobs whose final_amount was incorrectly replaced by an
    extra charge instead of increased by it.
    """
    extras_total = sum(
        (charge.amount for charge in RepairExtraCharge.query.filter_by(repair_id=repair.id).all()),
        Decimal("0"),
    )
    estimate = _money(repair.estimated_amount)

    if estimate > 0:
        repair.final_amount = estimate + extras_total
    else:
        # Older/manual jobs may have no estimate. Preserve their existing base
        # amount while still ensuring recorded extras are represented.
        current_final = _money(repair.final_amount)
        repair.final_amount = max(current_final, extras_total)

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
    db.session.add(invoice)
    db.session.flush()

    unlinked = Payment.query.filter_by(repair_id=repair.id, invoice_id=None).all()
    for payment in unlinked:
        payment.invoice_id = invoice.id

    net_paid = max(sum((p.amount for p in unlinked if p.payment_type == "Payment"), Decimal("0")) - sum((p.amount for p in unlinked if p.payment_type == "Refund"), Decimal("0")), Decimal("0"))
    outstanding = max(total - net_paid, Decimal("0"))
    invoice.status = "Paid" if outstanding == 0 and total > 0 else "Partially Paid" if net_paid > 0 else "Issued"
    repair.final_amount = total
    repair.amount_paid = net_paid
    repair.payment_status = "Paid" if outstanding == 0 and total > 0 else "Partially Paid" if net_paid > 0 else "Unpaid"
    return invoice


@billing_bp.route("/repair/<int:repair_id>/invoice", methods=["POST"])
@permission_required("billing")
def create_invoice(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id).with_for_update().first_or_404()
    if repair.invoice:
        return redirect(url_for("billing.view_invoice", invoice_id=repair.invoice.id))
    invoice = _create_invoice_for_repair(repair, discount=_money(request.form.get("discount")), tax=_money(request.form.get("tax")))
    db.session.commit()
    flash(f"Invoice {invoice.invoice_number} created", "success")
    return redirect(url_for("billing.view_invoice", invoice_id=invoice.id))


@billing_bp.route("/repair/<int:repair_id>/extra-charge", methods=["POST"])
@role_required("admin", "manager", "staff", "technician")
def add_extra_charge(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id).with_for_update().first_or_404()
    if g.current_user and g.current_user.role == "technician" and repair.assigned_technician_id != g.current_user.id:
        return ("Forbidden", 403)
    if repair.service_type != "Doorstep":
        flash("Extra charge action is currently available for Doorstep jobs", "error")
        return redirect(url_for("repair.view_repair", id=repair.id))
    if repair.invoice:
        flash("Invoice already exists. Add adjustments from billing instead of changing the job total.", "error")
        return redirect(url_for("repair.view_repair", id=repair.id))

    amount = _money(request.form.get("amount"))
    description = request.form.get("description", "").strip()
    if amount <= 0 or not description:
        flash("Enter a valid extra charge amount and reason", "error")
        return redirect(url_for("repair.view_repair", id=repair.id))

    charge = RepairExtraCharge(
        repair_id=repair.id,
        amount=amount,
        description=description,
        added_by_id=g.current_user.id,
    )
    db.session.add(charge)
    db.session.flush()

    _sync_doorstep_final_amount(repair)

    db.session.commit()
    flash(f"Extra charge ₹{amount:.2f} added. New final amount: ₹{repair.final_amount:.2f}", "success")
    return redirect(url_for("repair.view_repair", id=repair.id))


@billing_bp.route("/repair/<int:repair_id>/doorstep-payment", methods=["POST"])
@role_required("admin", "manager", "staff", "accounts", "technician")
def collect_doorstep_payment(repair_id):
    repair = RepairOrder.query.filter_by(id=repair_id).with_for_update().first_or_404()
    if g.current_user and g.current_user.role == "technician" and repair.assigned_technician_id != g.current_user.id:
        return ("Forbidden", 403)
    if repair.service_type != "Doorstep":
        flash("This payment action is only for Doorstep jobs", "error")
        return redirect(url_for("repair.view_repair", id=repair.id))
    if repair.status != "Completed":
        flash("Doorstep job must be Completed after QC After before payment", "error")
        return redirect(url_for("repair.view_repair", id=repair.id))

    method = request.form.get("payment_method", "")
    amount = _money(request.form.get("amount"))
    if method not in PAYMENT_METHODS or amount <= 0:
        flash("Enter a valid payment amount and method", "error")
        return redirect(url_for("repair.view_repair", id=repair.id))

    # Recalculate from the estimate + audited extras every time. This heals old
    # technician jobs where final_amount was incorrectly overwritten by an extra.
    final_amount = _sync_doorstep_final_amount(repair)
    amount_paid = _money(repair.amount_paid)
    outstanding = max(final_amount - amount_paid, Decimal("0"))
    if final_amount <= 0:
        flash("Final repair amount has not been set. Add the job amount or an extra charge before collecting payment.", "error")
        return redirect(url_for("repair.view_repair", id=repair.id))
    if amount > outstanding:
        db.session.commit()
        flash(
            f"Payment cannot exceed ₹{outstanding:.2f}. Final Amount: ₹{final_amount:.2f}; Already Paid: ₹{amount_paid:.2f}; Outstanding: ₹{outstanding:.2f}",
            "error",
        )
        return redirect(url_for("repair.view_repair", id=repair.id))

    payment = Payment(
        payment_number=_number("PAY", Payment, "payment_number"),
        repair_id=repair.id,
        invoice_id=repair.invoice.id if repair.invoice else None,
        amount=amount,
        payment_method=method,
        payment_type="Payment",
        reference=request.form.get("reference", "").strip() or None,
        notes="Doorstep payment collected after job completion",
        received_by_id=g.current_user.id if g.current_user else None,
    )
    db.session.add(payment)
    repair.amount_paid = amount_paid + amount
    remaining = max(final_amount - repair.amount_paid, Decimal("0"))
    repair.payment_status = "Paid" if remaining == 0 else "Partially Paid"
    repair.payment_method = method

    if repair.invoice:
        repair.invoice.status = "Paid" if remaining == 0 else "Partially Paid"

    db.session.commit()
    flash(f"Payment {payment.payment_number} recorded", "success")
    return redirect(url_for("repair.view_repair", id=repair.id))


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

    payment = Payment(payment_number=_number("PAY", Payment, "payment_number"), repair_id=invoice.repair_id, invoice_id=invoice.id, amount=amount, payment_method=method, payment_type=payment_type, reference=request.form.get("reference", "").strip() or None, notes=request.form.get("notes", "").strip() or None, received_by_id=g.current_user.id if g.current_user else None)
    db.session.add(payment)

    net_paid = net_paid + amount if payment_type == "Payment" else net_paid - amount
    outstanding = max(invoice.total - net_paid, Decimal("0"))
    invoice.status = "Paid" if outstanding == 0 else "Partially Paid" if net_paid > 0 else "Issued"
    repair = invoice.repair
    repair.amount_paid = max(net_paid, Decimal("0"))
    repair.payment_status = "Paid" if outstanding == 0 else "Partially Paid" if net_paid > 0 else "Unpaid"
    repair.payment_method = method

    db.session.commit()
    flash(f"{payment_type} {payment.payment_number} recorded", "success")
    return redirect(url_for("billing.view_invoice", invoice_id=invoice_id))
