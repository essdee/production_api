"""Backfill fp_status on existing Finishing Plans using compute_received_status.

Only moves docs currently in an auto-managed status (or blank). Finishing Plans
that have already been pushed to OCR Requested / OCR Completed / P&L Submitted
by the user are left alone.
"""
import frappe
from production_api.production_api.doctype.finishing_plan.finishing_plan import (
	compute_received_status,
	AUTO_FP_STATUSES,
)


def execute():
	names = frappe.get_all("Finishing Plan", pluck="name")
	updated = 0
	skipped = 0
	for name in names:
		doc = frappe.get_doc("Finishing Plan", name)
		current = doc.fp_status or ""
		if current not in AUTO_FP_STATUSES:
			skipped += 1
			continue
		new_status = compute_received_status(doc)
		if not new_status:
			new_status = "Planned"
		if new_status != current:
			frappe.db.set_value("Finishing Plan", name, "fp_status", new_status, update_modified=False)
			updated += 1
	frappe.db.commit()
	print(f"Finishing Plan fp_status backfill: updated={updated} skipped={skipped} total={len(names)}")
