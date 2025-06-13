# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe, json
from six import string_types

def execute(filters=None):
	types = frappe.db.get_single_value("MRP Settings", "received_type_list")
	received_types = types.split(",")
	for t in received_types:
		t = t.strip()
	columns = get_columns(received_types)
	data = get_data(filters, received_types)
	return columns, data

def get_columns(received_types):
	columns = [
		{"fieldname":"work_order","fieldtype":"Link","options":"Work Order","label":"Work Order"},
		{"fieldname":"wo_date","fieldtype":"Date","label":"WO Date"},
		{"fieldname":"supplier","fieldtype":"Link","options":"Supplier","label":"Supplier"},
		{"fieldname":"supplier_name","fieldtype":"Data","label":"Supplier Name"},
		{"fieldname":"lot","fieldtype":"Link","options":"Lot","label":"Lot"},
		{"fieldname":"item","fieldtype":"Link","options":"Item","label":"Item"},
		{"fieldname":"wo_colours","fieldtype":"Data","label":"WO Colours"},
		{"fieldname":"process_name","fieldtype":"Link","options":"Process","label":"Process"},
		{"fieldname":"planned_quantity","fieldtype":"Int","label":"Pieces Planned"},
		{"fieldname":"total_no_of_pieces_delivered","fieldtype":"Int","label":"Pieces Delivered"},
		{"fieldname":"total_no_of_pieces_received","fieldtype":"Int","label":"Pieces Received"},
	]

	for t in received_types:
		x = t.replace(" ", "_")
		columns.append(
			{"fieldname": x,"fieldtype":"Int","label":t},
		)
	columns = columns + [
		{"fieldname":"others", "fieldtype":"Int","label":"Others"},
		{"fieldname":"pending","fieldtype":"Int","label":"Pending"},	
		{"fieldname":"first_dc_date","fieldtype":"Date","label":"First DC Date"},
		{"fieldname":"last_dc_date","fieldtype":"Date","label":"Last DC Date"},
		{"fieldname":"first_grn_date","fieldtype":"Date","label":"First GRN Date"},
		{"fieldname":"last_grn_date","fieldtype":"Date","label":"Last GRN Date"},
	]	
	return columns

def get_data(filters, received_types):
	doctype = frappe.qb.DocType("Work Order")
	query = frappe.qb.from_(doctype).select(
		doctype.name.as_("work_order"),
		doctype.wo_date,
		doctype.supplier,
		doctype.supplier_name,
		doctype.lot,
		doctype.item,
		doctype.wo_colours,
		doctype.process_name,
		doctype.planned_quantity,
		doctype.total_no_of_pieces_delivered,
		doctype.total_no_of_pieces_received,
		(doctype.total_no_of_pieces_received - doctype.total_no_of_pieces_delivered).as_("pending"),
		doctype.first_dc_date,
		doctype.last_dc_date,
		doctype.first_grn_date,
		doctype.last_grn_date,
		doctype.received_types_json
	).where((doctype.docstatus == 1) & (doctype.wo_date >= filters.get("from_date")) & (doctype.wo_date <= filters.get("to_date")))


	if supplier := filters.get('supplier'):
		query = query.where(doctype.supplier == supplier)
	if process := filters.get("process_name"):
		query = query.where(doctype.process_name == process)
	if lot := filters.get("lot"):
		query = query.where(doctype.lot == lot)
	if item := filters.get("item"):
		query = query.where(doctype.item == item)	
	if status := filters.get("status"):
		if status == "Close":
			query = query.where(doctype.open_status == "Close")
		elif status == "Open":
			query = query.where(doctype.open_status == "Open")

	result = query.run(as_dict=True)
	for res in result:
		received_json = res['received_types_json']
		if isinstance(received_json, string_types):
			received_json = json.loads(received_json)
		others = 0	
		if received_json:
			for t in received_json:
				if t not in received_types:
					others += received_json.get(t)
				elif t in received_types and received_json.get(t):
					x = t.replace(" ", "_")
					res.update({x: received_json.get(t)})
				else:
					x = t.replace(" ", "_")
					res.update({x: 0})

		res.update({"others":others})	

	return result
