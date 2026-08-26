ROLE_LABELS = {
    "admin": "Administrator",
    "manager": "Manager",
    "staff": "Staff",
    "technician": "Technician",
    "customer": "Customer",
}

VALID_ROLES = set(ROLE_LABELS)

# Compatibility aliases let new roles safely inherit existing route access
# while granular permissions are introduced route-by-route.
ROLE_INHERITS = {
    "manager": {"staff"},
}


def role_allowed(user_role, allowed_roles):
    allowed = set(allowed_roles)
    if user_role in allowed:
        return True
    return bool(ROLE_INHERITS.get(user_role, set()) & allowed)
