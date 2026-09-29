"""Close eligible Production Orders linked to existing OCR-completed plans."""

import frappe

from production_api.production_api.doctype.production_order.production_order import (
	close_production_order_if_all_lots_audited,
)


def execute():
	ocr_completed_lots = frappe.get_all(
		"Finishing Plan",
		filters={
			"fp_status": "OCR Completed",
			"lot": ("is", "set"),
		},
		pluck="lot",
	)
	if not ocr_completed_lots:
		return

	ocr_completed_lots = sorted(set(filter(None, ocr_completed_lots)))
	production_orders = frappe.get_all(
		"Lot",
		filters={
			"name": ("in", ocr_completed_lots),
			"production_order": ("is", "set"),
		},
		pluck="production_order",
	)
	for production_order in sorted(set(filter(None, production_orders))):
		close_production_order_if_all_lots_audited(production_order)

	frappe.db.commit()
