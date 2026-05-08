import frappe


def execute():
	"""Backfill `tabFG Stock Entry Detail.lot` from the parent `tabFG Stock Entry.lot`.

	The `lot` field has been moved from FG Stock Entry (parent) down to
	FG Stock Entry Detail (child). The parent column is dropped via the
	updated doctype JSON; this patch fills the new child column from the
	old parent values before the column is removed.
	"""
	if not frappe.db.has_column("FG Stock Entry", "lot"):
		return
	if not frappe.db.has_column("FG Stock Entry Detail", "lot"):
		return

	frappe.db.sql("""
		UPDATE `tabFG Stock Entry Detail` d
		JOIN `tabFG Stock Entry` p ON d.parent = p.name
		SET d.lot = p.lot
		WHERE (d.lot IS NULL OR d.lot = '')
		  AND p.lot IS NOT NULL AND p.lot != ''
	""")
