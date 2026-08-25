import os

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import User
from app.seed import seed_all, seed_users, seed_customers, seed_repairs


@click.command("create-admin")
@with_appcontext
def create_admin():
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")

    if not email or "@" not in email:
        raise click.ClickException("Set a valid ADMIN_EMAIL environment variable")
    if len(password) < 12:
        raise click.ClickException("ADMIN_PASSWORD must be at least 12 characters")
    if User.query.filter_by(email=email).first():
        raise click.ClickException("A user with that email already exists")

    user = User(email=email, role="admin")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f"Admin user created: {email}")


def _demo_seed_allowed():
    return os.environ.get("ALLOW_DEMO_SEED", "false").lower() == "true"


@click.command("seed-db")
@with_appcontext
def seed_db():
    if not _demo_seed_allowed():
        raise click.ClickException("Demo seeding is disabled. Set ALLOW_DEMO_SEED=true explicitly.")
    seed_users()
    customers = seed_customers()
    seed_repairs(customers)
    click.echo("Database seeded with fake data.")


@click.command("seed-db-all")
@with_appcontext
def seed_db_all():
    if not _demo_seed_allowed():
        raise click.ClickException("Demo seeding is disabled. Set ALLOW_DEMO_SEED=true explicitly.")
    seed_all()
    click.echo("Database seeded with fake data in a single transaction.")
