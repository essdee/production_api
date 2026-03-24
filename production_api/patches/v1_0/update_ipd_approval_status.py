import frappe


def execute():
	frappe.db.sql("""
		UPDATE `tabItem Production Detail`
		SET approval_status = 'Approved'
		WHERE approval_status IS NULL OR approval_status = 'Not Approved'
	""")
	frappe.db.commit()
