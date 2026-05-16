"""One-shot recovery patch.

The earlier `rename_wo_debit_to_essdee_debit` patch lived in [post_model_sync],
so `bench migrate` had already created an empty `tabEssdee Debit` from the new
DocType JSON before it ran. The guard `if frappe.db.exists("DocType", "Essdee Debit")`
caused the rename to skip, leaving the 14 production rows stranded in `tabWO Debit`
while the app read from the new empty `tabEssdee Debit`.

This patch copies the rows over with the schema mapping (work_order -> against/against_id).
It is safe to re-run: it short-circuits when `tabEssdee Debit` already has rows
or when `tabWO Debit` does not exist.
"""

import frappe


def execute():
	if not frappe.db.table_exists("WO Debit"):
		return

	if not frappe.db.has_column("WO Debit", "work_order"):
		return

	existing = frappe.db.sql("SELECT COUNT(*) FROM `tabEssdee Debit`")[0][0]
	if existing:
		return

	frappe.db.sql(
		"""
		INSERT INTO `tabEssdee Debit` (
			name, creation, modified, modified_by, owner, docstatus, idx,
			`against`, against_id, status, approved_by, debit_type,
			debit_no, debit_value, reason, debit_document, inspection, on_close,
			amended_from
		)
		SELECT
			name, creation, modified, modified_by, owner, docstatus, idx,
			'Work Order' AS `against`, work_order AS against_id, status, approved_by, debit_type,
			debit_no, debit_value, reason, debit_document, 0 AS inspection, on_close,
			amended_from
		FROM `tabWO Debit`
		"""
	)
	frappe.db.commit()
