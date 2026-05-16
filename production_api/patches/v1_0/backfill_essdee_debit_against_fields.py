import frappe


def execute():
	if not frappe.db.table_exists("Essdee Debit"):
		return

	if not frappe.db.has_column("Essdee Debit", "work_order"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabEssdee Debit`
		SET against = 'Work Order',
			against_id = work_order
		WHERE IFNULL(work_order, '') != ''
			AND IFNULL(against_id, '') = ''
		"""
	)
