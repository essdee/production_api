import frappe
def execute():
    frappe.db.sql(
        """
            DELETE FROM `tabLot Order Item` WHERE parent = 'C0425-05';
        """
    )
    frappe.db.sql(
        """
            DELETE FROM `tabLot Order Detail` WHERE parent = 'C0425-05';
        """
    )