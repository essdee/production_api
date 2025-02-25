import frappe

def execute():
    frappe.db.sql(
        """
            Update `tabCutting Plan` set version = 'V1' where 1 = 1
        """
    )
