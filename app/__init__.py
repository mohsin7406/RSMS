import os

from flask import Flask

from app.config import config_by_name
from app.extensions import db, limiter, migrate
from app.security import register_security


def create_app(config_name=None):
    app = Flask(__name__)

    config_name = config_name or os.environ.get("FLASK_ENV", "production")
    config_class = config_by_name.get(config_name, config_by_name["production"])
    app.config.from_object(config_class)

    if config_name == "production":
        if not app.config.get("SECRET_KEY"):
            raise RuntimeError("SECRET_KEY must be set in production")
        if not app.config.get("SQLALCHEMY_DATABASE_URI"):
            raise RuntimeError("DATABASE_URL must be set in production")

    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    register_security(app)

    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.customer import customer_bp
    from app.routes.repair_order import repair_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(repair_bp)

    from app.commands import create_admin, seed_db, seed_db_all
    app.cli.add_command(create_admin)
    app.cli.add_command(seed_db_all)
    app.cli.add_command(seed_db)

    return app
