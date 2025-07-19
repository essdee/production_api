import frappe

def execute():
    frappe.db.sql(
        """
            UPDATE `tabCutting LaySheet` SET posting_date = DATE(creation), posting_time = TIME(creation)
            WHERE status != 'Cancelled'
        """
    )
