import frappe


def execute():
    # First pass: set null/empty statuses to "Submitted" (original patch logic)
    frappe.db.sql(
        """
            UPDATE `tabWork Order`
            SET status = 'Submitted'
            WHERE docstatus = 1 AND (status IS NULL OR status = '' OR status = 'null')
        """
    )
    frappe.db.commit()

    # Second pass: recalculate actual status for all "Submitted" work orders
    work_orders = frappe.get_all(
        "Work Order",
        filters={"docstatus": 1, "status": "Submitted"},
        pluck="name",
    )
    for i, name in enumerate(work_orders):
        doc = frappe.get_doc("Work Order", name)
        doc.set_status()
        if doc.status != "Submitted":
            doc.db_set("status", doc.status, update_modified=False)
        if i % 100 == 0:
            frappe.db.commit()
    frappe.db.commit()
