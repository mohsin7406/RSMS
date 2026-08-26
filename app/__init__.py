import os
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from app.config import config_by_name
from app.extensions import db, limiter, migrate
from app.security import register_security

def create_app(config_name=None):
    app=Flask(__name__); config_name=config_name or os.environ.get("FLASK_ENV","production"); config_class=config_by_name.get(config_name,config_by_name["production"]); app.config.from_object(config_class)
    if config_name=="production":
        required={"SECRET_KEY":app.config.get("SECRET_KEY"),"DATABASE_URL":app.config.get("SQLALCHEMY_DATABASE_URI"),"RATELIMIT_STORAGE_URI":app.config.get("RATELIMIT_STORAGE_URI")}; missing=[key for key,value in required.items() if not value]
        if missing: raise RuntimeError("Missing required production environment variables: "+", ".join(missing))
        if str(app.config["SQLALCHEMY_DATABASE_URI"]).startswith("sqlite:"): raise RuntimeError("SQLite is not supported for production RSMS. Configure PostgreSQL DATABASE_URL.")
        if app.config["RATELIMIT_STORAGE_URI"]=="memory://": raise RuntimeError("Production rate limiting requires a shared backend such as Redis.")
        if len(str(app.config["SECRET_KEY"]))<32: raise RuntimeError("SECRET_KEY must be at least 32 characters in production.")
    if app.config.get("TRUST_PROXY"): app.wsgi_app=ProxyFix(app.wsgi_app,x_for=1,x_proto=1,x_host=1,x_port=1)
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
    from app.routes.system_update import system_update_bp
    from app.routes.lead_webhook import lead_webhook_bp
    from app.routes.lead_webhook_settings import lead_webhook_settings_bp
    from app.services import notification_hooks  # noqa:F401
    for bp in [main_bp,auth_bp,customer_bp,repair_bp,inventory_bp,billing_bp,qc_bp,warranty_bp,profitability_bp,leads_bp,bookings_bp,conversion_bp,technician_bp,confirmation_bp,customer_status_bp,users_bp,notifications_bp,sms_logs_bp,materials_bp,purchases_bp,ops_bp,settings_bp,system_update_bp,lead_webhook_bp,lead_webhook_settings_bp]: app.register_blueprint(bp)
    from app.pagination_overrides import register_pagination_overrides
    register_pagination_overrides(app)
    from app.services.settings import get_setting,get_bool,get_options
    from app.services.system_updater import current_version
    @app.context_processor
    def inject_runtime_settings(): return {"system_setting":get_setting,"system_setting_bool":get_bool,"setting_options":get_options,"rsms_version":current_version}
    from app.commands import create_admin,reset_admin_password,seed_db,seed_db_all
    app.cli.add_command(create_admin); app.cli.add_command(reset_admin_password); app.cli.add_command(seed_db_all); app.cli.add_command(seed_db)
    return app
