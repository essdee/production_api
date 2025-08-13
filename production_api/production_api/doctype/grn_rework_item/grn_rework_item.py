# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class GRNReworkItem(Document):
	pass

@frappe.whitelist()
def revert_reworked_item(docname):
	doc = frappe.get_doc("GRN Rework Item", docname)
	warehouse = doc.warehouse
	single_doc = frappe.get_single("Stock Settings")
	accepted = single_doc.default_received_type
	rejected = single_doc.default_rejected_type	
	sl_entries = []
	for row in doc.grn_rework_item_details:
		if row.completed == 0:
			continue
		if row.rejection > 0:
			sl_entries.append({
				"item": row.item_variant,
				"warehouse": warehouse,
				"received_type": rejected,
				"lot": doc.lot,
				"voucher_type": "GRN Rework Item",
				"voucher_no": docname,
				"voucher_detail_no": row.name,
				"qty": row.rejection * -1,
				"uom": row.uom,
				"rate": 0,
				"valuation_rate": 0,
				"is_cancelled": 0,
				"posting_date": frappe.utils.nowdate(),
				"posting_time": frappe.utils.nowtime(),
			})
		if row.quantity - row.rejection > 0:
			sl_entries.append({
				"item": row.item_variant,
				"warehouse": warehouse,
				"received_type": accepted,
				"lot": doc.lot,
				"voucher_type": "GRN Rework Item",
				"voucher_no": docname,
				"voucher_detail_no": row.name,
				"qty":  (row.quantity - row.rejection) * -1,
				"uom": row.uom,
				"rate": 0,
				"valuation_rate": 0,
				"is_cancelled": 0,
				"posting_date": frappe.utils.nowdate(),
				"posting_time": frappe.utils.nowtime(),
			})			
		sl_entries.append({
			"item": row.item_variant,
			"warehouse": warehouse,
			"received_type": row.received_type,
			"lot": doc.lot,
			"voucher_type": "GRN Rework Item",
			"voucher_no": docname,
			"voucher_detail_no": row.name,
			"qty": row.quantity,
			"uom": row.uom,
			"rate": 0,
			"valuation_rate": 0,
			"is_cancelled": 0,
			"posting_date": frappe.utils.nowdate(),
			"posting_time": frappe.utils.nowtime(),
		})	
		row.completed = 0
	doc.completed = 0	
	doc.save(ignore_permissions=True)	
	from production_api.mrp_stock.stock_ledger import make_sl_entries
	make_sl_entries(sl_entries)
