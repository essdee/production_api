import frappe


def execute():
	if not frappe.db.exists("DocType", "WO Debit"):
		return
	if frappe.db.exists("DocType", "Essdee Debit"):
		return

	frappe.rename_doc("DocType", "WO Debit", "Essdee Debit", force=True)
	frappe.reload_doctype("Essdee Debit")
