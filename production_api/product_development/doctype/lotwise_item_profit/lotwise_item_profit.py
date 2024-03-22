# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class LotwiseItemProfit(Document):
	pass

@frappe.whitelist()
def get_lot_qty(lot, type):
	lot = frappe.get_doc("Lot", lot)
	d = {}
	for qty in lot.planned_qty:
		d[qty.size] = qty.get(type)
	return d