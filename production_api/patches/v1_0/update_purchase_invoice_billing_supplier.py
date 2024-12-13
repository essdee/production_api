import frappe

def execute():
    frappe.db.sql("UPDATE `tabPurchase Invoice` SET billing_supplier = supplier WHERE billing_supplier IS NULL")