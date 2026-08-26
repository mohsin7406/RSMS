def test_operational_templates_exist(app):
    required = [
        "dashboard.html",
        "repairs/list.html",
        "repairs/detail.html",
        "customers/list.html",
        "leads/list.html",
        "leads/form.html",
        "bookings/list.html",
        "bookings/form.html",
        "inventory/list.html",
        "inventory/form.html",
        "qc/detail.html",
        "billing/invoice.html",
        "customer_status/repair.html",
        "technician/dashboard.html",
        "reports/dashboard.html",
        "reports/repairs.html",
        "reports/profitability.html",
    ]
    for template_name in required:
        app.jinja_env.get_template(template_name)
