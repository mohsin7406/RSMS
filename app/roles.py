ROLE_LABELS = {
    "admin": "Administrator",
    "manager": "Manager",
    "staff": "Staff",
    "technician": "Technician",
    "accounts": "Accounts",
    "reception": "Reception / Telecaller",
    "customer": "Customer",
}

VALID_ROLES = set(ROLE_LABELS)

PERMISSIONS = {
    "repairs_view",
    "repairs_manage",
    "customers",
    "inventory",
    "leads",
    "bookings",
    "billing",
    "reports",
    "qc",
    "users_admin",
    "notification_settings",
}

ROLE_PERMISSIONS = {
    "admin": set(PERMISSIONS),
    "manager": {
        "repairs_view", "repairs_manage", "customers", "inventory", "leads",
        "bookings", "billing", "reports", "qc",
    },
    "staff": {
        "repairs_view", "repairs_manage", "customers", "inventory", "leads",
        "bookings", "billing", "reports",
    },
    # Existing route-level checks still restrict technicians to their assigned jobs.
    "technician": {"repairs_view", "repairs_manage", "qc"},
    "accounts": {"repairs_view", "customers", "billing", "reports"},
    "reception": {"repairs_view", "customers", "leads", "bookings"},
    "customer": set(),
}


def role_allowed(user_role, allowed_roles):
    return user_role in set(allowed_roles)


def has_permission(user_role, permission):
    if permission not in PERMISSIONS:
        return False
    return permission in ROLE_PERMISSIONS.get(user_role, set())
