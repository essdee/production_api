import frappe


REQUIRED_ROLES = {
    "Merch User": {"desk_access": 1},
    "Merch Manager": {"desk_access": 1},
    "Senior Merch": {"desk_access": 1},
    "Brand QA User": {"desk_access": 1},
    "Brand QA Manager": {"desk_access": 1},
    "Finishing User": {"desk_access": 1},
    "Factory Manager": {"desk_access": 1},
    "DocType Reader": {"desk_access": 1},
}

COMMON_ROLE_VALUES = {
    "disabled": 0,
    "home_page": None,
    "restrict_to_domain": None,
    "two_factor_auth": 0,
}


def ensure_role(role_name, values):
    """Create or update an application Role in place without deleting it."""
    desired_values = {**COMMON_ROLE_VALUES, **values}
    if frappe.db.exists("Role", role_name):
        role = frappe.get_doc("Role", role_name)
        changed = False
        for fieldname, value in desired_values.items():
            if role.get(fieldname) != value:
                role.set(fieldname, value)
                changed = True
        if changed:
            role.save(ignore_permissions=True)
        return role

    role = frappe.new_doc("Role")
    role.role_name = role_name
    role.update(desired_values)
    role.insert(ignore_permissions=True)
    return role


def ensure_required_roles():
    for role_name, values in REQUIRED_ROLES.items():
        ensure_role(role_name, values)
