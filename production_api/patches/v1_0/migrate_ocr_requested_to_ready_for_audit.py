"""Move legacy OCR requests into the Accounts audit workflow."""

import frappe
from frappe.utils import date_diff, getdate, today

from production_api.production_api.doctype.production_order.production_order import (
	close_production_order_if_all_lots_audited,
)


def execute():
	if (
		not frappe.db.get_single_value("MRP Settings", "accounts_user_role")
		and frappe.db.exists("Role", "Accounts User")
	):
		frappe.db.set_single_value(
			"MRP Settings", "accounts_user_role", "Accounts User"
		)

	legacy_requests = frappe.get_all(
		"Finishing Plan",
		filters={"fp_status": ("in", ["OCR Requested", "Ready for Audit"])},
		fields=["name", "lot", "modified", "audit_requested_date"],
	)
	affected_lots = set()
	for row in legacy_requests:
		request_date = getdate(row.audit_requested_date or row.modified)
		is_older_than_30_days = date_diff(today(), request_date) > 30
		values = {
			"fp_status": (
				"OCR Completed" if is_older_than_30_days else "Ready for Audit"
			),
			"audit_requested_date": request_date,
		}
		if is_older_than_30_days:
			values["audit_completed_date"] = today()
		frappe.db.set_value(
			"Finishing Plan",
			row.name,
			values,
			update_modified=False,
		)
		if row.lot:
			affected_lots.add(row.lot)

	if affected_lots:
		production_orders = {
			row.production_order
			for row in frappe.get_all(
				"Lot",
				filters={"name": ("in", list(affected_lots))},
				fields=["production_order"],
			)
			if row.production_order
		}
		for production_order in sorted(production_orders):
			close_production_order_if_all_lots_audited(production_order)

	frappe.db.commit()
