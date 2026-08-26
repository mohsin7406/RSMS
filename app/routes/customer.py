from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Booking, Customer, Lead, Payment, RepairOrder, WarrantyClaim
from app.security import permission_required, role_required

customer_bp = Blueprint("customer", __name__, url_prefix="/customer")
PER_PAGE=20

def _customer_form_values():
    return {"name":request.form.get("name","").strip(),"email":request.form.get("email","").strip().lower() or None,"phone":request.form.get("phone","").strip()}

@customer_bp.route("/add",methods=["GET","POST"])
@permission_required("customers")
def add_customer():
    if request.method=="POST":
        values=_customer_form_values()
        if not values["name"] or not values["phone"]: flash("Name and phone are required","error"); return render_template("customers/form.html",action="Add")
        if values["email"] and Customer.query.filter_by(email=values["email"]).first(): flash("Customer email already exists","error"); return render_template("customers/form.html",action="Add")
        customer=Customer(**values); db.session.add(customer)
        try: db.session.commit()
        except IntegrityError: db.session.rollback(); flash("Customer could not be created","error"); return render_template("customers/form.html",action="Add")
        flash("Customer created successfully","success"); return redirect(url_for("customer.view_customers"))
    return render_template("customers/form.html",action="Add")

@customer_bp.route("/edit/<int:id>",methods=["GET","POST"])
@permission_required("customers")
def edit_customer(id):
    customer=Customer.query.get_or_404(id)
    if request.method=="POST":
        values=_customer_form_values()
        if not values["name"] or not values["phone"]: flash("Name and phone are required","error"); return render_template("customers/form.html",action="Edit",customer=customer)
        duplicate=Customer.query.filter(Customer.email==values["email"],Customer.id!=customer.id).first() if values["email"] else None
        if duplicate: flash("Customer email already exists","error"); return render_template("customers/form.html",action="Edit",customer=customer)
        customer.name=values["name"]; customer.email=values["email"]; customer.phone=values["phone"]; db.session.commit(); flash("Customer updated successfully","success"); return redirect(url_for("customer.customer_details",id=customer.id))
    return render_template("customers/form.html",action="Edit",customer=customer)

@customer_bp.route("/delete/<int:id>",methods=["POST"])
@role_required("admin")
def delete_customer(id):
    customer=Customer.query.get_or_404(id)
    if customer.repair_orders: flash("Cannot delete a customer with existing repair orders","error"); return redirect(url_for("customer.view_customers"))
    db.session.delete(customer); db.session.commit(); flash("Customer deleted successfully","success"); return redirect(url_for("customer.view_customers"))

@customer_bp.route("/view")
@permission_required("customers")
def view_customers():
    page=max(request.args.get("page",1,type=int),1);pagination=Customer.query.order_by(Customer.created_at.desc()).paginate(page=page,per_page=PER_PAGE,error_out=False);return render_template("customers/list.html",customers=pagination.items,pagination=pagination)

@customer_bp.route("/details/<int:id>")
@permission_required("customers")
def customer_details(id):
    customer=Customer.query.get_or_404(id)
    repairs=RepairOrder.query.filter_by(customer_id=id).filter(RepairOrder.deleted_at.is_(None)).order_by(RepairOrder.created_at.desc()).all()
    repair_ids=[r.id for r in repairs]
    payments=Payment.query.filter(Payment.repair_id.in_(repair_ids)).order_by(Payment.created_at.desc()).all() if repair_ids else []
    bookings=Booking.query.filter_by(customer_id=id).order_by(Booking.created_at.desc()).all()
    leads=Lead.query.filter_by(customer_id=id).order_by(Lead.created_at.desc()).all()
    warranties=WarrantyClaim.query.filter(WarrantyClaim.repair_id.in_(repair_ids)).order_by(WarrantyClaim.opened_at.desc()).all() if repair_ids else []
    billed=sum((Decimal(r.final_amount or 0) for r in repairs),Decimal("0")); paid=sum((Decimal(p.amount or 0) for p in payments if p.payment_type=="Payment"),Decimal("0")); refunded=sum((Decimal(p.amount or 0) for p in payments if p.payment_type=="Refund"),Decimal("0")); net_paid=max(paid-refunded,Decimal("0")); outstanding=max(billed-net_paid,Decimal("0"))
    return render_template("customers/detail.html",customer=customer,repairs=repairs,payments=payments,bookings=bookings,leads=leads,warranties=warranties,billed=billed,net_paid=net_paid,outstanding=outstanding)
