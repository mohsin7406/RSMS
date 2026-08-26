import os
from flask import Flask
from app.config import config_by_name
from app.extensions import db, limiter, migrate
from app.security import register_security

def create_app(config_name=None):
    app=Flask(__name__); config_name=config_name or os.environ.get("FLASK_ENV","production"); config_class=config_by_name.get(config_name,config_by_name["production"]); app.config.from_object(config_class)
    if config_name=="production":
        if not app.config.get("SECRET_KEY"): raise RuntimeError("SECRET_KEY must be set in production")
        if not app.config.get("SQLALCHEMY_DATABASE_URI"): raise RuntimeError("DATABASE_URL must be set in production")
        if not app.config.get("RATELIMIT_STORAGE_URI"): raise RuntimeError("RATELIMIT_STORAGE_URI must be set in production")
    db.init_app(app); migrate.init_app(app,db); limiter.init_app(app); register_security(app)
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.customer import customer_bp
    from app.routes.repair_order import repair_bp
    from app.routes import repair_permissions  # noqa:F401
    from app.routes.inventory import inventory_bp
    from app.routes.billing import billing_bp
    from app.routes.qc import qc_bp
    from app.routes.warranty import warranty_bp
    from app.routes.profitability import profitability_bp
    from app.routes.leads import leads_bp
    from app.routes.bookings import bookings_bp
    from app.routes.booking_conversion import conversion_bp
    from app.routes.technician import technician_bp
    from app.routes.service_confirmation import confirmation_bp
    from app.routes.customer_status import customer_status_bp
    from app.routes.users import users_bp
    from app.routes.notification_settings import notifications_bp
    from app.routes.sms_logs import sms_logs_bp
    from app.routes.job_materials import materials_bp
    from app.routes.purchases import purchases_bp
    from app.routes.operations import ops_bp
    from app.routes.system_settings import settings_bp
    from app.services import notification_hooks  # noqa:F401
    for bp in [main_bp,auth_bp,customer_bp,repair_bp,inventory_bp,billing_bp,qc_bp,warranty_bp,profitability_bp,leads_bp,bookings_bp,conversion_bp,technician_bp,confirmation_bp,customer_status_bp,users_bp,notifications_bp,sms_logs_bp,materials_bp,purchases_bp,ops_bp,settings_bp]: app.register_blueprint(bp)
    from app.commands import create_admin,reset_admin_password,seed_db,seed_db_all
    app.cli.add_command(create_admin); app.cli.add_command(reset_admin_password); app.cli.add_command(seed_db_all); app.cli.add_command(seed_db)
    return app
