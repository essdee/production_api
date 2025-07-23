# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from production_api.mrp_stock.utils import get_combine_datetime

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "options": "Cut Bundle Movement Ledger", "label": "Name"},
		{"fieldname": "lot", "fieldtype": "Link", "options": "Lot", "label": "Lot"},
		{"fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "label": "Supplier"},
		{"fieldname": "supplier_name", "fieldtype": "Data", "label": "Supplier Name"},
		{"fieldname": "item", "fieldtype": "Link", "options": "Item", "label": "Item"},
		{"fieldname": "lay_no", "fieldtype": "Int", "label": "Lay No"},
		{"fieldname": "bundle_no", "fieldtype": "Int", "label": "Bundle No"},
		{"fieldname": "size", "fieldtype": "Data", "label": "Size"},
		{"fieldname": "colour", "fieldtype": "Data", "label": "Colour"},
		{"fieldname": "shade", "fieldtype": "Data", "label": "Shade"},
		{"fieldname": "panel", "fieldtype": "Data", "label": "Panel"},
		{"fieldname": "qty", "fieldtype": "Int", "label": "Quantity"},
	]

def get_data(filters):
	date_time = get_combine_datetime(frappe.utils.nowdate(), frappe.utils.nowtime())
	conditions1 = ""
	conditions2 = ""
	con = {
		"datetime_value": date_time
	}
	if filters.get("lot"):
		conditions1 += f" AND lot = %(lot)s"
		conditions2 += f" AND cbml.lot = %(lot)s"

		con['lot'] = filters.get("lot")

	if filters.get("supplier"):
		conditions1 += f" AND supplier = %(supplier)s"
		conditions2 += f" AND cbml.supplier = %(supplier)s"

		con['supplier'] = filters.get("supplier")	

	cb_list = frappe.db.sql(
		f"""
			SELECT cbml.name, cbml.lot, cbml.supplier, cbml.supplier_name, cbml.lay_no, cbml.bundle_no, 
				cbml.quantity_after_transaction as qty, cbml.panel, cbml.shade, cbml.item, cbml.size, 
				cbml.colour FROM `tabCut Bundle Movement Ledger` cbml
				INNER JOIN (
					SELECT cbm_key, MAX(posting_datetime) AS max_posting_datetime, lay_no FROM `tabCut Bundle Movement Ledger`
					WHERE posting_datetime <= %(datetime_value)s AND is_cancelled = 0 AND collapsed_bundle = 0
					AND is_collapsed = 0 AND transformed = 0 {conditions1}
 					GROUP BY cbm_key
				) latest_cbml
			ON cbml.cbm_key = latest_cbml.cbm_key AND cbml.posting_datetime = latest_cbml.max_posting_datetime
			WHERE cbml.posting_datetime <= %(datetime_value)s AND cbml.is_collapsed = 0 AND cbml.collapsed_bundle = 0
			AND cbml.quantity_after_transaction > 0 AND cbml.is_cancelled = 0 {conditions2} 
			ORDER BY latest_cbml.lay_no asc
		""", con, as_dict=True)

	return cb_list
