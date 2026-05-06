import frappe
from frappe import _
from frappe.utils import add_days, nowdate


def execute(filters=None):
    filters = filters or {}
    doctype = filters.get("doctype") or "DocType"
    days = int(filters.get("days") or 7)

    if not frappe.db.exists("DocType", doctype):
        frappe.throw(_("DocType {0} does not exist").format(doctype))

    cutoff = add_days(nowdate(), -days)

    columns = [
        {"label": _("Name"), "fieldname": "name", "fieldtype": "Dynamic Link", "options": "doctype_name", "width": 240},
        {"label": _("DocType"), "fieldname": "doctype_name", "fieldtype": "Data", "width": 160},
        {"label": _("Modified"), "fieldname": "modified", "fieldtype": "Datetime", "width": 180},
        {"label": _("Modified By"), "fieldname": "modified_by", "fieldtype": "Link", "options": "User", "width": 200},
        {"label": _("Owner"), "fieldname": "owner", "fieldtype": "Link", "options": "User", "width": 200},
    ]

    rows = frappe.get_all(
        doctype,
        filters={"modified": [">=", cutoff]},
        fields=["name", "modified", "modified_by", "owner"],
        order_by="modified desc",
        limit=500,
    )

    for r in rows:
        r["doctype_name"] = doctype

    return columns, rows
