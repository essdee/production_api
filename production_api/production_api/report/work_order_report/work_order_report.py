# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{"fieldname":"work_order","fieldtype":"Link","options":"Work Order","label":"Work Order"},
		{"fieldname":"wo_date","fieldtype":"Date","label":"WO Date"},
		{"fieldname":"supplier","fieldtype":"Link","options":"Supplier","label":"Supplier"},
		{"fieldname":"lot","fieldtype":"Link","options":"Lot","label":"Lot"},
		{"fieldname":"item","fieldtype":"Link","options":"Item","label":"Item"},
		{"fieldname":"wo_colours","fieldtype":"Data","label":"WO Colours"},
		{"fieldname":"process_name","fieldtype":"Link","options":"Process","label":"Process"},
		{"fieldname":"total_no_of_pieces_delivered","fieldtype":"Int","label":"Pieces Delivered"},
		{"fieldname":"total_no_of_pieces_received","fieldtype":"Int","label":"Pieces Received"},
		{"fieldname":"difference","fieldtype":"Int","label":"Difference"},	
		{"fieldname":"first_dc_date","fieldtype":"Date","label":"First DC Date"},
		{"fieldname":"last_dc_date","fieldtype":"Date","label":"Last DC Date"},
		{"fieldname":"first_grn_date","fieldtype":"Date","label":"First GRN Date"},
		{"fieldname":"last_grn_date","fieldtype":"Date","label":"Last GRN Date"},
	]

def get_data(filters):
	doctype = frappe.qb.DocType("Work Order")
	query = frappe.qb.from_(doctype).select(
		doctype.name.as_("work_order"),
		doctype.wo_date,
		doctype.supplier,
		doctype.lot,
		doctype.item,
		doctype.wo_colours,
		doctype.process_name,
		doctype.total_no_of_pieces_delivered,
		doctype.total_no_of_pieces_received,
		(doctype.total_no_of_pieces_delivered - doctype.total_no_of_pieces_received).as_("difference"),
		doctype.first_dc_date,
		doctype.last_dc_date,
		doctype.first_grn_date,
		doctype.last_grn_date,

	).where(doctype.docstatus == 1)

	if supplier := filters.get('supplier'):
		query = query.where(doctype.supplier == supplier)
	if process := filters.get("process_name"):
		query = query.where(doctype.process_name == process)
	if lot := filters.get("lot"):
		query = query.where(doctype.lot == lot)
	if item := filters.get("item"):
		query = query.where(doctype.item == item)	
	if status := filters.get("status"):
		if status == "Closed":
			query = query.where(doctype.open_status == "Close")

	res = query.run(as_dict=True)
	return res
