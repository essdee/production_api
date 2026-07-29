"""Backfill status="Open" on existing submitted Production Orders.

Only touches docstatus=1 docs whose status is empty. Draft and cancelled
Production Orders are left untouched.
"""
import frappe


def execute():
	names = frappe.get_all(
		"Production Order",
		filters={"docstatus": 1, "status": ["is", "not set"]},
		pluck="name",
	)
	for name in names:
		frappe.db.set_value("Production Order", name, "status", "Open", update_modified=False)
	frappe.db.commit()
	print(f"Production Order status backfill: updated={len(names)}")
