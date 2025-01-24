import frappe

def execute():
    frappe.db.sql(
        """
            update `tabSingles` set value = 'Accepted' where doctype = 'Stock Settings' and field = 'default_received_type' 
        """
    )
    frappe.db.sql(
        """
            update `tabStock Entry Detail` set received_type = 'Accepted' where 1 = 1 
        """
    )
    frappe.db.sql(
        """
            update `tabStock Reconciliation Item` set received_type = 'Accepted' where 1 = 1 
        """
    )
    frappe.db.sql(
        """
            update `tabFG Stock Entry Detail` set received_type = 'Accepted' where 1 = 1 
        """
    )
    frappe.db.sql(
        """
            update `tabLot Transfer Item` set received_type = 'Accepted' where 1 = 1 
        """
    )
    frappe.db.sql(
        """
            update `tabBin` set received_type = 'Accepted' where 1 = 1 
        """
    )
    frappe.db.sql(
        """
            update `tabStock Ledger Entry` set received_type = 'Accepted' where 1 = 1 
        """
    )
    frappe.db.sql(
        """
            update `tabRepost Item Valuation` set received_type = 'Accepted' where based_on = 'Item and Warehouse' 
        """
    )
    frappe.db.sql(
        """
            update `tabStock Reservation Entry` set received_type = 'Accepted' where 1 = 1 
        """
    )
    
