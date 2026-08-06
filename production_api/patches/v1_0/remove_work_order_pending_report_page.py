import frappe


def execute():
	if frappe.db.exists("Page", "work-order-pending-report"):
		frappe.delete_doc(
			"Page",
			"work-order-pending-report",
			force=True,
			ignore_permissions=True,
		)
