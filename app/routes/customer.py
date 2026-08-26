from sqlalchemy.exc import IntegrityError
from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Customer
from app.security import permission_required, role_required


customer_bp = Blueprint("customer", __name__, url_prefix="/customer")


def _customer_form_values():
    return {
        "name": request.form.get("name", "").strip(),
        "email": request.form.get("email", "").strip().lower() or None,
        "phone": request.form.get("phone", "").strip(),
    }


@customer_bp.route("/add", methods=["GET", "POST"])
@permission_required("customers")
def add_customer():
    if request.method == "POST":
        values = _customer_form_values()
        if not values["name"] or not values["phone"]:
            flash("Name and phone are required", "error")
            return render_template("customers/form.html", action="Add")

        if values["email"] and Customer.query.filter_by(email=values["email"]).first():
            flash("Customer email already exists", "error")
            return render_template("customers/form.html", action="Add")

        customer = Customer(**values)
        db.session.add(customer)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Customer could not be created", "error")
            return render_template("customers/form.html", action="Add")

        flash("Customer created successfully", "success")
        return redirect(url_for("customer.view_customers"))

    return render_template("customers/form.html", action="Add")


@customer_bp.route("/edit/<int:id>", methods=["GET", "POST"])
@permission_required("customers")
def edit_customer(id):
    customer = Customer.query.get_or_404(id)

    if request.method == "POST":
        values = _customer_form_values()
        if not values["name"] or not values["phone"]:
            flash("Name and phone are required", "error")
            return render_template("customers/form.html", action="Edit", customer=customer)

        duplicate = Customer.query.filter(
            Customer.email == values["email"], Customer.id != customer.id
        ).first() if values["email"] else None
        if duplicate:
            flash("Customer email already exists", "error")
            return render_template("customers/form.html", action="Edit", customer=customer)

        customer.name = values["name"]
        customer.email = values["email"]
        customer.phone = values["phone"]
        db.session.commit()
        flash("Customer updated successfully", "success")
        return redirect(url_for("customer.view_customers"))

    return render_template("customers/form.html", action="Edit", customer=customer)


@customer_bp.route("/delete/<int:id>", methods=["POST"])
@role_required("admin")
def delete_customer(id):
    customer = Customer.query.get_or_404(id)
    if customer.repair_orders:
        flash("Cannot delete a customer with existing repair orders", "error")
        return redirect(url_for("customer.view_customers"))

    db.session.delete(customer)
    db.session.commit()
    flash("Customer deleted successfully", "success")
    return redirect(url_for("customer.view_customers"))


@customer_bp.route("/view", methods=["GET"])
@permission_required("customers")
def view_customers():
    customers = Customer.query.order_by(Customer.created_at.desc()).all()
    return render_template("customers/list.html", customers=customers)


@customer_bp.route("/details/<int:id>", methods=["GET"])
@permission_required("customers")
def customer_details(id):
    customer = Customer.query.get_or_404(id)
    return render_template("customers/detail.html", customer=customer)
