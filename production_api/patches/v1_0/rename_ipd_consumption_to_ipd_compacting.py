import frappe


def execute():
	if not frappe.db.exists("DocType", "IPD Consumption"):
		return
	if frappe.db.exists("DocType", "IPD Compacting"):
		return

	frappe.rename_doc(
		"DocType",
		"IPD Consumption",
		"IPD Compacting",
		force=True,
	)
