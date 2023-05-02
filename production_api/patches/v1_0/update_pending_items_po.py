import frappe

def execute():
    # A new Column has been added to the Purchase Order Item table
    # This column is called "pending_qty"
    # Copy all the values from the qty column to the pending_qty column using SQL

    frappe.db.sql("""
        UPDATE `tabPurchase Order Item`
        SET pending_qty = qty
    """)
    # Update all cancelled Purchase Orders to have a pending_qty of 0 and cancelled_qty of qty
    frappe.db.sql("""
        UPDATE `tabPurchase Order Item`
        SET pending_qty = 0, cancelled_qty = qty
        WHERE docstatus = 2
    """)