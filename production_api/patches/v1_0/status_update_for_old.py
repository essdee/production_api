import frappe


def execute():
    frappe.db.sql(
        """
            UPDATE `tabWork Order` 
            SET status = 'Submitted'
            WHERE docstatus = 1 AND (status IS NULL OR status = '' OR status = 'null')
        """
    )
