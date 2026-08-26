ROLE_LABELS={"admin":"Administrator","manager":"Manager","staff":"Staff","technician":"Technician","accounts":"Accounts","reception":"Reception / Telecaller","customer":"Customer"}; VALID_ROLES=set(ROLE_LABELS)
PERMISSION_LABELS={"repairs_view":"Repairs - View","repairs_manage":"Repairs - Manage / Update","customers":"Customers","inventory":"Inventory","leads":"Leads","bookings":"Bookings","billing":"Billing / Invoices / Payments","reports":"Reports","qc":"QC Before / QC After","users_admin":"Users & Roles","notification_settings":"SMS / WhatsApp Settings","purchases":"Purchases / Suppliers / Payables","expenses":"Expenses","audit":"System Audit Log"}; PERMISSIONS=set(PERMISSION_LABELS)
DEFAULT_ROLE_PERMISSIONS={"admin":set(PERMISSIONS),"manager":{"repairs_view","repairs_manage","customers","inventory","leads","bookings","billing","reports","qc","purchases","expenses","audit"},"staff":{"repairs_view","repairs_manage","customers","inventory","leads","bookings","billing","reports"},"technician":{"repairs_view","repairs_manage","qc"},"accounts":{"repairs_view","customers","billing","reports","purchases","expenses"},"reception":{"repairs_view","customers","leads","bookings"},"customer":set()}; ROLE_PERMISSIONS=DEFAULT_ROLE_PERMISSIONS
def role_allowed(user_role,allowed_roles): return user_role in set(allowed_roles)
def permissions_for_role(user_role):
 if user_role=='admin': return set(PERMISSIONS)
 if user_role not in VALID_ROLES:return set()
 try:
  from app.models import RolePermission
  rows=RolePermission.query.filter_by(role=user_role).all()
 except Exception:return set(DEFAULT_ROLE_PERMISSIONS.get(user_role,set()))
 if not rows:return set(DEFAULT_ROLE_PERMISSIONS.get(user_role,set()))
 return {row.permission for row in rows if row.enabled and row.permission in PERMISSIONS}
def has_permission(user_role,permission): return permission in PERMISSIONS and permission in permissions_for_role(user_role)
