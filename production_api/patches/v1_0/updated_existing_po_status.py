import frappe

def execute():
    frappe.db.sql("""
        UPDATE `tabPurchase Order`
        SET status = 'Draft'
    """)
    frappe.db.sql("""
        UPDATE `tabPurchase Order`
        SET status = 'Ordered'
        WHERE docstatus = 1
    """)