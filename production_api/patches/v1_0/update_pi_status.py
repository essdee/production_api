import frappe

def execute():
    frappe.db.sql(
		"""
			UPDATE `tabPurchase Invoice` SET status = 'Draft' WHERE docstatus = 0
		"""
	)		
    frappe.db.sql(
		"""
			UPDATE `tabPurchase Invoice` SET status = 'Submitted' WHERE docstatus = 1
		"""
	)		
    frappe.db.sql(
		"""
			UPDATE `tabPurchase Invoice` SET status = 'Cancelled' WHERE docstatus = 2
		"""
	)		