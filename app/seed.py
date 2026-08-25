from faker import Faker
import random
import secrets

from app.extensions import db
from app.models import Customer, RepairOrder, User


fake = Faker()
STATUSES = ["Pending", "In Progress", "Completed"]
DEVICES = ["iPhone 11", "Samsung A51", "Laptop", "iPad", "MacBook"]
ROLES = ["admin", "staff", "technician", "customer"]


def _random_demo_password():
    return secrets.token_urlsafe(18)


def seed_users(n=5):
    for _ in range(n):
        user = User(email=fake.unique.email(), role=random.choice(ROLES))
        user.set_password(_random_demo_password())
        db.session.add(user)
    db.session.commit()


def seed_customers(n=20):
    customers = []
    for _ in range(n):
        customer = Customer(name=fake.name(), email=fake.unique.email(), phone=fake.phone_number())
        db.session.add(customer)
        customers.append(customer)
    db.session.commit()
    return customers


def seed_repairs(customers, n=50):
    for _ in range(n):
        db.session.add(RepairOrder(
            customer_id=random.choice(customers).id,
            device=random.choice(DEVICES),
            issue_description=fake.sentence(),
            status=random.choice(STATUSES),
        ))
    db.session.commit()


def seed_all():
    try:
        with db.session.begin():
            for _ in range(5):
                user = User(email=fake.unique.email(), role=random.choice(ROLES))
                user.set_password(_random_demo_password())
                db.session.add(user)

            customers = []
            for _ in range(20):
                customer = Customer(name=fake.name(), email=fake.unique.email(), phone=fake.phone_number())
                db.session.add(customer)
                customers.append(customer)

            db.session.flush()

            for _ in range(50):
                db.session.add(RepairOrder(
                    customer_id=random.choice(customers).id,
                    device=random.choice(DEVICES),
                    issue_description=fake.sentence(),
                    status=random.choice(STATUSES),
                ))
    except Exception:
        db.session.rollback()
        raise
