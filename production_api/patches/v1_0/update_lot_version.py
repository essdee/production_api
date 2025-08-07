import frappe

def execute():
    frappe.db.sql(
        """
            UPDATE `tabLot` SET version = 'V1' WHERE capacity_planning = 0
        """
    )