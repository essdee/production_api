import frappe

def execute():
	frappe.db.sql("""
		UPDATE `tabProduction Order`
		SET submitted_by = modified_by, submitted_time = modified
		WHERE docstatus = 1
	""")
