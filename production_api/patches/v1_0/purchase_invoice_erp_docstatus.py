import frappe

def execute():
    frappe.db.sql("update `tabPurchase Invoice` set `erp_inv_docstatus` = 1 where `docstatus` = 1")
    frappe.db.sql("update `tabPurchase Invoice` set `erp_inv_docstatus` = 2 where `docstatus` = 2")